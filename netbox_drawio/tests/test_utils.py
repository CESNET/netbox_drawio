from django.test import SimpleTestCase

from netbox_drawio.utils import get_embed_origin


class GetEmbedOriginTest(SimpleTestCase):
    def test_normalization_table(self):
        cases = [
            # (embed_url, expected origin)
            ("https://embed.diagrams.net/?embed=1", "https://embed.diagrams.net"),
            ("https://Drawio.example.com/", "https://drawio.example.com"),
            ("HTTPS://DRAWIO.EXAMPLE.COM/", "https://drawio.example.com"),
            ("https://drawio.example.com:443/", "https://drawio.example.com"),
            ("http://drawio.example.com:80/", "http://drawio.example.com"),
            ("https://drawio.example.com:80/", "https://drawio.example.com:80"),
            ("http://drawio.example.com:8080/path?x=1", "http://drawio.example.com:8080"),
            ("https://drawio.example.com/some/path/", "https://drawio.example.com"),
            ("https://[2001:db8::1]:8443/", "https://[2001:db8::1]:8443"),
            ("https://[2001:db8::1]:443/", "https://[2001:db8::1]"),
            # Malformed / unusable values -> None
            ("", None),
            ("?embed=1&proto=json", None),
            ("/drawio/", None),
            ("drawio.example.com", None),
            ("ftp://drawio.example.com/", None),
            ("https://", None),
            ("https://drawio.example.com:notaport/", None),
        ]
        for embed_url, expected in cases:
            with self.subTest(embed_url=embed_url):
                self.assertEqual(get_embed_origin(embed_url), expected)
