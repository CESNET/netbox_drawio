import json

from django.db.models import Count
from django.db.models.functions import Length
from django.http import HttpResponse, HttpResponseNotModified, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import View
from netbox.views import generic
from utilities.views import ConditionalLoginRequiredMixin, register_model_view

from netbox_drawio import filtersets, forms, models, tables
from netbox_drawio.utils import (
    build_embed_url,
    decode_svg_data_uri,
    get_embed_origin,
    get_enabled_object_type_queryset,
    get_setting,
)

# CSP for the raw SVG endpoint: draw.io SVGs need inline styles and data: images/fonts;
# scripts are blocked even on direct navigation to the URL.
SVG_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; sandbox"


@register_model_view(models.Diagram, name="", detail=True)
class DiagramView(generic.ObjectView):
    queryset = models.Diagram.objects.select_related(
        "owner",
        "owner__group",
    ).prefetch_related(
        "assignments",
        "assignments__object_type",
    )

    def get_extra_context(self, request, instance):
        assignments_table = tables.DiagramAssignmentTable(
            instance.assignments.all(),
            exclude=("diagram",),
        )
        assignments_table.configure(request)
        return {
            "assignments_table": assignments_table,
        }


@register_model_view(models.Diagram, name="list", path="", detail=False)
class DiagramListView(generic.ObjectListView):
    actions = {
        "add": {"add"},
        "export": set(),
        "bulk_edit": {"change"},
        "bulk_delete": {"delete"},
    }
    queryset = (
        models.Diagram.objects.defer("source_xml", "svg_cache")
        .select_related("owner", "owner__group")
        .prefetch_related("assignments", "assignments__object_type")
        .annotate(
            assignment_count=Count("assignments", distinct=True),
            svg_size=Length("svg_cache"),
        )
    )
    table = tables.DiagramTable
    filterset = filtersets.DiagramFilterSet
    filterset_form = forms.DiagramFilterForm


