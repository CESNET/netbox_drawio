from django.test import SimpleTestCase, override_settings

from netbox_drawio.checks import check_drawio_base_url, check_max_size_reachable


class DrawioBaseUrlCheckTest(SimpleTestCase):
    def test_default_config_passes(self):
        self.assertEqual(check_drawio_base_url(None), [])

    @override_settings(PLUGINS_CONFIG={"netbox_drawio": {"drawio_base_url": "https://Drawio.example.com:443/"}})
    def test_normalizable_url_passes(self):
        self.assertEqual(check_drawio_base_url(None), [])

    @override_settings(PLUGINS_CONFIG={"netbox_drawio": {"drawio_base_url": "/drawio/"}})
    def test_relative_url_warns(self):
        warnings = check_drawio_base_url(None)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].id, "netbox_drawio.W001")
        self.assertIn("drawio_base_url", warnings[0].msg)

    @override_settings(PLUGINS_CONFIG={"netbox_drawio": {"drawio_base_url": ""}})
    def test_empty_url_warns(self):
        warnings = check_drawio_base_url(None)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].id, "netbox_drawio.W001")


class MaxSizeReachableCheckTest(SimpleTestCase):
    @override_settings(
        DATA_UPLOAD_MAX_MEMORY_SIZE=2621440,
        PLUGINS_CONFIG={"netbox_drawio": {"max_size": 10 * 1024 * 1024}},
    )
    def test_unreachable_max_size_warns(self):
        warnings = check_max_size_reachable(None)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].id, "netbox_drawio.W002")
        self.assertIn("DATA_UPLOAD_MAX_MEMORY_SIZE", warnings[0].msg)

    @override_settings(
        DATA_UPLOAD_MAX_MEMORY_SIZE=64 * 1024 * 1024,
        PLUGINS_CONFIG={"netbox_drawio": {"max_size": 10 * 1024 * 1024}},
    )
    def test_reachable_max_size_passes(self):
        self.assertEqual(check_max_size_reachable(None), [])

    @override_settings(
        DATA_UPLOAD_MAX_MEMORY_SIZE=None,
        PLUGINS_CONFIG={"netbox_drawio": {"max_size": 10 * 1024 * 1024}},
    )
    def test_unlimited_upload_size_passes(self):
        self.assertEqual(check_max_size_reachable(None), [])
