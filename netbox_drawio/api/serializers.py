from core.models.object_types import ObjectType
from django.core.exceptions import ObjectDoesNotExist
from netbox.api.fields import ContentTypeField
from netbox.api.serializers import NetBoxModelSerializer, PrimaryModelSerializer
from rest_framework import serializers
from utilities.api import get_serializer_for_model

from netbox_drawio.constants import BLOB_FIELDS
from netbox_drawio.models import Diagram, DiagramAssignment
from netbox_drawio.utils import get_setting, validate_object_type


class ObjectTypeField(ContentTypeField):
    """
    ContentTypeField that returns an ObjectType (NetBox proxy) instance instead
    of a plain Django ContentType.  NetBox's ContentTypeField.to_internal_value()
    hardcodes ContentType.objects, so the ForeignKey(to=ObjectType) would reject
    the returned value without this cast.
    """

    def to_internal_value(self, data):
        ct = super().to_internal_value(data)
        return ObjectType.objects.get(pk=ct.pk)


class DiagramAssignmentSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_drawio-api:diagramassignment-detail")
    diagram = serializers.PrimaryKeyRelatedField(queryset=Diagram.objects.all())
    object_type = ObjectTypeField(queryset=ObjectType.objects.all())
    parent = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DiagramAssignment
        fields = [
            "id",
            "url",
            "display",
            "diagram",
            "object_type",
            "object_id",
            "parent",
            "custom_fields",
            "tags",
            "created",
            "last_updated",
        ]
        brief_fields = ("id", "url", "display", "object_type", "object_id")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        # "diagram" is absent in brief mode (not in brief_fields)
        if request and hasattr(request, "user") and "diagram" in self.fields:
            self.fields["diagram"].queryset = Diagram.objects.restrict(request.user, "view")

    def validate(self, data):
        # Validate that the parent object exists.
        # Fall back to instance values so PATCH requests that only supply one
        # of the two fields are still validated against the full pair.
        object_type = data.get("object_type", getattr(self.instance, "object_type", None))
        object_id = data.get("object_id", getattr(self.instance, "object_id", None))
        if object_type is not None and object_id is not None:
            # Enforce plugin scope on the target model
            model_class = object_type.model_class()
            if model_class is None or not validate_object_type(model_class):
                raise serializers.ValidationError({"object_type": "This object type is not permitted for diagrams."})
            # Restrict to objects the requesting user may view, so forbidden and
            # nonexistent pks are indistinguishable (no existence oracle).
            queryset = model_class.objects.all()
            request = self.context.get("request")
            if request and hasattr(request, "user") and hasattr(queryset, "restrict"):
                queryset = queryset.restrict(request.user, "view")
            if not queryset.filter(pk=object_id).exists():
                raise serializers.ValidationError("Invalid parent object: {} ID {}".format(object_type, object_id))
        return super().validate(data)

    def get_parent(self, obj):
        try:
            parent = obj.parent
        except ObjectDoesNotExist:
            return None

        if parent is None:
            return None

        # Hide parents the requesting user is not permitted to view. This costs
        # one extra query per row on list views; accepted for correctness.
        request = self.context.get("request")
        queryset = type(parent).objects.all()
        if request and hasattr(request, "user") and hasattr(queryset, "restrict"):
            if not queryset.restrict(request.user, "view").filter(pk=parent.pk).exists():
                return None

        serializer = get_serializer_for_model(parent.__class__)
        return serializer(parent, nested=True, context=self.context).data


class DiagramSerializer(PrimaryModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="plugins-api:netbox_drawio-api:diagram-detail")
    source_xml = serializers.CharField(required=False, allow_blank=True)
    svg_cache = serializers.CharField(required=False, allow_blank=True)
    assignments = DiagramAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = Diagram
        fields = [
            "id",
            "url",
            "display",
            "name",
            "description",
            "source_xml",
            "svg_cache",
            "owner",
            "assignments",
            "created",
            "last_updated",
            "comments",
            "custom_fields",
            "tags",
        ]
        brief_fields = ("id", "url", "display", "name", "description")

    def _validate_blob_size(self, value, label):
        max_size = int(get_setting("max_size"))
        if value and len(value.encode("utf-8")) > max_size:
            raise serializers.ValidationError(f"{label} exceeds the maximum allowed size ({max_size} bytes)")
        return value

    def validate_source_xml(self, value):
        return self._validate_blob_size(value, "Diagram XML")

    def validate_svg_cache(self, value):
        return self._validate_blob_size(value, "SVG cache")


class DiagramListSerializer(DiagramSerializer):
    """
    List-action serializer: omits the XML/SVG blobs, which can reach max_size
    (10 MB by default) per row. Retrieve a diagram individually to get them.
    """

    # Declared-field removals must stay literal; keep in sync with BLOB_FIELDS
    source_xml = None
    svg_cache = None

    class Meta(DiagramSerializer.Meta):
        fields = [f for f in DiagramSerializer.Meta.fields if f not in BLOB_FIELDS]