@register_model_view(models.Diagram, name="add", detail=False)
@register_model_view(models.Diagram, name="edit", detail=True)
class DiagramEditView(generic.ObjectEditView):
    queryset = models.Diagram.objects.all()
    form = forms.DiagramForm
    default_return_url = "plugins:netbox_drawio:diagram_list"

    def alter_object(self, instance, request, args, kwargs):
        if not instance.pk:
            try:
                object_type_id = int(request.GET.get("object_type", ""))
                object_id = int(request.GET.get("object_id", ""))
            except (TypeError, ValueError):
                return instance
            if object_type_id and object_id:
                object_type = get_object_or_404(get_enabled_object_type_queryset(), pk=object_type_id)
                model = object_type.model_class()
                if model is None:
                    return instance
                get_object_or_404(model.objects.restrict(request.user, "view"), pk=object_id)
                # Pass validated assignment context to the form's save() via instance attributes
                instance._pending_object_type_id = object_type.pk
                instance._pending_object_id = object_id
        return instance

    def get_extra_addanother_params(self, request):
        return_url = request.GET.get("return_url")
        if return_url and not url_has_allowed_host_and_scheme(
            return_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return_url = None
        return {
            "object_type": request.GET.get("object_type"),
            "object_id": request.GET.get("object_id"),
            "return_url": return_url,
        }


@register_model_view(models.Diagram, name="delete", detail=True)
class DiagramDeleteView(generic.ObjectDeleteView):
    queryset = models.Diagram.objects.all()
    default_return_url = "plugins:netbox_drawio:diagram_list"


@register_model_view(models.Diagram, "bulk_edit", path="edit", detail=False)
class DiagramBulkEditView(generic.BulkEditView):
    queryset = models.Diagram.objects.defer("source_xml", "svg_cache").annotate(
        assignment_count=Count("assignments", distinct=True),
        svg_size=Length("svg_cache"),
    )
    filterset = filtersets.DiagramFilterSet
    table = tables.DiagramTable
    form = forms.DiagramBulkEditForm


@register_model_view(models.Diagram, "bulk_delete", path="delete", detail=False)
class DiagramBulkDeleteView(generic.BulkDeleteView):
    queryset = models.Diagram.objects.defer("source_xml", "svg_cache").annotate(
        assignment_count=Count("assignments", distinct=True),
        svg_size=Length("svg_cache"),
    )
    filterset = filtersets.DiagramFilterSet
    table = tables.DiagramTable
    default_return_url = "plugins:netbox_drawio:diagram_list"


@register_model_view(models.Diagram, name="editor", path="editor", detail=True)
class DiagramEditorView(generic.ObjectView):
    """Full-page draw.io editor embedded via iframe (postMessage embed protocol)."""

    queryset = models.Diagram.objects.all()
    template_name = "netbox_drawio/diagram_editor.html"

    def get_required_permission(self):
        # Editing diagram content requires change permission, not just view
        return "netbox_drawio.change_diagram"

    def get_extra_context(self, request, instance):
        return_url = request.GET.get("return_url")
        if return_url and not url_has_allowed_host_and_scheme(
            return_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return_url = None
        if not return_url:
            return_url = instance.get_absolute_url()

        embed_url = build_embed_url()
        return {
            "embed_url": embed_url,
            "return_url": return_url,
            "drawio_config": {
                "embedOrigin": get_embed_origin(embed_url),
                "saveUrl": reverse("plugins:netbox_drawio:diagram_save", kwargs={"pk": instance.pk}),
                "returnUrl": return_url,
                "csrfToken": get_token(request),
                "autosave": bool(get_setting("autosave")),
                "xml": instance.source_xml,
            },
        }


@register_model_view(models.Diagram, name="save", path="save", detail=True)
class DiagramSaveView(ConditionalLoginRequiredMixin, View):
    """
    Save endpoint for the embedded editor. Accepts JSON
    {"xml": "<mxfile...>", "svg_data_uri": "data:image/svg+xml;base64,..."} via POST.
    """

    def post(self, request, pk):
        diagram = get_object_or_404(models.Diagram.objects.restrict(request.user, "change"), pk=pk)
        max_size = int(get_setting("max_size"))

        # Reject oversized requests before parsing (base64 + JSON overhead margin)
        try:
            content_length = int(request.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            content_length = 0
        if content_length > max_size * 3:
            return JsonResponse({"error": "Request too large"}, status=413)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)
        if not isinstance(data, dict):
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)

        xml = data.get("xml")
        if not isinstance(xml, str) or not xml.strip():
            return JsonResponse({"error": "Missing diagram XML"}, status=400)
        if len(xml.encode("utf-8")) > max_size:
            return JsonResponse({"error": "Diagram XML exceeds the maximum allowed size"}, status=413)
        head = xml.lstrip()[:1000]
        if not head.startswith("<") or ("mxfile" not in head and "mxGraphModel" not in head):
            return JsonResponse({"error": "Payload is not a draw.io diagram"}, status=400)

        svg = ""
        svg_data_uri = data.get("svg_data_uri")
        if svg_data_uri:
            try:
                svg = decode_svg_data_uri(svg_data_uri)
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=400)
            if len(svg.encode("utf-8")) > max_size:
                return JsonResponse({"error": "SVG exceeds the maximum allowed size"}, status=413)

        diagram.snapshot()
        diagram.source_xml = xml
        if svg:
            diagram.svg_cache = svg
        diagram.save()

        return JsonResponse(
            {
                "status": "ok",
                "last_updated": diagram.last_updated.isoformat() if diagram.last_updated else None,
            }
        )


@register_model_view(models.Diagram, name="svg", path="svg", detail=True)
class DiagramSVGView(ConditionalLoginRequiredMixin, View):
    """Raw SVG preview endpoint; everything renders it via <img src>."""

    def get(self, request, pk):
        diagram = get_object_or_404(
            models.Diagram.objects.restrict(request.user, "view").only(
                "id", "name", "svg_cache", "content_hash", "last_updated"
            ),
            pk=pk,
        )
        if not diagram.svg_cache:
            return HttpResponse(status=404)

        if diagram.content_hash:
            etag = f'"{diagram.content_hash}"'
        elif diagram.last_updated:
            etag = f'"{diagram.last_updated.timestamp()}"'
        else:
            etag = None
        if etag and request.headers.get("If-None-Match") == etag:
            return HttpResponseNotModified()

        response = HttpResponse(diagram.svg_cache, content_type="image/svg+xml; charset=utf-8")
        response["Content-Security-Policy"] = SVG_CSP
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Disposition"] = f'inline; filename="diagram-{diagram.pk}.svg"'
        if etag:
            response["ETag"] = etag
        return response


