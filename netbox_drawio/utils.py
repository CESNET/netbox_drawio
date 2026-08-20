import base64
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from netbox_drawio.constants import FORCED_EMBED_PARAMS, HARD_EXCLUDED_APPS, SVG_DATA_URI_PREFIX


def _get_plugin_settings():
    try:
        plugins_config = getattr(settings, "PLUGINS_CONFIG", {})
    except (AttributeError, ImproperlyConfigured):
        return {}

    if not isinstance(plugins_config, dict):
        return {}

    plugin_settings = plugins_config.get("netbox_drawio", {})
    if not isinstance(plugin_settings, dict):
        return {}

    return plugin_settings


def get_setting(key):
    """Read a plugin setting, falling back to the PluginConfig default."""
    from netbox_drawio import NetBoxDrawioConfig

    plugin_settings = _get_plugin_settings()
    if key in plugin_settings:
        return plugin_settings[key]
    return NetBoxDrawioConfig.default_settings.get(key)


def _as_list(value):
    if value is None or not isinstance(value, (list, tuple, set)):
        return []
    return list(value)


def validate_object_type(model):
    """
    Whether the model is in scope for diagrams (Diagrams tab + assignment targets).

    Two layers:
      1. Deny: HARD_EXCLUDED_APPS, the excluded_apps setting (app_label) and the
         excluded_models setting (app_label.model_name) always lose.
      2. Allow: an empty scope_filter puts every remaining model in scope. A non-empty
         scope_filter narrows with netbox-attachments semantics: applied_scope="app"
         matches app labels only; applied_scope="model" matches a bare app label
         ("dcim" = whole app) or an exact "dcim.device".
    """
    app_label = model._meta.app_label
    label_lower = model._meta.label_lower

    # Deny layer — cheap string checks only
    if app_label in HARD_EXCLUDED_APPS:
        return False
    if app_label in _as_list(get_setting("excluded_apps")):
        return False
    if label_lower in _as_list(get_setting("excluded_models")):
        return False

    # Allow layer
    scope_filter = _as_list(get_setting("scope_filter"))
    if not scope_filter:
        return True

    applied_scope = get_setting("applied_scope")
    if applied_scope not in ("app", "model"):
        applied_scope = "model"

    if applied_scope == "app":
        return app_label in scope_filter
    # "model": a bare app label enables the whole app, an exact label one model
    return app_label in scope_filter or label_lower in scope_filter


def get_enabled_object_type_queryset():
    """
    ObjectType queryset limited to models in scope, for the link form's picker.
    """
    from functools import reduce
    from operator import or_

    from core.models.object_types import ObjectType
    from django.apps import apps
    from django.db.models import Q

    q_filters = []
    seen = set()

    for model in apps.get_models():
        key = model._meta.label_lower
        if key in seen:
            continue
        seen.add(key)
        if model._meta.proxy:
            continue
        if validate_object_type(model):
            q_filters.append(Q(app_label=model._meta.app_label, model=model._meta.model_name))

    if not q_filters:
        return ObjectType.objects.none()

    return ObjectType.objects.filter(reduce(or_, q_filters))


def build_embed_url():
    """
    Build the draw.io embed iframe URL: drawio_base_url + drawio_url_params, with the
    embed-protocol params always forced on top.
    """
    base_url = str(get_setting("drawio_base_url") or "").strip()
    extra_params = get_setting("drawio_url_params")
    if not isinstance(extra_params, dict):
        extra_params = {}

    params = {**{str(k): str(v) for k, v in extra_params.items()}, **FORCED_EMBED_PARAMS}
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(params)}"


def decode_svg_data_uri(data_uri):
    """
    Decode the "data:image/svg+xml;base64,..." URI posted by the editor into SVG text.
    Raises ValueError on anything that is not a base64 SVG data URI.
    """
    if not isinstance(data_uri, str) or not data_uri.startswith(SVG_DATA_URI_PREFIX):
        raise ValueError("Expected a base64-encoded SVG data URI")

    payload = data_uri[len(SVG_DATA_URI_PREFIX) :]
    try:
        svg = base64.b64decode(payload, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Malformed SVG data URI") from exc

    if "<svg" not in svg[:5000]:
        raise ValueError("Decoded payload does not look like SVG")

    return svg


def get_embed_origin(embed_url):
    """
    Browser-normalized origin of the draw.io embed URL, used as the postMessage
    origin allowlist: lowercase scheme and host, default ports dropped — matching
    what the browser reports in event.origin. Returns None for anything that is
    not an absolute http(s) URL, so callers can fail loudly instead of comparing
    against an origin that can never match.
    """
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(str(embed_url))
        hostname = parts.hostname
        port = parts.port  # raises ValueError on a non-numeric port
    except ValueError:
        return None

    scheme = parts.scheme.lower()
    if scheme not in ("http", "https") or not hostname:
        return None

    host = f"[{hostname}]" if ":" in hostname else hostname
    if port and port != {"http": 80, "https": 443}[scheme]:
        return f"{scheme}://{host}:{port}"
    return f"{scheme}://{host}"
