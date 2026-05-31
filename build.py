#!/usr/bin/env python3
"""build.py — assemblage déterministe HTML depuis manifest.json."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import markdown as md


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _toc(entries: list[dict]) -> str:
    items = []
    for e in entries:
        indent = "  " if e["type"] == "widget" else ""
        items.append(f'{indent}<li><a href="#{e["anchor"]}">{e["title"]}</a></li>')
    return "<nav><ul>\n" + "\n".join(items) + "\n</ul></nav>\n"


def _section(entry: dict, sections_index: dict) -> str:
    sec = sections_index.get(entry["id"])
    if not sec:
        raise KeyError(f"Section '{entry['id']}' absente de sections_draft.json")
    level = sec.get("level", 2)
    body  = md.markdown(sec["content"])
    return (f'<section id="{entry["anchor"]}">\n'
            f'<h{level}>{entry["title"]}</h{level}>\n{body}\n</section>\n')


def _widget(entry: dict, widgets_dir: Path) -> str:
    wpath = widgets_dir / f"{entry['id']}.html"
    if not wpath.exists():
        raise FileNotFoundError(f"{entry['id']}.html introuvable dans {widgets_dir}")
    raw  = wpath.read_text()
    # Extraire le contenu du body si le widget est un document HTML complet
    m    = re.search(r"<body[^>]*>(.*?)</body>", raw, re.DOTALL | re.IGNORECASE)
    body = m.group(1).strip() if m else raw
    # Extraire les <style> du <head>
    styles = "\n".join(re.findall(r"<style[^>]*>.*?</style>", raw, re.DOTALL | re.IGNORECASE))
    return (f'<div class="widget-container" id="{entry["anchor"]}">\n'
            f'<h3>{entry["title"]}</h3>\n'
            f'{styles}\n{body}\n</div>\n')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build(run_dir: Path, css_path: Path | None = None) -> None:
    run_dir    = Path(run_dir)
    manifest   = json.loads((run_dir / "manifest.json").read_text())
    sections   = json.loads((run_dir / "sections_draft.json").read_text())
    sec_index  = {s["id"]: s for s in sections}
    widgets_dir = run_dir / "widgets"

    # Validation préalable : tous les widgets référencés doivent exister
    for e in manifest:
        if e["type"] == "widget":
            wpath = widgets_dir / f"{e['id']}.html"
            if not wpath.exists():
                raise FileNotFoundError(f"{e['id']}.html manquant dans {widgets_dir}")

    css = (css_path or Path("assets/style.css")).read_text()

    parts = [_toc(manifest)]
    for e in manifest:
        if e["type"] == "section":
            parts.append(_section(e, sec_index))
        elif e["type"] == "widget":
            parts.append(_widget(e, widgets_dir))

    title = sections[0]["title"] if sections else "Document"
    html  = (
        f'<!DOCTYPE html>\n<html lang="fr">\n<head>\n'
        f'<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{title}</title>\n'
        f'<style>{css}</style>\n'
        f'</head>\n<body>\n'
        + "".join(parts)
        + '</body>\n</html>'
    )

    out = run_dir / "output.html"
    out.write_text(html)
    n_widgets = sum(1 for e in manifest if e["type"] == "widget")
    print(f"[build] {out} généré ({len(html)} chars, {n_widgets} widget(s))")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build.py run/<slug>/", file=sys.stderr)
        sys.exit(1)
    build(Path(sys.argv[1]))
