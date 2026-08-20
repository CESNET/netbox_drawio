from core.models.object_types import ObjectType
from django.test import override_settings
from rest_framework import status
from users.models import ObjectPermission
from utilities.testing import APITestCase, APIViewTestCases, create_test_device

from netbox_drawio.models import Diagram, DiagramAssignment
from netbox_drawio.tests.utils import SAMPLE_XML, assign, make_diagram, mutate_svg


class AppTest(APITestCase):
    def test_root(self):
        response = self.client.get("/api/plugins/drawio/", **self.header)
        self.assertEqual(response.status_code, 200)


class DiagramAPITest(
    APIViewTestCases.GetObjectViewTestCase,
    APIViewTestCases.ListObjectsViewTestCase,
    APIViewTestCases.CreateObjectViewTestCase,
    APIViewTestCases.UpdateObjectViewTestCase,
    APIViewTestCases.DeleteObjectViewTestCase,
):
    model = Diagram
    view_namespace = "plugins-api:netbox_drawio"
    brief_fields = ["description", "display", "id", "name", "url"]

    create_data = [
        {"name": "API Diagram 1", "source_xml": SAMPLE_XML},
        {"name": "API Diagram 2", "description": "second"},
        {"name": "API Diagram 3"},
    ]
    bulk_update_data = {
        "description": "Bulk updated",
    }

    @classmethod
    def setUpTestData(cls):
        make_diagram("Existing Diagram 1")
        make_diagram("Existing Diagram 2")
        make_diagram("Existing Diagram 3")

    def test_svg_only_patch_changes_hash_and_creates_objectchange(self):
        from core.models import ObjectChange

        diagram = Diagram.objects.get(name="Existing Diagram 1")
        original_hash = diagram.content_hash
        self.add_permissions("netbox_drawio.change_diagram")
        response = self.client.patch(
            self._get_detail_url(diagram),
            {"svg_cache": mutate_svg(diagram)},
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        diagram.refresh_from_db()
        self.assertNotEqual(diagram.content_hash, original_hash)

        oc = ObjectChange.objects.filter(changed_object_id=diagram.pk).order_by("-time").first()
        self.assertIsNotNone(oc)
        self.assertEqual(oc.postchange_data.get("content_hash"), diagram.content_hash)
        self.assertNotIn("svg_cache", oc.postchange_data)

    @override_settings(PLUGINS_CONFIG={"netbox_drawio": {"max_size": 50}})
    def test_oversize_source_xml_rejected(self):
        self.add_permissions("netbox_drawio.add_diagram")
        response = self.client.post(
            self._get_list_url(),
            {"name": "Too big", "source_xml": SAMPLE_XML},
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DiagramAssignmentAPITest(
    APIViewTestCases.GetObjectViewTestCase,
    APIViewTestCases.ListObjectsViewTestCase,
    APIViewTestCases.CreateObjectViewTestCase,
    APIViewTestCases.DeleteObjectViewTestCase,
):
    model = DiagramAssignment
    view_namespace = "plugins-api:netbox_drawio"
    brief_fields = ["display", "id", "object_id", "object_type", "url"]

    @classmethod
    def setUpTestData(cls):
        cls.devices = [
            create_test_device("drawio-api-device-1"),
            create_test_device("drawio-api-device-2"),
            create_test_device("drawio-api-device-3"),
        ]
        cls.diagram = make_diagram("API Assignment Diagram")
        other = make_diagram("API Assignment Diagram 2")
        assign(other, cls.devices[0])
        assign(other, cls.devices[1])
        assign(other, cls.devices[2])

        cls.create_data = [
            {"diagram": cls.diagram.pk, "object_type": "dcim.device", "object_id": cls.devices[0].pk},
            {"diagram": cls.diagram.pk, "object_type": "dcim.device", "object_id": cls.devices[1].pk},
            {"diagram": cls.diagram.pk, "object_type": "dcim.device", "object_id": cls.devices[2].pk},
        ]

    def setUp(self):
        super().setUp()
        # The stock create tests grant only add_diagramassignment; the serializer's
        # restricted querysets additionally require view on the diagram and the target.
        self.add_permissions("netbox_drawio.view_diagram", "dcim.view_device")

    def _add_constrained_permission(self, model, action, constraints):
        obj_perm = ObjectPermission(name=f"Constrained {action}", actions=[action], constraints=constraints)
        obj_perm.save()
        obj_perm.users.add(self.user)
        obj_perm.object_types.add(ObjectType.objects.get_for_model(model))

    def test_cannot_assign_non_viewable_diagram(self):
        self.remove_permissions("netbox_drawio.view_diagram")
        self.add_permissions("netbox_drawio.add_diagramassignment")
        self._add_constrained_permission(Diagram, "view", {"name": "API Assignment Diagram 2"})
        response = self.client.post(
            self._get_list_url(),
            {"diagram": self.diagram.pk, "object_type": "dcim.device", "object_id": self.devices[0].pk},
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("diagram", response.data)

    def test_forbidden_and_missing_parent_indistinguishable(self):
        self.remove_permissions("dcim.view_device")
        self.add_permissions("netbox_drawio.add_diagramassignment")

        def post(object_id):
            return self.client.post(
                self._get_list_url(),
                {"diagram": self.diagram.pk, "object_type": "dcim.device", "object_id": object_id},
                format="json",
                **self.header,
            )

        forbidden = post(self.devices[0].pk)
        missing = post(999999999)
        self.assertEqual(forbidden.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        # An existing-but-forbidden pk must be indistinguishable from a missing one
        self.assertEqual(
            str(forbidden.data).replace(str(self.devices[0].pk), "<pk>"),
            str(missing.data).replace("999999999", "<pk>"),
        )

    def test_parent_hidden_without_view_permission(self):
        self.remove_permissions("dcim.view_device")
        self.add_permissions("netbox_drawio.view_diagramassignment")
        assignment = DiagramAssignment.objects.first()
        response = self.client.get(self._get_detail_url(assignment), **self.header)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["parent"])

    def test_out_of_scope_object_type_rejected(self):
        from extras.models import Tag

        tag = Tag.objects.create(name="APIScopeTag", slug="apiscopetag")
        self.add_permissions("netbox_drawio.add_diagramassignment", "netbox_drawio.view_diagram")
        response = self.client.post(
            self._get_list_url(),
            {"diagram": self.diagram.pk, "object_type": "extras.tag", "object_id": tag.pk},
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("object_type", response.data)

    def test_nonexistent_parent_rejected(self):
        self.add_permissions("netbox_drawio.add_diagramassignment", "netbox_drawio.view_diagram")
        response = self.client.post(
            self._get_list_url(),
            {"diagram": self.diagram.pk, "object_type": "dcim.device", "object_id": 999999999},
            format="json",
            **self.header,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_parent_nested_representation(self):
        self.add_permissions("netbox_drawio.view_diagramassignment")
        assignment = DiagramAssignment.objects.first()
        url = self._get_detail_url(assignment)
        response = self.client.get(url, **self.header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["parent"]["id"], assignment.object_id)
        self.assertIn("url", response.data["parent"])
