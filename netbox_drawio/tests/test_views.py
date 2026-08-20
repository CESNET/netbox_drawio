from core.models.object_types import ObjectType
from utilities.testing import ViewTestCases, create_test_device, create_tags
from utilities.testing.views import ModelViewTestCase

from netbox_drawio.models import Diagram, DiagramAssignment
from netbox_drawio.tests.utils import assign, make_diagram


class DiagramViewTestCase(
    ViewTestCases.GetObjectViewTestCase,
    ViewTestCases.GetObjectChangelogViewTestCase,
    ViewTestCases.CreateObjectViewTestCase,
    ViewTestCases.EditObjectViewTestCase,
    ViewTestCases.DeleteObjectViewTestCase,
    ViewTestCases.ListObjectsViewTestCase,
    ViewTestCases.BulkEditObjectsViewTestCase,
    ViewTestCases.BulkDeleteObjectsViewTestCase,
):
    model = Diagram

    def _get_base_url(self):
        return "plugins:netbox_drawio:diagram_{}"

    @classmethod
    def setUpTestData(cls):
        make_diagram("View Diagram 1")
        make_diagram("View Diagram 2")
        make_diagram("View Diagram 3")
        tags = create_tags("Alpha", "Bravo", "Charlie")

        cls.form_data = {
            "name": "View Diagram X",
            "description": "A new diagram",
            "comments": "created by test",
            "tags": [t.pk for t in tags],
        }
        cls.bulk_edit_data = {
            "description": "Bulk description",
        }


class DiagramAssignmentViewTestCase(
    ViewTestCases.GetObjectViewTestCase,
    ViewTestCases.GetObjectChangelogViewTestCase,
    ViewTestCases.DeleteObjectViewTestCase,
    ViewTestCases.ListObjectsViewTestCase,
    ViewTestCases.BulkDeleteObjectsViewTestCase,
):
    model = DiagramAssignment

    def _get_base_url(self):
        return "plugins:netbox_drawio:diagramassignment_{}"

    @classmethod
    def setUpTestData(cls):
        device1 = create_test_device("drawio-view-device-1")
        device2 = create_test_device("drawio-view-device-2")
        device3 = create_test_device("drawio-view-device-3")
        diagram = make_diagram("Assignment View Diagram")
        assign(diagram, device1)
        assign(diagram, device2)
        assign(diagram, device3)


class DiagramCreateWithAssignmentTest(ModelViewTestCase):
    """Custom flows: create-with-context, link form, diagrams tab."""

    model = Diagram

    def _get_base_url(self):
        return "plugins:netbox_drawio:diagram_{}"

    @classmethod
    def setUpTestData(cls):
        cls.device = create_test_device("drawio-flow-device-1")
        cls.device_ot = ObjectType.objects.get_for_model(cls.device)

    def test_create_with_object_context_creates_assignment(self):
        self.add_permissions("netbox_drawio.add_diagram", "dcim.view_device")
        url = self._get_url("add") + f"?object_type={self.device_ot.pk}&object_id={self.device.pk}"
        response = self.client.post(
            url,
            data={"name": "Context Diagram", "description": "", "comments": "", "tags": []},
        )
        self.assertHttpStatus(response, 302)
        diagram = Diagram.objects.get(name="Context Diagram")
        assignment = diagram.assignments.get()
        self.assertEqual(assignment.parent, self.device)

    def test_save_and_add_another_without_context(self):
        self.add_permissions("netbox_drawio.add_diagram")
        # "Save & Add Another" from the nav menu: no object context in GET
        response = self.client.post(
            self._get_url("add"),
            data={"name": "AddAnother 1", "description": "", "comments": "", "tags": [], "_addanother": ""},
        )
        self.assertHttpStatus(response, 302)
        redirect_url = response["Location"]
        # Absent GET params must not round-trip as the literal string "None"
        self.assertNotIn("None", redirect_url)
        # A plain Save from the re-presented form must not redirect to "/add/None";
        # with no return_url it lands on the new diagram's detail page
        response = self.client.post(
            redirect_url,
            data={"name": "AddAnother 2", "description": "", "comments": "", "tags": []},
        )
        self.assertHttpStatus(response, 302)
        diagram = Diagram.objects.get(name="AddAnother 2")
        self.assertEqual(response["Location"], diagram.get_absolute_url())

    def test_create_with_out_of_scope_object_type_rejected(self):
        self.add_permissions("netbox_drawio.add_diagram")
        # extras is excluded by default settings; Tag ObjectType must be refused
        from extras.models import Tag

        tag = Tag.objects.create(name="ScopeTag", slug="scopetag")
        tag_ot = ObjectType.objects.get_for_model(Tag)
        url = self._get_url("add") + f"?object_type={tag_ot.pk}&object_id={tag.pk}"
        response = self.client.post(
            url,
            data={"name": "Refused Diagram", "description": "", "comments": "", "tags": []},
        )
        self.assertHttpStatus(response, 404)
        self.assertFalse(Diagram.objects.filter(name="Refused Diagram").exists())

    def test_link_form_forward_flow(self):
        self.add_permissions("netbox_drawio.add_diagramassignment", "netbox_drawio.view_diagram", "dcim.view_device")
        diagram = make_diagram("Linkable")
        url = f"/plugins/drawio/diagrams/link/?object_type={self.device_ot.pk}&object_id={self.device.pk}"
        response = self.client.post(url, data={"diagram": diagram.pk, "tags": []})
        self.assertHttpStatus(response, 302)
        self.assertTrue(
            DiagramAssignment.objects.filter(
                diagram=diagram, object_type=self.device_ot, object_id=self.device.pk
            ).exists()
        )

    def test_link_form_duplicate_rejected(self):
        self.add_permissions("netbox_drawio.add_diagramassignment", "netbox_drawio.view_diagram", "dcim.view_device")
        diagram = make_diagram("Duplicate Link")
        assign(diagram, self.device)
        url = f"/plugins/drawio/diagrams/link/?object_type={self.device_ot.pk}&object_id={self.device.pk}"
        response = self.client.post(url, data={"diagram": diagram.pk, "tags": []})
        # Form error re-renders the page (200) without creating a second assignment
        self.assertHttpStatus(response, 200)
        self.assertEqual(diagram.assignments.count(), 1)

    def test_diagrams_tab_on_device(self):
        self.add_permissions("netbox_drawio.view_diagram", "dcim.view_device")
        diagram = make_diagram("Tab Diagram")
        assign(diagram, self.device)
        response = self.client.get(f"/dcim/devices/{self.device.pk}/diagrams/")
        self.assertHttpStatus(response, 200)
        self.assertIn(b"Tab Diagram", response.content)
