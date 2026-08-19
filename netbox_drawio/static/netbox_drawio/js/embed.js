/*
 * draw.io embed protocol glue for netbox_drawio.
 *
 * Message flow (JSON protocol, https://www.drawio.com/doc/faq/embed-mode):
 *   iframe -> {event: 'init'}              => we send {action: 'load', xml}
 *   iframe -> {event: 'save', xml}         => we stash xml, request an SVG export
 *   iframe -> {event: 'autosave', xml}     => same as save (only when autosave is on)
 *   iframe -> {event: 'export', data}      => we POST xml + svg to the NetBox save endpoint
 *   iframe -> {event: 'exit'}              => navigate back to returnUrl
 */
(function () {
    "use strict";

    const configEl = document.getElementById("drawio-config");
    const frame = document.getElementById("drawio-frame");
    const statusEl = document.getElementById("drawio-status");
    if (!configEl || !frame) {
        return;
    }

    let cfg;
    try {
        cfg = JSON.parse(configEl.textContent);
    } catch (err) {
        return;
    }

    let stashedXml = null;
    let saving = false;

    function setStatus(text, isError) {
        if (!statusEl) {
            return;
        }
        statusEl.textContent = text;
        statusEl.className = isError ? "text-danger small" : "text-muted small";
    }

    function post(message) {
        frame.contentWindow.postMessage(JSON.stringify(message), cfg.embedOrigin);
    }

    function requestExport() {
        // xmlsvg embeds the diagram XML inside the SVG, keeping the preview round-trippable
        post({ action: "export", format: "xmlsvg", xml: stashedXml, spinKey: "saving" });
    }

    function persist(svgDataUri) {
        if (saving || stashedXml === null) {
            return;
        }
        saving = true;
        setStatus("Saving…", false);
        fetch(cfg.saveUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": cfg.csrfToken,
            },
            credentials: "same-origin",
            body: JSON.stringify({ xml: stashedXml, svg_data_uri: svgDataUri }),
        })
            .then(function (response) {
                if (!response.ok) {
                    return response
                        .json()
                        .catch(function () {
                            return {};
                        })
                        .then(function (body) {
                            throw new Error(body.error || "HTTP " + response.status);
                        });
                }
                return response.json();
            })
            .then(function () {
                stashedXml = null;
                setStatus("Saved " + new Date().toLocaleTimeString(), false);
                post({ action: "status", message: "Saved", modified: false });
            })
            .catch(function (err) {
                setStatus("Save failed: " + err.message, true);
                post({ action: "status", message: "Save failed!", modified: true });
            })
            .finally(function () {
                saving = false;
            });
    }

    window.addEventListener("message", function (event) {
        if (event.origin !== cfg.embedOrigin || typeof event.data !== "string" || !event.data.length) {
            return;
        }

        let msg;
        try {
            msg = JSON.parse(event.data);
        } catch (err) {
            return;
        }

        switch (msg.event) {
            case "init":
                post({ action: "load", autosave: cfg.autosave ? 1 : 0, xml: cfg.xml || "" });
                setStatus("Ready", false);
                break;
            case "configure":
                // Only sent when the operator adds configure=1 via drawio_url_params
                post({ action: "configure", config: cfg.editorConfig || {} });
                break;
            case "save":
                stashedXml = msg.xml;
                requestExport();
                break;
            case "autosave":
                if (cfg.autosave) {
                    stashedXml = msg.xml;
                    requestExport();
                }
                break;
            case "export":
                if (stashedXml !== null && msg.data) {
                    persist(msg.data);
                }
                break;
            case "exit":
                window.location.href = cfg.returnUrl;
                break;
            default:
                break;
        }
    });
})();
