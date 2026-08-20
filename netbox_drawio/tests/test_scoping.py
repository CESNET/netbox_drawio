from django.test import TestCase, override_settings

from netbox_drawio.utils import (
    build_embed_url,
    decode_svg_data_uri,
    get_enabled_object_type_queryset,
    validate_object_type,
)
from netbox_drawio.tests.utils import SAMPLE_SVG, sample_svg_data_uri


class ValidateObjectTypeTest(TestCase):
    def test_defaults(self):
        from dcim.models import Device, Site
        from extras.models import Tag
        from users.models import User

        from netbox_drawio.models import Diagram, DiagramAssignment

        # Everything real is in scope by default
        self.assertTrue(validate_object_type(Device))
        self.assertTrue(validate_object_type(Site))
        # Internals and own models are not
        self.assertFalse(validate_object_type(Tag))  # extras excluded
        self.assertFalse(validate_object_type(User))  # users excluded
        self.assertFalse(validate_object_type(Diagram))  # own app hard-excluded
        self.assertFalse(validate_object_type(DiagramAssignment))

    @override_settings(PLUGINS_CONFIG={"netbox_drawio": {"excluded_models": ["dcim.site"]}})
    def test_excluded_models(self):
        from dcim.models import Device, Site

        self.assertTrue(validate_object_type(Device))
        self.assertFalse(validate_object_type(Site))

    @override_settings(PLUGINS_CONFIG={"netbox_drawio": {"applied_scope": "app", "scope_filter": ["dcim"]}})
    def test_scope_filter_app_mode(self):
        from dcim.models import Device
        from ipam.models import Prefix

        self.assertTrue(validate_object_type(Device))
        self.assertFalse(validate_object_type(Prefix))

    @override_settings(
        PLUGINS_CONFIG={"netbox_drawio": {"applied_scope": "model", "scope_filter": ["ipam", "dcim.device"]}}
    )
    def test_scope_filter_model_mode(self):
        from dcim.models import Device, Site
        from ipam.models import Prefix

        self.assertTrue(validate_object_type(Device))  # exact model match
        self.assertTrue(validate_object_type(Prefix))  # whole-app match
        self.assertFalse(validate_object_type(Site))  # not listed

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_drawio": {
                "applied_scope": "app",
                "scope_filter": ["dcim"],
                "excluded_models": ["dcim.device"],
            }
        }
    )
    def test_excluded_beats_scope_filter(self):
        from dcim.models import Device, Site

        self.assertFalse(validate_object_type(Device))
        self.assertTrue(validate_object_type(Site))

    def test_enabled_object_type_queryset(self):
        object_types = get_enabled_object_type_queryset()
        labels = {f"{ot.app_label}.{ot.model}" for ot in object_types}
        self.assertIn("dcim.device", labels)
        self.assertNotIn("extras.tag", labels)
        self.assertNotIn("netbox_drawio.diagram", labels)


class EmbedUrlTest(TestCase):
    def test_default_embed_url(self):
        url = build_embed_url()
        self.assertTrue(url.startswith("https://embed.diagrams.net/?"))
        self.assertIn("embed=1", url)
        self.assertIn("proto=json", url)
        self.assertIn("spin=1", url)

    @override_settings(
        PLUGINS_CONFIG={
            "netbox_drawio": {
                "drawio_base_url": "https://drawio.example.com/",
                "drawio_url_params": {"ui": "min", "dark": "auto", "proto": "xml"},
            }
        }
    )
    def test_custom_url_params_and_forced_overrides(self):
        url = build_embed_url()
        self.assertTrue(url.startswith("https://drawio.example.com/?"))
        self.assertIn("ui=min", url)
        self.assertIn("dark=auto", url)
        # forced param wins over the operator's attempt to change the protocol
        self.assertIn("proto=json", url)
        self.assertNotIn("proto=xml", url)


class DecodeSvgTest(TestCase):
    def test_valid(self):
        self.assertEqual(decode_svg_data_uri(sample_svg_data_uri()), SAMPLE_SVG)

    def test_rejects_wrong_prefix(self):
        with self.assertRaises(ValueError):
            decode_svg_data_uri("data:image/png;base64,AAAA")

    def test_rejects_bad_base64(self):
        with self.assertRaises(ValueError):
            decode_svg_data_uri("data:image/svg+xml;base64,!!!not-base64!!!")

    def test_rejects_non_svg_payload(self):
        import base64

        payload = base64.b64encode(b"<html>nope</html>").decode()
        with self.assertRaises(ValueError):
            decode_svg_data_uri(f"data:image/svg+xml;base64,{payload}")
