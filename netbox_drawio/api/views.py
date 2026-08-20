from netbox.api.metadata import ContentTypeMetadata
from netbox.api.viewsets import NetBoxModelViewSet

from netbox_drawio import filtersets, models
from netbox_drawio.api.serializers import DiagramAssignmentSerializer, DiagramListSerializer, DiagramSerializer


class DiagramViewSet(NetBoxModelViewSet):
    metadata_class = ContentTypeMetadata
    queryset = models.Diagram.objects.prefetch_related(
        "assignments",
        "assignments__object_type",
    )
    serializer_class = DiagramSerializer
    filterset_class = filtersets.DiagramFilterSet

    def get_serializer_class(self):
        if self.action == "list":
            return DiagramListSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            # Pairs with DiagramListSerializer: without the serializer change,
            # deferring would re-fetch both blobs per row (N+1)
            queryset = queryset.defer("source_xml", "svg_cache")
        return queryset


class DiagramAssignmentViewSet(NetBoxModelViewSet):
    metadata_class = ContentTypeMetadata
    queryset = models.DiagramAssignment.objects.select_related(
        "diagram",
        "object_type",
    )
    serializer_class = DiagramAssignmentSerializer
    filterset_class = filtersets.DiagramAssignmentFilterSet
