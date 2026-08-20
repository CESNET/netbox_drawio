from unittest import mock

from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from utilities.testing import create_test_device

from netbox_drawio import signals as drawio_signals
from netbox_drawio.models import Diagram, DiagramAssignment
from netbox_drawio.tests.utils import SAMPLE_XML, assign, make_diagram


class DiagramModelTest(TestCase):
    def test_str_and_absolute_url(self):
        diagram = make_diagram("Topology A")
        self.assertEqual(str(diagram), "Topology A")
        self.assertEqual(diagram.get_absolute_url(), f"/plugins/drawio/diagrams/{diagram.pk}/")

    def test_content_hash_maintained_on_save(self):
        diagram = make_diagram("Hash", source_xml=SAMPLE_XML)
        self.assertEqual(len(diagram.content_hash), 64)
        original_hash = diagram.content_hash

        diagram.source_xml = SAMPLE_XML.replace("Page-1", "Page-2")
        diagram.save()
        self.assertNotEqual(diagram.content_hash, original_hash)

        diagram.source_xml = ""
        diagram.save()
        self.assertEqual(diagram.content_hash, "")

    def test_serialize_object_excludes_blobs(self):
        diagram = make_diagram("Serialized")
        data = diagram.serialize_object()
        self.assertNotIn("source_xml", data)
        self.assertNotIn("svg_cache", data)
        self.assertIn("content_hash", data)
        self.assertIn("name", data)

    def test_snapshot_excludes_blobs(self):
        diagram = make_diagram("Snapshot")
        diagram.snapshot()
        self.assertNotIn("source_xml", diagram._prechange_snapshot)
        self.assertNotIn("svg_cache", diagram._prechange_snapshot)


class DiagramAssignmentModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.device = create_test_device("drawio-test-device-1")
        cls.diagram = make_diagram("Assigned")

    def test_parent_resolution(self):
        assignment = assign(self.diagram, self.device)
        self.assertEqual(assignment.parent, self.device)

    def test_parent_none_for_missing_object(self):
        assignment = assign(self.diagram, self.device)
        # Bypass the cleanup receiver by pointing at a nonexistent id
        assignment.object_id = 999999999
        self.assertIsNone(assignment.parent)

    def test_unique_constraint(self):
        assign(self.diagram, self.device)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                assign(self.diagram, self.device)

    def test_orphan_cleanup_on_object_delete(self):
        device = create_test_device("drawio-test-device-2")
        assignment = assign(self.diagram, device)
        device.delete()
        self.assertFalse(DiagramAssignment.objects.filter(pk=assignment.pk).exists())
        # The diagram itself survives
        self.assertTrue(Diagram.objects.filter(pk=self.diagram.pk).exists())

    def test_pre_delete_skips_plugin_table_when_absent(self):
        """
        During `manage.py migrate`, another app's data migration may delete rows before
        the assignment table exists. The receiver must not touch the table at all —
        on PostgreSQL a failed statement poisons the surrounding transaction.
        """
        device = create_test_device("drawio-guard-device")
        table = DiagramAssignment._meta.db_table
        drawio_signals._assignment_table_ready = None
        try:
            with mock.patch.object(connection.introspection, "table_names", return_value=[]):
                with CaptureQueriesContext(connection) as ctx:
                    device.delete()
        finally:
            drawio_signals._assignment_table_ready = None
        self.assertFalse(any(table in query["sql"] for query in ctx.captured_queries))

    def test_post_migrate_resets_table_cache(self):
        drawio_signals._assignment_table_ready = False
        try:
            drawio_signals.reset_assignment_table_cache(sender=None)
            self.assertIsNone(drawio_signals._assignment_table_ready)
        finally:
            drawio_signals._assignment_table_ready = None

    def test_diagram_delete_cascades_assignments(self):
        diagram = make_diagram("Cascade")
        assignment = assign(diagram, self.device)
        diagram.delete()
        self.assertFalse(DiagramAssignment.objects.filter(pk=assignment.pk).exists())
        # The device is untouched
        self.assertTrue(type(self.device).objects.filter(pk=self.device.pk).exists())
