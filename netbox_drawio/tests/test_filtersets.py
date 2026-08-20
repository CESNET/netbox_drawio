from django.test import TestCase
from utilities.testing import create_test_device

from netbox_drawio.filtersets import DiagramAssignmentFilterSet, DiagramFilterSet
from netbox_drawio.models import Diagram, DiagramAssignment
from netbox_drawio.tests.utils import assign, make_diagram


class DiagramFilterSetTest(TestCase):
    queryset = Diagram.objects.all()

    @classmethod
    def setUpTestData(cls):
        cls.device1 = create_test_device("drawio-fs-device-1")
        cls.device2 = create_test_device("drawio-fs-device-2")
        cls.d1 = make_diagram("Alpha topology", description="north ring")
        cls.d2 = make_diagram("Beta topology", description="south ring")
        cls.d3 = make_diagram("Gamma", description="")
        cls.a1 = assign(cls.d1, cls.device1)
        cls.a2 = assign(cls.d1, cls.device2)
        cls.a3 = assign(cls.d2, cls.device2)

    def filter(self, params):
        return DiagramFilterSet(params, self.queryset).qs

    def test_q(self):
        self.assertEqual(self.filter({"q": "topology"}).count(), 2)
        self.assertEqual(self.filter({"q": "north"}).count(), 1)

    def test_name(self):
        # Exact-match semantics, consistent with core models
        self.assertEqual(self.filter({"name": ["Alpha topology"]}).count(), 1)
        self.assertEqual(self.filter({"name": ["alpha"]}).count(), 0)

    def test_name_ic(self):
        self.assertEqual(self.filter({"name__ic": ["alpha"]}).count(), 1)

    def test_created_gte(self):
        self.assertEqual(self.filter({"created__gte": ["2000-01-01T00:00:00"]}).count(), 3)
        self.assertEqual(self.filter({"created__gte": ["2999-01-01T00:00:00"]}).count(), 0)

    def test_object_type_id(self):
        object_type_id = self.a1.object_type_id
        # d1 + d2 assigned to devices; distinct so d1 not duplicated
        self.assertEqual(self.filter({"object_type_id": object_type_id}).count(), 2)

    def test_object_id(self):
        self.assertEqual(self.filter({"object_id": self.device2.pk}).count(), 2)
        self.assertEqual(self.filter({"object_id": self.device1.pk}).count(), 1)

    def test_has_assignments(self):
        self.assertEqual(self.filter({"has_assignments": True}).count(), 2)
        self.assertEqual(self.filter({"has_assignments": False}).count(), 1)


class DiagramAssignmentFilterSetTest(TestCase):
    queryset = DiagramAssignment.objects.all()

    @classmethod
    def setUpTestData(cls):
        cls.device1 = create_test_device("drawio-afs-device-1")
        cls.device2 = create_test_device("drawio-afs-device-2")
        cls.d1 = make_diagram("Assignment Alpha")
        cls.d2 = make_diagram("Assignment Beta")
        cls.a1 = assign(cls.d1, cls.device1)
        cls.a2 = assign(cls.d1, cls.device2)
        cls.a3 = assign(cls.d2, cls.device2)

    def filter(self, params):
        return DiagramAssignmentFilterSet(params, self.queryset).qs

    def test_diagram_id(self):
        self.assertEqual(self.filter({"diagram_id": [self.d1.pk]}).count(), 2)
        self.assertEqual(self.filter({"diagram_id": [self.d1.pk, self.d2.pk]}).count(), 3)

    def test_object_type_id(self):
        self.assertEqual(self.filter({"object_type_id": [self.a1.object_type_id]}).count(), 3)

    def test_object_id(self):
        self.assertEqual(self.filter({"object_id": self.device2.pk}).count(), 2)

    def test_q(self):
        self.assertEqual(self.filter({"q": "Alpha"}).count(), 2)
