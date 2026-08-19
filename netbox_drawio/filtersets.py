import django_filters
from django.db.models import Q
from extras.filters import TagFilter
from netbox.filtersets import NetBoxModelFilterSet
from users.filterset_mixins import OwnerFilterMixin
from utilities.filtersets import register_filterset

from netbox_drawio.models import Diagram, DiagramAssignment


@register_filterset
class DiagramFilterSet(OwnerFilterMixin, NetBoxModelFilterSet):
    q = django_filters.CharFilter(method="search", label="Search")
    created = django_filters.DateTimeFilter()
    name = django_filters.CharFilter(lookup_expr="icontains")
    description = django_filters.CharFilter(lookup_expr="icontains")
    tag = TagFilter()

    # Filters routed through the assignment relation
    object_type_id = django_filters.NumberFilter(
        method="filter_object_type_id",
        label="Object Type (ID)",
    )
    object_id = django_filters.NumberFilter(
        method="filter_object_id",
        label="Object ID",
    )
    has_assignments = django_filters.BooleanFilter(
        method="filter_has_assignments",
        label="Has Assignments",
    )

    class Meta:
        model = Diagram
        fields = ["id", "name", "description"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset

        filters = Q(name__icontains=value) | Q(description__icontains=value)
        return queryset.filter(filters)

    def filter_object_type_id(self, queryset, name, value):
        return queryset.filter(assignments__object_type_id=value).distinct()

    def filter_object_id(self, queryset, name, value):
        return queryset.filter(assignments__object_id=value).distinct()

    def filter_has_assignments(self, queryset, name, value):
        if value:
            return queryset.filter(assignments__isnull=False).distinct()
        return queryset.filter(assignments__isnull=True).distinct()


@register_filterset
class DiagramAssignmentFilterSet(NetBoxModelFilterSet):
    q = django_filters.CharFilter(method="search", label="Search")
    tag = TagFilter()
    diagram_id = django_filters.NumberFilter(
        field_name="diagram_id",
        label="Diagram (ID)",
    )
    object_type_id = django_filters.NumberFilter(
        field_name="object_type_id",
        label="Object Type (ID)",
    )
    object_id = django_filters.NumberFilter(
        field_name="object_id",
        label="Object ID",
    )

    class Meta:
        model = DiagramAssignment
        fields = ["id", "diagram_id", "object_type_id", "object_id"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset

        return queryset.filter(Q(diagram__name__icontains=value) | Q(diagram__description__icontains=value))
