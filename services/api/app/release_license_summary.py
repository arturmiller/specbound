"""Summarize open release findings while keeping the underlying approvals scoped."""

from collections import Counter
from html import escape

ARTIFACT_LABELS = {
    "portal": "Portal",
    "api-image": "API-Image",
    "worker-image": "Worker-Image",
}
ECOSYSTEMS = {
    "deb": "Debian",
    "python": "Python-Paket",
    "npm": "npm",
    "binary": "Binärdatei",
    "rust-crate": "Rust",
}
REASONS = {
    "outside-policy": "Außerhalb der Richtlinie",
    "missing-declaration": "Lizenzangabe fehlt",
    "conflicting-declarations": "Abweichende SPDX-Angaben",
    "unresolved-expression": "Lizenzausdruck ungeklärt",
}


def _cell(value):
    return (
        escape(" ".join(str(value).split()), quote=False)
        .replace("|", "&#124;")
        .replace("`", "&#96;")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
    )


def _open_findings(artifacts):
    pending = {}
    for name, artifact in artifacts.items():
        for index, component in enumerate(artifact["components"]):
            if component["status"] in ("PASS", "APPROVED"):
                continue
            key = (
                component.get("purl") or (name, index),
                component["status"],
                component["reason"],
                component["license"],
                component.get("declaredLicense"),
                component.get("concludedLicense"),
            )
            _, locations = pending.setdefault(key, (component, {}))
            locations.setdefault(name, set()).update(
                component.get("licenseSources") or component.get("locations") or []
            )
    return sorted(
        pending.values(),
        key=lambda item: (
            {"python": 0, "npm": 1, "deb": 2}.get(item[0].get("ecosystem"), 3),
            item[0]["name"],
            item[0]["version"] or "",
        ),
    )


def markdown_summary(report):
    artifacts = report["artifacts"]
    lines = [
        "# Lizenzprüfung für die Kundenauslieferung",
        "",
        "**Bereit zur Freigabe**" if report["ready"] else "**Freigabe offen**",
        "",
        "| Artefakt | Erfüllt | Freigegeben | Blockierende Verstöße | Davon ungeklärt |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, artifact in artifacts.items():
        counts = Counter(item["status"] for item in artifact["components"])
        label = ARTIFACT_LABELS[name]
        lines.append(
            f"| {label} | {counts['PASS']} | {counts['APPROVED']} | {counts['FAIL'] + counts['UNKNOWN']} | {counts['UNKNOWN']} |"
        )
    pending = []
    if not report["projectLicenseReviewed"]:
        pending.append(
            "Rechte am eigenen Code und dessen Veröffentlichungslizenz bestätigen."
        )
    for name, artifact in artifacts.items():
        label = ARTIFACT_LABELS[name]
        if not artifact["inventoryReviewed"]:
            pending.append(f"Vollständigkeit des Inventars für das {label} bestätigen.")
        if not artifact["noticesReviewed"]:
            pending.append(
                f"Lizenzhinweise und Auslieferungsauflagen für das {label} belegen."
            )
    if pending:
        lines.extend(
            ["", "## Fehlende Freigaben", "", *("- " + item for item in pending)]
        )
    findings = _open_findings(artifacts)
    if findings:
        lines.extend(
            [
                "",
                "## Offene Komponenten",
                "",
                "Identische Komponenten mit demselben Befund stehen in einer Zeile. Die Freigabe gilt für den Digest des jeweiligen Artefakts.",
                "",
                "| Komponente | Herkunft | Lizenz und Prüfgrund | Artefakte und Fundstellen |",
                "| --- | --- | --- | --- |",
            ]
        )
    for component, sources in findings:
        label = " ".join(filter(None, (component["name"], component["version"])))
        ecosystem = ECOSYSTEMS.get(component.get("ecosystem"), "Unbestimmt")
        license_label = component["license"] or "Offen"
        paths = []
        for name, locations in sources.items():
            location_label = ", ".join(_cell(path) for path in sorted(locations)[:2])
            paths.append(
                ARTIFACT_LABELS[name]
                + (f"<br>{location_label}" if location_label else "")
            )
        reason = REASONS[component["reason"]]
        lines.append(
            f"| {_cell(label)} | {ecosystem} | {_cell(license_label)} · {reason} | {'<br>'.join(paths)} |"
        )
    return "\n".join(lines) + "\n"