@register_model_view(models.Diagram, name="source", path="source", detail=True)
class DiagramSourceView(ConditionalLoginRequiredMixin, View):
    """Download the diagram source as a .drawio file."""

    def get(self, request, pk):
        diagram = get_object_or_404(
            models.Diagram.objects.restrict(request.user, "view").only("id", "name", "source_xml"),
            pk=pk,
        )
        if not diagram.source_xml:
            return HttpResponse(status=404)

        response = HttpResponse(diagram.source_xml, content_type="application/xml; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="diagram-{diagram.pk}.drawio"'
        return response


class DiagramLinkView(generic.ObjectEditView):
    """Link an existing diagram to a NetBox object."""

    queryset = models.DiagramAssignment.objects.all()
    form = forms.DiagramLinkForm
    template_name = "netbox_drawio/diagram_link.html"
    default_return_url = "plugins:netbox_drawio:diagram_list"

    def alter_object(self, instance, request, args, kwargs):
        if not instance.pk:
            try:
                object_type_id = int(request.GET.get("object_type", ""))
                object_id = int(request.GET.get("object_id", ""))
            except (TypeError, ValueError):
                return instance
            # Only pre-populate when both are valid integers (forward flow from a
            # detail page). HTMX re-renders supply only object_type; they are
            # rejected above, leaving the instance untouched so the form resolves
            # the selection via get_field_value.
            if object_type_id and object_id:
                object_type = get_object_or_404(get_enabled_object_type_queryset(), pk=object_type_id)
                model = object_type.model_class()
                if model is None:
                    return instance
                get_object_or_404(model.objects.restrict(request.user, "view"), pk=object_id)
                instance.object_type = object_type
                instance.object_id = object_id
        return instance

    def get_extra_addanother_params(self, request):
        return_url = request.GET.get("return_url")
        if return_url and not url_has_allowed_host_and_scheme(
            return_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return_url = None
        if request.GET.get("diagram"):
            # Diagram-forward flow: keep diagram pre-selected so the user
            # only needs to pick a new target object for the next assignment.
            return {"diagram": request.GET["diagram"], "return_url": return_url}
        # Object-forward flow: keep object context so the user keeps linking
        # diagrams to the same object.
        return {
            "object_type": request.GET.get("object_type"),
            "object_id": request.GET.get("object_id"),
            "return_url": return_url,
        }


@register_model_view(models.DiagramAssignment, name="", detail=True)
class DiagramAssignmentView(generic.ObjectView):
    queryset = models.DiagramAssignment.objects.select_related("diagram", "object_type").prefetch_related("tags")


@register_model_view(models.DiagramAssignment, name="list", path="", detail=False)
class DiagramAssignmentListView(generic.ObjectListView):
    queryset = models.DiagramAssignment.objects.select_related("diagram", "object_type").prefetch_related("tags")
    table = tables.DiagramAssignmentTable
    filterset = filtersets.DiagramAssignmentFilterSet
    filterset_form = forms.DiagramAssignmentFilterForm
    actions = {
        "export": set(),
        "bulk_edit": {"change"},
        "bulk_delete": {"delete"},
    }


@register_model_view(models.DiagramAssignment, name="edit", detail=True)
class DiagramAssignmentEditView(generic.ObjectEditView):
    queryset = models.DiagramAssignment.objects.all()
    form = forms.DiagramAssignmentForm


@register_model_view(models.DiagramAssignment, "bulk_edit", path="edit", detail=False)
class DiagramAssignmentBulkEditView(generic.BulkEditView):
    queryset = models.DiagramAssignment.objects.all()
    filterset = filtersets.DiagramAssignmentFilterSet
    table = tables.DiagramAssignmentTable
    form = forms.DiagramAssignmentBulkEditForm


@register_model_view(models.DiagramAssignment, "bulk_delete", path="delete", detail=False)
class DiagramAssignmentBulkDeleteView(generic.BulkDeleteView):
    queryset = models.DiagramAssignment.objects.all()
    filterset = filtersets.DiagramAssignmentFilterSet
    table = tables.DiagramAssignmentTable
    default_return_url = "plugins:netbox_drawio:diagramassignment_list"


@register_model_view(models.DiagramAssignment, name="delete", detail=True)
class DiagramAssignmentDeleteView(generic.ObjectDeleteView):
    """
    Unlinks a diagram assignment from an object.
    The diagram itself is preserved and can be re-linked to other objects.
    """

    queryset = models.DiagramAssignment.objects.all()
    default_return_url = "plugins:netbox_drawio:diagramassignment_list"
