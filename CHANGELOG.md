# Changelog

All notable changes to this project are documented here.

## 0.1.0

First public release. Requires NetBox 4.6.4 – 4.6.99, Python ≥ 3.12.

- Embedded draw.io editor using the draw.io embed protocol — diagram XML travels only between
  the browser and NetBox; the editor host never receives it.
- Diagrams tab on object detail pages with SVG preview cards, per-card *edit* / *unlink*
  actions, and *Add Diagram* / *Link Existing* buttons.
- Many-to-many assignment: one diagram links to any number of objects of any enabled type.
- SVG previews served from a hardened endpoint (CSP, `sandbox`, `nosniff`; rendered via `<img>`
  so embedded scripts can never execute).
- `.drawio` source download.
- REST API for diagrams and assignments; the diagram list response omits the `source_xml` /
  `svg_cache` blobs.
- Global search, change logging (content blobs excluded; a `content_hash` records every content
  change), tags, custom fields, journaling, and object permissions.
- Configurable editor URL and query params, autosave, model scoping (`applied_scope`,
  `scope_filter`, `excluded_apps`, `excluded_models`), tab placement, and a byte cap on
  diagram XML and SVG.
