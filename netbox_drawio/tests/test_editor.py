import json

from django.test import override_settings
from utilities.testing.views import ModelViewTestCase

from netbox_drawio.models import Diagram
from netbox_drawio.tests.utils import SAMPLE_SVG, SAMPLE_XML, make_diagram, sample_svg_data_uri


class DiagramEditorViewTest(ModelViewTestCase):
    model = Diagram

    def _get_base_url(self):
        return "plugins:netbox_drawio:diagram_{}"

    @classmethod
    def setUpTestData(cls):
        cls.diagram = make_diagram("Editor Diagram")

    def test_editor_requires_change_permission(self):
        self.add_permissions("netbox_drawio.view_diagram")
        response = self.client.get(self._get_url("editor", self.diagram))
        self.assertHttpStatus(response, 403)

    def test_editor_renders_with_change_permission(self):
        self.add_permissions("netbox_drawio.view_diagram", "netbox_drawio.change_diagram")
        response = self.client.get(self._get_url("editor", self.diagram))
        self.assertHttpStatus(response, 200)
        content = response.content.decode()
        self.assertIn("embed=1", content)
        self.assertIn("proto=json", content)
        self.assertIn("drawio-config", content)
        self.assertIn("embed.diagrams.net", content)

    def test_editor_rejects_offsite_return_url(self):
        self.add_permissions("netbox_drawio.view_diagram", "netbox_drawio.change_diagram")
        response = self.client.get(self._get_url("editor", self.diagram) + "?return_url=https://evil.example/x")
        self.assertHttpStatus(response, 200)
        self.assertNotIn(b"evil.example", response.content)


class DiagramSaveViewTest(ModelViewTestCase):
    model = Diagram

    def _get_base_url(self):
        return "plugins:netbox_drawio:diagram_{}"

    @classmethod
    def setUpTestData(cls):
        cls.diagram = make_diagram("Save Diagram", source_xml="", svg_cache="")

    def _save(self, payload, **kwargs):
        return self.client.post(
            self._get_url("save", self.diagram),
            data=json.dumps(payload),
            content_type="application/json",
            **kwargs,
        )

    def test_save_requires_change_permission(self):
        self.add_permissions("netbox_drawio.view_diagram")
        response = self._save({"xml": SAMPLE_XML})
        self.assertHttpStatus(response, 404)

    def test_save_happy_path(self):
        self.add_permissions("netbox_drawio.change_diagram")
        response = self._save({"xml": SAMPLE_XML, "svg_data_uri": sample_svg_data_uri()})
        self.assertHttpStatus(response, 200)
        self.diagram.refresh_from_db()
        self.assertEqual(self.diagram.source_xml, SAMPLE_XML)
        self.assertEqual(self.diagram.svg_cache, SAMPLE_SVG)
        self.assertEqual(len(self.diagram.content_hash), 64)

    def test_save_creates_blob_free_changelog(self):
        from core.models import ObjectChange

        self.add_permissions("netbox_drawio.change_diagram")
        response = self._save({"xml": SAMPLE_XML, "svg_data_uri": sample_svg_data_uri()})
        self.assertHttpStatus(response, 200)
        oc = ObjectChange.objects.filter(changed_object_id=self.diagram.pk).order_by("-time").first()
        self.assertIsNotNone(oc)
        self.assertNotIn("source_xml", oc.postchange_data)
        self.assertNotIn("svg_cache", oc.postchange_data)
        self.assertEqual(oc.postchange_data.get("content_hash"), Diagram.objects.get(pk=self.diagram.pk).content_hash)

    def test_save_rejects_invalid_json(self):
        self.add_permissions("netbox_drawio.change_diagram")
        response = self.client.post(
            self._get_url("save", self.diagram), data="{not json", content_type="application/json"
        )
        self.assertHttpStatus(response, 400)

    def test_save_rejects_non_drawio_payload(self):
        self.add_permissions("netbox_drawio.change_diagram")
        response = self._save({"xml": "<html>nope</html>"})
        self.assertHttpStatus(response, 400)

    def test_save_rejects_missing_xml(self):
        self.add_permissions("netbox_drawio.change_diagram")
        response = self._save({"svg_data_uri": sample_svg_data_uri()})
        self.assertHttpStatus(response, 400)

    def test_save_rejects_malformed_svg_uri(self):
        self.add_permissions("netbox_drawio.change_diagram")
        response = self._save({"xml": SAMPLE_XML, "svg_data_uri": "data:image/png;base64,xxxx"})
        self.assertHttpStatus(response, 400)

    @override_settings(PLUGINS_CONFIG={"netbox_drawio": {"max_size": 50}})
    def test_save_rejects_oversize_xml(self):
        self.add_permissions("netbox_drawio.change_diagram")
        response = self._save({"xml": SAMPLE_XML})
        self.assertHttpStatus(response, 413)

    def test_save_get_not_allowed(self):
        self.add_permissions("netbox_drawio.change_diagram")
        response = self.client.get(self._get_url("save", self.diagram))
        self.assertHttpStatus(response, 405)

    def test_save_enforces_csrf(self):
        from django.test import Client

        self.add_permissions("netbox_drawio.change_diagram")
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        response = csrf_client.post(
            self._get_url("save", self.diagram),
            data=json.dumps({"xml": SAMPLE_XML}),
            content_type="application/json",
        )
        self.assertHttpStatus(response, 403)


class DiagramSVGSourceViewTest(ModelViewTestCase):
    model = Diagram

    def _get_base_url(self):
        return "plugins:netbox_drawio:diagram_{}"

    @classmethod
    def setUpTestData(cls):
        cls.diagram = make_diagram("SVG Diagram")
        cls.empty = make_diagram("Empty Diagram", source_xml="", svg_cache="")

    def test_svg_requires_view_permission(self):
        response = self.client.get(self._get_url("svg", self.diagram))
        self.assertHttpStatus(response, 404)

    def test_svg_response_and_headers(self):
        self.add_permissions("netbox_drawio.view_diagram")
        response = self.client.get(self._get_url("svg", self.diagram))
        self.assertHttpStatus(response, 200)
        self.assertEqual(response["Content-Type"], "image/svg+xml; charset=utf-8")
        self.assertIn("default-src 'none'", response["Content-Security-Policy"])
        self.assertIn("sandbox", response["Content-Security-Policy"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("inline", response["Content-Disposition"])
        self.assertEqual(response.content.decode(), self.diagram.svg_cache)

    def test_svg_etag_304(self):
        self.add_permissions("netbox_drawio.view_diagram")
        first = self.client.get(self._get_url("svg", self.diagram))
        etag = first["ETag"]
        second = self.client.get(self._get_url("svg", self.diagram), HTTP_IF_NONE_MATCH=etag)
        self.assertHttpStatus(second, 304)

    def test_svg_404_when_empty(self):
        self.add_permissions("netbox_drawio.view_diagram")
        response = self.client.get(self._get_url("svg", self.empty))
        self.assertHttpStatus(response, 404)

    def test_source_download(self):
        self.add_permissions("netbox_drawio.view_diagram")
        response = self.client.get(self._get_url("source", self.diagram))
        self.assertHttpStatus(response, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".drawio", response["Content-Disposition"])
        self.assertEqual(response.content.decode(), self.diagram.source_xml)

    def test_source_404_when_empty(self):
        self.add_permissions("netbox_drawio.view_diagram")
        response = self.client.get(self._get_url("source", self.empty))
        self.assertHttpStatus(response, 404)
