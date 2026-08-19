from netbox.api.routers import NetBoxRouter

from netbox_drawio.api import views

app_name = "netbox_drawio"
router = NetBoxRouter()
router.register("diagrams", views.DiagramViewSet)
router.register("diagram-assignments", views.DiagramAssignmentViewSet)

urlpatterns = router.urls
