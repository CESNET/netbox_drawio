# Apps that can never be in scope, regardless of settings (the plugin's own models
# must not carry a Diagrams tab; assigning a diagram to a diagram makes no sense).
HARD_EXCLUDED_APPS = ("netbox_drawio",)

# High-frequency Django internal apps skipped by the pre_delete cleanup receiver
PRE_DELETE_SKIPPED_APPS = ("sessions", "admin", "contenttypes", "auth", "taggit", "users", "migrations")

# Query params always forced onto the draw.io embed URL
FORCED_EMBED_PARAMS = {
    "embed": "1",
    "proto": "json",
    "spin": "1",
}

# Accepted data URI prefix for the SVG posted back by the editor
SVG_DATA_URI_PREFIX = "data:image/svg+xml;base64,"
