"""Django system checks.

The embedded editor fails silently in the browser when its configuration is
unusable: a `drawio_base_url` whose origin never matches `event.origin` drops
every postMessage (the editor spins forever), and Django's
`DATA_UPLOAD_MAX_MEMORY_SIZE` can reject save bodies long before the plugin's
own `max_size` does. Both are legal-looking configs, so warn at startup
instead. Check IDs are a published contract (README, users'
SILENCED_SYSTEM_CHECKS): never renumber or reuse one.
"""

from django.conf import settings
from django.core.checks import Warning, register

from netbox_drawio.constants import SAVE_BODY_BUDGET_FACTOR
from netbox_drawio.utils import get_embed_origin, get_setting


@register()
def check_drawio_base_url(app_configs, **kwargs):
    """Warn when drawio_base_url cannot yield a usable postMessage origin."""
    base_url = str(get_setting("drawio_base_url") or "").strip()
    if get_embed_origin(base_url) is not None:
        return []
    return [
        Warning(
            f"netbox-drawio: 'drawio_base_url' ({base_url!r}) is not an absolute http(s) URL. "
            "The editor iframe will ignore every postMessage and never load or save.",
            hint="Set PLUGINS_CONFIG['netbox_drawio']['drawio_base_url'] to an absolute URL, "
            "e.g. 'https://embed.diagrams.net/'.",
            id="netbox_drawio.W001",
        )
    ]


@register()
def check_max_size_reachable(app_configs, **kwargs):
    """Warn when the effective max_size is unreachable under Django's body-size cap.

    Fires on stock installs too: NetBox defaults DATA_UPLOAD_MAX_MEMORY_SIZE to
    2.5 MB, which makes the plugin's advertised 10 MB cap unreachable until the
    operator raises one or lowers the other.
    """
    upload_limit = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
    if upload_limit is None:
        return []

    try:
        max_size = int(get_setting("max_size"))
    except (TypeError, ValueError):
        # A garbage max_size crashes the save view, not startup — not this check's problem.
        return []

    if max_size * SAVE_BODY_BUDGET_FACTOR <= upload_limit:
        return []

    return [
        Warning(
            f"netbox-drawio: 'max_size' ({max_size} bytes) is unreachable — Django's "
            f"DATA_UPLOAD_MAX_MEMORY_SIZE ({upload_limit} bytes) rejects save requests first. "
            f"Diagrams well under max_size will fail to save with a 413.",
            hint=f"Set DATA_UPLOAD_MAX_MEMORY_SIZE to at least {SAVE_BODY_BUDGET_FACTOR}x max_size "
            f"({max_size * SAVE_BODY_BUDGET_FACTOR}) in the NetBox configuration, or lower max_size.",
            id="netbox_drawio.W002",
        )
    ]
