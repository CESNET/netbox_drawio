# Changelog

All notable changes to this project are documented here.

## 0.2.0 — 2026-09-04

- **Breaking:** requires NetBox 4.7.x (`min_version` 4.7.0, `max_version` 4.7.99). NetBox 4.6.x
  installs stay on 0.1.x.
- Verified against NetBox 4.7.0 (Django 6.1, django-tables2 3.0): no code or migration changes.
  List-view / API query-count baselines re-recorded (NetBox 4.7 issues fewer queries per request).

## 0.1.1 — 2026-08-26

- Fix save being silently dropped when a draw.io spinner was already active (two saves in quick
  succession, autosave during a manual save): the export request no longer sets `spinKey`, so
  draw.io's spinner guard can't swallow it ([#4](https://github.com/CESNET/netbox_drawio/issues/4)).
- The status line now shows *Saving…* as soon as a save is requested, so a stalled export is visible.

## 0.1.0 — 2026-08-21

First public release. Requires NetBox 4.6.4 – 4.6.99, Python ≥ 3.12, < 3.15.

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
