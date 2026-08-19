import base64

from core.models.object_types import ObjectType

from netbox_drawio.models import Diagram, DiagramAssignment

SAMPLE_XML = (
    '<mxfile host="embed.diagrams.net"><diagram name="Page-1">'
    '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel>'
    "</diagram></mxfile>"
)

SAMPLE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
    '<rect width="100" height="50" fill="lightblue"/><text x="10" y="30">test</text></svg>'
)


def sample_svg_data_uri(svg=SAMPLE_SVG):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def make_diagram(name, **kwargs):
    kwargs.setdefault("source_xml", SAMPLE_XML)
    kwargs.setdefault("svg_cache", SAMPLE_SVG)
    return Diagram.objects.create(name=name, **kwargs)


def assign(diagram, obj):
    return DiagramAssignment.objects.create(
        diagram=diagram,
        object_type=ObjectType.objects.get_for_model(obj),
        object_id=obj.pk,
    )
