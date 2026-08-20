from core.models.object_types import ObjectType
from django import forms
from django.urls import NoReverseMatch
from django.utils.translation import gettext_lazy as _
from netbox.forms import (
    NetBoxModelBulkEditForm,
    NetBoxModelFilterSetForm,
    NetBoxModelForm,
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelForm,
)
from utilities.forms.fields import (
    CommentField,
    ContentTypeChoiceField,
    ContentTypeMultipleChoiceField,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    TagFilterField,
)
from utilities.forms.utils import get_field_value
from utilities.forms.widgets import HTMXSelect
from utilities.forms.widgets.apiselect import APISelect
from utilities.views import get_action_url

from netbox_drawio.models import Diagram, DiagramAssignment
from netbox_drawio.utils import get_enabled_object_type_queryset


class DiagramForm(PrimaryModelForm):
    comments = CommentField(label="Comment")

    class Meta:
        model = Diagram
        fields = [
            "name",
            "description",
            "owner_group",
            "owner",
            "comments",
            "tags",
        ]

    def save(self, commit=True):
        """
        After saving the diagram, create an assignment if pending context is set.
        The view's alter_object() sets _pending_object_type and _pending_object_id
        on the instance — already validated against the enabled-type allowlist and
        the user's view permission — to pass context into this save() method.
        """
        obj = super().save(commit=commit)

        if commit:
            object_type = getattr(self.instance, "_pending_object_type", None)
            object_id = getattr(self.instance, "_pending_object_id", None)
            if object_type is not None and object_id is not None:
                DiagramAssignment.objects.get_or_create(
                    diagram=obj,
                    object_type=object_type,
                    object_id=object_id,
                )

        return obj


class DiagramLinkForm(NetBoxModelForm):
    """Form for linking an existing diagram to a NetBox object."""

    diagram = DynamicModelChoiceField(
        queryset=Diagram.objects.all(),
        selector=True,
        label=_("Diagram"),
    )
    object_type = ContentTypeChoiceField(
        queryset=ObjectType.objects.all(),
        required=False,
        label=_("Object Type"),
        widget=HTMXSelect(),
    )
    object = DynamicModelChoiceField(
        queryset=ObjectType.objects.none(),  # placeholder; updated in __init__
        required=False,
        disabled=True,
        label=_("Object"),
    )

    class Meta:
        model = DiagramAssignment
        fields = ["diagram", "tags"]  # object_type / object handled manually

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.object_type_id:
            # Forward flow: object already resolved — hide picker fields
            del self.fields["object_type"]
            del self.fields["object"]
        else:
            # Restrict choices to models enabled in the plugin config
            self.fields["object_type"].queryset = get_enabled_object_type_queryset()
            if object_type_id := get_field_value(self, "object_type"):
                # Reverse flow after HTMX reload: enable object picker for chosen type
                try:
                    obj_type = get_enabled_object_type_queryset().get(pk=object_type_id)
                    model = obj_type.model_class()
                    # Probe whether a REST API list URL exists for this model
                    try:
                        get_action_url(model, action="list", rest_api=True)
                        api_available = True
                    except NoReverseMatch:
                        api_available = False

                    if api_available:
                        self.fields["object"].queryset = model.objects.all()
                        self.fields["object"].model = model  # update field's model ref for selector
                        self.fields["object"].selector = True  # now safe: model is the real target
                        self.fields["object"].widget.attrs["selector"] = (
                            model._meta.label_lower
                        )  # bake into widget attrs for template
                        self.fields["object"].disabled = False
                        self.fields["object"].label = _(model._meta.verbose_name.title())
                    else:
                        # Model has no REST API endpoint — use a static ModelChoiceField
                        self.fields["object"] = forms.ModelChoiceField(
                            queryset=model.objects.all(),
                            required=True,
                            label=_(model._meta.verbose_name.title()),
                        )
                except (ObjectType.DoesNotExist, ValueError):
                    pass  # Invalid or missing pk; object picker stays disabled
                except (AttributeError, TypeError):
                    pass  # model_class() returned None or model has no manager

    def clean(self):
        super().clean()
        cleaned_data = self.cleaned_data
        diagram = cleaned_data.get("diagram")

        object_type = getattr(self.instance, "object_type", None)
        object_id = getattr(self.instance, "object_id", None)

        # Reverse flow: resolve from form fields
        if not object_type:
            object_type = cleaned_data.get("object_type")
            obj = cleaned_data.get("object")
            if not object_type:
                self.add_error("object_type", _("Object type is required."))
            if not obj:
                self.add_error("object", _("Object is required."))
            if object_type and obj:
                self.instance.object_type = object_type
                self.instance.object_id = obj.pk
                object_id = obj.pk

        # Duplicate-assignment check
        if diagram and object_type and object_id:
            qs = DiagramAssignment.objects.filter(
                diagram=diagram,
                object_type=object_type,
                object_id=object_id,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(_("This diagram is already linked to this object."))

        return cleaned_data


class DiagramAssignmentForm(NetBoxModelForm):
    class Meta:
        model = DiagramAssignment
        fields = ["tags"]


class DiagramFilterForm(PrimaryModelFilterSetForm):
    model = Diagram
    # Substring semantics for the UI text boxes; plain ?name= is exact-match
    name__ic = forms.CharField(required=False, label=_("Name"))
    description__ic = forms.CharField(required=False, label=_("Description"))
    object_type_id = DynamicModelChoiceField(
        queryset=ObjectType.objects.all(),
        required=False,
        label=_("Object Type"),
        widget=APISelect(
            api_url="/api/core/object-types/",
        ),
    )
    has_assignments = forms.ChoiceField(
        required=False,
        label=_("Has Assignments"),
        choices=[
            ("", "---------"),
            ("true", _("Yes")),
            ("false", _("No")),
        ],
    )
    tag = TagFilterField(model)


class DiagramAssignmentFilterForm(NetBoxModelFilterSetForm):
    model = DiagramAssignment
    diagram_id = DynamicModelMultipleChoiceField(
        queryset=Diagram.objects.all(),
        required=False,
        label=_("Diagram"),
    )
    object_type_id = ContentTypeMultipleChoiceField(
        queryset=ObjectType.objects.all(),
        required=False,
        label=_("Object Type"),
    )
    tag = TagFilterField(model)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Deferred like DiagramLinkForm: the enabled-type allowlist depends on runtime config
        self.fields["object_type_id"].queryset = get_enabled_object_type_queryset().order_by("app_label", "model")


class DiagramBulkEditForm(PrimaryModelBulkEditForm):
    description = forms.CharField(
        widget=forms.Textarea,
        max_length=Diagram._meta.get_field("description").max_length,
        required=False,
    )

    model = Diagram
    nullable_fields = ("description", "owner")


class DiagramAssignmentBulkEditForm(NetBoxModelBulkEditForm):
    model = DiagramAssignment
    nullable_fields = ()
