from django.urls import include, path
from utilities.urls import get_model_urls

from netbox_drawio import views

urlpatterns = (
    path(
        "diagrams/",
        include(get_model_urls("netbox_drawio", "diagram", detail=False)),
    ),
    path(
        "diagrams/link/",
        views.DiagramLinkView.as_view(),
        name="diagram_link",
    ),
    path(
        "diagrams/<int:pk>/",
        include(get_model_urls("netbox_drawio", "diagram")),
    ),
    path(
        "diagram-assignments/",
        include(get_model_urls("netbox_drawio", "diagramassignment", detail=False)),
    ),
    path(
        "diagram-assignments/<int:pk>/",
        include(get_model_urls("netbox_drawio", "diagramassignment")),
    ),
)
