from netbox.search import SearchIndex, register_search

from netbox_drawio.models import Diagram


@register_search
class DiagramIndex(SearchIndex):
    model = Diagram
    fields = (
        ("name", 100),
        ("description", 500),
        ("comments", 5000),
    )
    display_attrs = ("description",)
