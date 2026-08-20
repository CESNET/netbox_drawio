import logging

from django.db.utils import OperationalError

from netbox_drawio.utils import get_setting, get_tab_unsupported_reason, validate_object_type

logger = logging.getLogger(__name__)


def register_diagrams_tab_view(model) -> str:
    from core.models.object_types import ObjectType
    from django.db.models.functions import Length
    from django.shortcuts import get_object_or_404, render
    from django.views.generic import View
    from netbox.context import current_request
    from utilities.views import ConditionalLoginRequiredMixin, ViewTab, get_default_template, register_model_view

    from netbox_drawio.models import Diagram, DiagramAssignment

    view_name = "diagrams"

    def assigned_diagram_count(obj):
        # Runs on every detail-page render (model_view_tabs) — must never break the page
        try:
            request = current_request.get()
            queryset = Diagram.objects.filter(
                assignments__object_type=ObjectType.objects.get_for_model(obj),
                assignments__object_id=obj.pk,
            )
            if request:
                queryset = queryset.restrict(request.user, "view")
            return queryset.distinct().count()
        except Exception as e:
            logger.debug(f"Diagrams tab badge failed for {obj!r}: {e}")
            return 0

    class DiagramsTabView(ConditionalLoginRequiredMixin, View):
        """Per-object Diagrams tab rendering SVG preview cards (Images-style)."""

        tab = ViewTab(
            label="Diagrams",
            badge=assigned_diagram_count,
            permission="netbox_drawio.view_diagram",
            weight=int(get_setting("tab_weight") or 6500),
            hide_if_empty=bool(get_setting("hide_empty_tab")),
        )

        def get(self, request, **kwargs):
            obj = get_object_or_404(model.objects.restrict(request.user, "view"), **kwargs)
            assignments = (
                DiagramAssignment.objects.filter(
                    object_type=ObjectType.objects.get_for_model(obj),
                    object_id=obj.pk,
                    diagram__in=Diagram.objects.restrict(request.user, "view"),
                )
                .select_related("diagram")
                .defer("diagram__source_xml", "diagram__svg_cache")
                .annotate(
                    svg_size=Length("diagram__svg_cache"),
                )
                .order_by("diagram__name")
            )
            return render(
                request,
                "netbox_drawio/tab_diagrams.html",
                {
                    "object": obj,
                    "assignments": assignments,
                    "base_template": get_default_template(model),
                    "tab": self.tab,
                },
            )

    register_model_view(model, name=view_name, path=view_name)(DiagramsTabView)
    return view_name


def get_template_extensions():
    """
    Register a Diagrams tab for every in-scope model at startup.

    Returns an empty extension list — the tab views register as a side effect
    (PluginTemplateExtensions are not used in v1).
    """
    try:
        from django.apps import apps
    except Exception:
        return []

    try:
        seen_models = set()
        for model in apps.get_models():
            model_id = model._meta.label_lower
            if model_id in seen_models:
                continue
            seen_models.add(model_id)

            if model._meta.proxy:
                continue

            if not validate_object_type(model):
                continue

            unsupported = get_tab_unsupported_reason(model)
            if unsupported:
                logger.debug(f"Skipping Diagrams tab for {model_id}: {unsupported}")
                continue

            register_diagrams_tab_view(model)

    except OperationalError:
        logger.error("Database is not ready, skipping Diagrams tab setup")
    except Exception as e:
        logger.error("Unexpected error in Diagrams tab setup")
        logger.debug(f"Error details: {str(e)}", exc_info=True)

    return []


template_extensions = get_template_extensions()
