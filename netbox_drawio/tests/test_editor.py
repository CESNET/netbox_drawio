import json

from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from utilities.testing.views import ModelViewTestCase

from netbox_drawio.models import Diagram
from netbox_drawio.tests.utils import SAMPLE_SVG, SAMPLE_XML, make_diagram, mutate_svg, sample_svg_data_uri


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

    @override_settings(PLUGINS_CONFIG={"netbox_drawio": {"drawio_base_url": "https://EMBED.diagrams.net:443/"}})
    def test_editor_normalizes_embed_origin(self):
        self.add_permissions("netbox_drawio.view_diagram", "netbox_drawio.change_diagram")
        response = self.client.get(self._get_url("editor", self.diagram))
        self.assertHttpStatus(response, 200)
        self.assertEqual(response.context["drawio_config"]["embedOrigin"], "https://embed.diagrams.net")

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

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=200)
    def test_save_body_over_django_limit_returns_actionable_413(self):
        self.add_permissions("netbox_drawio.change_diagram")
        response = self._save({"xml": SAMPLE_XML, "padding": "x" * 500})
        self.assertHttpStatus(response, 413)
        self.assertIn("DATA_UPLOAD_MAX_MEMORY_SIZE", response.json()["error"])

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

    def test_svg_etag_changes_on_svg_only_update(self):
        self.add_permissions("netbox_drawio.view_diagram")
        first = self.client.get(self._get_url("svg", self.diagram))
        etag = first["ETag"]

        diagram = Diagram.objects.get(pk=self.diagram.pk)
        diagram.svg_cache = mutate_svg(diagram)
        diagram.save()

        second = self.client.get(self._get_url("svg", self.diagram), HTTP_IF_NONE_MATCH=etag)
        self.assertHttpStatus(second, 200)
        self.assertNotEqual(second["ETag"], etag)

    def test_svg_etag_weak_if_none_match(self):
        self.add_permissions("netbox_drawio.view_diagram")
        etag = self.client.get(self._get_url("svg", self.diagram))["ETag"]
        response = self.client.get(self._get_url("svg", self.diagram), HTTP_IF_NONE_MATCH=f"W/{etag}")
        self.assertHttpStatus(response, 304)

    def test_svg_etag_multivalue_if_none_match(self):
        self.add_permissions("netbox_drawio.view_diagram")
        etag = self.client.get(self._get_url("svg", self.diagram))["ETag"]
        response = self.client.get(
            self._get_url("svg", self.diagram),
            HTTP_IF_NONE_MATCH=f'"stale-tag", {etag}, W/"other-tag"',
        )
        self.assertHttpStatus(response, 304)

    def test_svg_etag_star_if_none_match(self):
        self.add_permissions("netbox_drawio.view_diagram")
        response = self.client.get(self._get_url("svg", self.diagram), HTTP_IF_NONE_MATCH="*")
        self.assertHttpStatus(response, 304)

    def test_svg_etag_non_matching_multivalue_returns_200(self):
        self.add_permissions("netbox_drawio.view_diagram")
        self.client.get(self._get_url("svg", self.diagram))
        response = self.client.get(
            self._get_url("svg", self.diagram),
            HTTP_IF_NONE_MATCH='"stale-tag", W/"other-tag"',
        )
        self.assertHttpStatus(response, 200)

    def test_svg_versioned_url_is_immutable(self):
        self.add_permissions("netbox_drawio.view_diagram")
        url = self._get_url("svg", self.diagram) + f"?v={self.diagram.content_hash}"
        response = self.client.get(url)
        self.assertHttpStatus(response, 200)
        self.assertEqual(response["Cache-Control"], "private, max-age=31536000, immutable")

        not_modified = self.client.get(url, HTTP_IF_NONE_MATCH=response["ETag"])
        self.assertHttpStatus(not_modified, 304)
        self.assertEqual(not_modified["Cache-Control"], "private, max-age=31536000, immutable")
        self.assertEqual(not_modified["ETag"], response["ETag"])

    def test_svg_unversioned_or_stale_url_revalidates(self):
        self.add_permissions("netbox_drawio.view_diagram")
        url = self._get_url("svg", self.diagram)
        for query in ("", "?v=", "?v=stale"):
            with self.subTest(query=query):
                response = self.client.get(url + query)
                self.assertHttpStatus(response, 200)
                self.assertEqual(response["Cache-Control"], "private, no-cache")

    def test_svg_304_skips_blob_query(self):
        self.add_permissions("netbox_drawio.view_diagram")
        url = self._get_url("svg", self.diagram)
        etag = self.client.get(url)["ETag"]
        with CaptureQueriesContext(connection) as full:
            self.assertHttpStatus(self.client.get(url), 200)
        with CaptureQueriesContext(connection) as conditional:
            self.assertHttpStatus(self.client.get(url, HTTP_IF_NONE_MATCH=etag), 304)
        self.assertEqual(len(conditional), len(full) - 1)
        self.assertFalse(any("svg_cache" in q["sql"] for q in conditional.captured_queries))

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
