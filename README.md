# netbox-drawio

NetBox plugin for creating [draw.io](https://www.drawio.com/) diagrams directly in NetBox and
assigning them to **multiple** NetBox objects (Devices, Sites, Circuits, …).

A topology diagram usually touches many objects — unlike a per-object attachment, one Diagram
here can be linked to every Device and Site it depicts.

## Features

- **Embedded draw.io editor** — edit diagrams in an iframe using the draw.io embed protocol.
  Diagram XML travels only between your browser and NetBox; the editor host never receives it.
- **Diagrams tab** on object detail pages (like the Images feature) with SVG preview cards,
  per-card *edit* and *unlink* actions, and *Add Diagram* / *Link Existing* buttons.
- **Many-to-many assignment** — link one diagram to any number of objects of any enabled type.
- **SVG previews** served from a hardened endpoint (CSP, `sandbox`, `nosniff`; rendered via
  `<img>` so embedded scripts can never execute).
- **`.drawio` source download**, REST API for diagrams and assignments, global search,
  change logging (content blobs are excluded; a `content_hash` records every content change),
  tags, custom fields, journaling, and object permissions.

## Compatibility

| NetBox | Plugin |
|--------|--------|
| 4.5.x – 4.6.x | ≥ 0.1.0 |

Python ≥ 3.12.

## Installation

```bash
pip install netbox-drawio       # or: pip install -e /opt/drawio-netbox-plugin
```

`configuration.py`:

```python
PLUGINS = [
    # ...
    "netbox_drawio",
]
```

```bash
python manage.py migrate netbox_drawio
python manage.py collectstatic --no-input
# restart NetBox services
```

## Configuration

All settings are optional (`PLUGINS_CONFIG["netbox_drawio"] = {...}`):

| Setting | Default | Description |
|---------|---------|-------------|
| `drawio_base_url` | `https://embed.diagrams.net/` | Editor URL loaded in the iframe. Point it at a self-hosted draw.io for offline/private setups. Also used as the `postMessage` origin allowlist, so it must be an absolute `http(s)` URL (a system check warns otherwise, `netbox_drawio.W001`). |
| `drawio_url_params` | `{}` | Extra query params for the embed URL (`ui`, `dark`, `libraries`, `lang`, …). `embed`, `proto` and `spin` are always forced. |
| `autosave` | `False` | Persist draw.io autosave events (save on every change instead of explicit Save). |
| `applied_scope` | `model` | `app` or `model` — how `scope_filter` entries are interpreted (netbox-attachments semantics). |
| `scope_filter` | `[]` | Empty = every non-excluded model gets the Diagrams tab. Non-empty = allow-list, e.g. `["dcim", "circuits.circuit"]`. |
| `excluded_apps` | Django/NetBox internals (`auth`, `core`, `extras`, `users`, …) | Deny-list of app labels; always wins. |
| `excluded_models` | `[]` | Deny-list of `app.model` labels; always wins. |
| `tab_weight` | `6500` | Diagrams tab position (Images = 6000, Journal = 9000). |
| `hide_empty_tab` | `False` | Hide the tab when the object has no diagrams. |
| `max_size` | `10485760` | Max size in bytes for diagram XML and SVG, each. Django's `DATA_UPLOAD_MAX_MEMORY_SIZE` (2.5 MB by default) also caps the save request body — raise it to at least 3× `max_size` in the NetBox configuration or saves fail with a 413 well below this limit (a system check warns when `max_size` is unreachable, `netbox_drawio.W002`). |

### Self-hosted draw.io

```python
PLUGINS_CONFIG = {
    "netbox_drawio": {
        "drawio_base_url": "https://drawio.example.com/",
        "drawio_url_params": {"ui": "min", "dark": "auto"},
    },
}
```

## Usage

1. **From an object**: open e.g. a Device → *Diagrams* tab → *Add Diagram* (creates the diagram
   already linked to the device) or *Link Existing*.
2. **Draw**: on the diagram page click *Edit Diagram* — the embedded editor opens. Press the
   editor's *Save* button to store the XML and refresh the SVG preview. *Exit* returns to NetBox.
3. **Link more objects**: diagram page → *Assign to Object* (or link from any object's tab).
   Unlinking never deletes the diagram.

## REST API

- `/api/plugins/drawio/diagrams/` — CRUD incl. `source_xml` / `svg_cache`.
  The **list** response intentionally omits both blob fields (they can reach
  `max_size` per row); retrieve a diagram by id to get them. `?brief=true`
  is unaffected.
- `/api/plugins/drawio/diagram-assignments/` — `object_type` as `"app.model"`, e.g.
  `{"diagram": 1, "object_type": "dcim.device", "object_id": 42}`

## Development

```bash
/opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py test netbox_drawio --keepdb
```

## License

Apache-2.0
