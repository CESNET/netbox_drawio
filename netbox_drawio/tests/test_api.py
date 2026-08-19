from django.test import override_settings
from rest_framework import status
from utilities.testing import APITestCase, APIViewTestCases, create_test_device

from netbox_drawio.models import Diagram, DiagramAssignment
from netbox_drawio.tests.utils import SAMPLE_XML, assign, make_diagram


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
