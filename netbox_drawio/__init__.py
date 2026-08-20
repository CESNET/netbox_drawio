try:
    from netbox.plugins import PluginConfig
except ModuleNotFoundError:

    class PluginConfig:  # type: ignore[no-redef]
        pass


from netbox_drawio.version import __version__

__author__ = "Jan Krupa"
__email__ = "jan.krupa@cesnet.cz"


class NetBoxDrawioConfig(PluginConfig):
    name = "netbox_drawio"
    verbose_name = "NetBox Draw.io"
    description = "Create draw.io diagrams and assign them to multiple NetBox objects"
    version = __version__
    author = __author__
    author_email = __email__
    base_url = "drawio"
    default_settings = {
        # Editor
        "drawio_base_url": "https://embed.diagrams.net/",
        # Extra query params merged onto the embed URL (ui, dark, libraries, lang, ...).
        # embed/proto/spin are always forced and cannot be overridden.
        "drawio_url_params": {},
        # Forward draw.io autosave events to the save endpoint (saves on every change)
        "autosave": False,
        # Scoping — which models get the Diagrams tab / may be assigned diagrams.
        # Deny layer: excluded_apps + excluded_models are never in scope.
        # Allow layer: empty scope_filter means every non-excluded model is in scope;
        # a non-empty scope_filter narrows further (netbox-attachments semantics).
        "applied_scope": "model",  # "app" | "model"
        "scope_filter": [],
        "excluded_apps": [
            "admin",
            "auth",
            "contenttypes",
            "sessions",
            "taggit",
            "social_django",
            "django_rq",
            "users",
            "core",
            "extras",
        ],
        "excluded_models": [],
        # Diagrams tab placement (Images=6000, Journal=9000)
        "tab_weight": 6500,
        "hide_empty_tab": False,
        # Byte cap applied to diagram XML and SVG each
        "max_size": 10 * 1024 * 1024,
    }
    required_settings = []
    min_version = "4.5.0"
    max_version = "4.6.99"

    def ready(self):
        super().ready()
        from netbox_drawio import signals  # noqa: F401


config = NetBoxDrawioConfig
