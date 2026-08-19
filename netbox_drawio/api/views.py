from netbox.api.metadata import ContentTypeMetadata
from netbox.api.viewsets import NetBoxModelViewSet

from netbox_drawio import filtersets, models
from netbox_drawio.api.serializers import DiagramAssignmentSerializer, DiagramSerializer


class DiagramViewSet(NetBoxModelViewSet):
    metadata_class = ContentTypeMetadata
    queryset = models.Diagram.objects.prefetch_related(
        "assignments",
        "assignments__object_type",
    )
    serializer_class = DiagramSerializer
    filterset_class = filtersets.DiagramFilterSet


class DiagramAssignmentViewSet(NetBoxModelViewSet):
    metadata_class = ContentTypeMetadata
    queryset = models.DiagramAssignment.objects.select_related(
        "diagram",
        "object_type",
    )
    serializer_class = DiagramAssignmentSerializer
    filterset_class = filtersets.DiagramAssignmentFilterSet
