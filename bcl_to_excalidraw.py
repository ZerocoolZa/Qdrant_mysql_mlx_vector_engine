#!/usr/bin/env python3
"""
BCL-to-Excalidraw converter.
Compact DSL → Excalidraw JSON. ~98% token reduction.

DSL syntax:
  box id "label" @ (x,y) w=180 h=80 fill=#color stroke=#color
  ellipse id "label" @ (x,y) w=180 h=80 fill=#color
  diamond id "label" @ (x,y) w=180 h=80 fill=#color
  text id "label" @ (x,y) size=20
  arrow src --> dst "label"
  arrow src --> dst "label" dashed

Usage:
  python3 bcl_to_excalidraw.py input.bcl output.excalidraw
"""
import json
import sys
import re
import random
import time


def rand_id():
    return f"{random.randint(1000000000, 9999999999)}"


def make_box(el_id, x, y, w, h, fill, stroke, label, shape="rectangle"):
    box_id = el_id
    text_id = f"{el_id}-t"
    now = int(time.time() * 1000)
    box = {
        "id": box_id, "type": shape, "x": x, "y": y,
        "width": w, "height": h, "angle": 0,
        "strokeColor": stroke or "#1e1e1e",
        "backgroundColor": fill or "transparent",
        "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
        "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
        "index": "a0", "roundness": {"type": 3},
        "seed": random.randint(1000, 9999), "version": 1,
        "versionNonce": random.randint(1000, 9999),
        "isDeleted": False,
        "boundElements": [{"id": text_id, "type": "text"}],
        "updated": now, "link": None, "locked": False
    }
    text = {
        "id": text_id, "type": "text",
        "x": x + w / 2 - 60, "y": y + h / 2 - 15,
        "width": 120, "height": 50, "angle": 0,
        "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
        "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
        "index": "a1", "roundness": None,
        "seed": random.randint(1000, 9999), "version": 1,
        "versionNonce": random.randint(1000, 9999),
        "isDeleted": False, "boundElements": None,
        "updated": now, "link": None, "locked": False,
        "text": label, "fontSize": 16, "fontFamily": 5,
        "textAlign": "center", "verticalAlign": "middle",
        "containerId": box_id, "originalText": label,
        "autoResize": False, "lineHeight": 1.25
    }
    return [box, text], box


def make_arrow(arr_id, src_box, dst_box, label, dashed=False):
    now = int(time.time() * 1000)
    sx = src_box["x"] + src_box["width"] / 2
    sy = src_box["y"] + src_box["height"]
    dx = dst_box["x"] + dst_box["width"] / 2
    dy = dst_box["y"]
    arrow = {
        "id": arr_id, "type": "arrow",
        "x": sx, "y": sy,
        "width": dx - sx, "height": dy - sy, "angle": 0,
        "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 2,
        "strokeStyle": "dashed" if dashed else "solid",
        "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
        "index": "a0", "roundness": {"type": 2},
        "seed": random.randint(1000, 9999), "version": 1,
        "versionNonce": random.randint(1000, 9999),
        "isDeleted": False, "boundElements": None,
        "updated": now, "link": None, "locked": False,
        "startBinding": {"elementId": src_box["id"], "focus": 0, "gap": 1},
        "endBinding": {"elementId": dst_box["id"], "focus": 0, "gap": 1},
        "lastCommittedPoint": None,
        "startArrowhead": None, "endArrowhead": "arrow",
        "points": [[0, 0], [dx - sx, dy - sy]]
    }
    elements = [arrow]
    if label:
        text_id = f"{arr_id}-t"
        text = {
            "id": text_id, "type": "text",
            "x": (sx + dx) / 2 - 30, "y": (sy + dy) / 2 - 10,
            "width": 60, "height": 20, "angle": 0,
            "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
            "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
            "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
            "index": "a1", "roundness": None,
            "seed": random.randint(1000, 9999), "version": 1,
            "versionNonce": random.randint(1000, 9999),
            "isDeleted": False, "boundElements": None,
            "updated": now, "link": None, "locked": False,
            "text": label, "fontSize": 12, "fontFamily": 5,
            "textAlign": "center", "verticalAlign": "middle",
            "containerId": None, "originalText": label,
            "autoResize": False, "lineHeight": 1.25
        }
        arrow["boundElements"] = [{"id": text_id, "type": "text"}]
        elements.append(text)
    return elements


def parse_bcl(text):
    elements = []
    boxes = {}
    box_order = []
    idx = 0

    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # arrow: arrow src --> dst "label" [dashed]
        arr_m = re.match(
            r'arrow\s+(\w+)\s*-->\s*(\w+)(?:\s+"([^"]*)")?(?:\s+(dashed))?',
            line
        )
        if arr_m:
            src, dst, label, dashed = arr_m.groups()
            if src in boxes and dst in boxes:
                arr_id = f"arr-{src}-{dst}"
                arr_els = make_arrow(arr_id, boxes[src], boxes[dst], label, bool(dashed))
                elements.extend(arr_els)
            continue

        # box/ellipse/diamond: shape id "label" @ (x,y) [w=W] [h=H] [fill=#color] [stroke=#color]
        shape_m = re.match(
            r'(box|ellipse|diamond|text)\s+(\w+)\s+"([^"]*)"\s+@\s+\((\d+),\s*(\d+)\)'
            r'(?:\s+w=(\d+))?(?:\s+h=(\d+))?(?:\s+fill=(#[0-9a-fA-F]+))?(?:\s+stroke=(#[0-9a-fA-F]+))?(?:\s+size=(\d+))?',
            line
        )
        if shape_m:
            shape_kw, el_id, label, x, y, w, h, fill, stroke, size = shape_m.groups()
            x, y = int(x), int(y)
            w = int(w) if w else 180
            h = int(h) if h else 80
            shape_map = {"box": "rectangle", "ellipse": "ellipse", "diamond": "diamond", "text": "text"}
            ex_shape = shape_map.get(shape_kw, "rectangle")

            if shape_kw == "text":
                now = int(time.time() * 1000)
                t = {
                    "id": el_id, "type": "text", "x": x, "y": y,
                    "width": 200, "height": 50, "angle": 0,
                    "strokeColor": stroke or "#1e1e1e",
                    "backgroundColor": "transparent",
                    "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
                    "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
                    "index": f"a{idx}", "roundness": None,
                    "seed": random.randint(1000, 9999), "version": 1,
                    "versionNonce": random.randint(1000, 9999),
                    "isDeleted": False, "boundElements": None,
                    "updated": now, "link": None, "locked": False,
                    "text": label, "fontSize": int(size) if size else 20,
                    "fontFamily": 5, "textAlign": "left", "verticalAlign": "top",
                    "containerId": None, "originalText": label,
                    "autoResize": False, "lineHeight": 1.25
                }
                elements.append(t)
                idx += 1
            else:
                els, box = make_box(el_id, x, y, w, h, fill, stroke, label, ex_shape)
                for e in els:
                    e["index"] = f"a{idx}"
                    idx += 1
                elements.extend(els)
                boxes[el_id] = box
                box_order.append(el_id)
            continue

    return elements


def render_svg(elements, boxes):
    """Render elements as SVG HTML with auto-refresh."""
    # Zone backgrounds first (low opacity)
    zone_ids = {"zone_ai", "zone_proc", "zone_core", "zone_data", "zone_pipe"}
    parts = []
    for el in elements:
        if el["id"] in zone_ids and el["type"] == "rectangle":
            parts.append(
                f'<rect x="{el["x"]}" y="{el["y"]}" width="{el["width"]}" '
                f'height="{el["height"]}" fill="{el["backgroundColor"]}" '
                f'stroke="{el["strokeColor"]}" stroke-width="3" rx="12" '
                f'opacity="0.3" />'
            )
    # Non-zone elements
    for el in elements:
        if el["id"] in zone_ids:
            continue
        if el["type"] == "rectangle":
            parts.append(
                f'<rect x="{el["x"]}" y="{el["y"]}" width="{el["width"]}" '
                f'height="{el["height"]}" fill="{el["backgroundColor"]}" '
                f'stroke="{el["strokeColor"]}" stroke-width="2" rx="8" />'
            )
        elif el["type"] == "ellipse":
            cx = el["x"] + el["width"] / 2
            cy = el["y"] + el["height"] / 2
            rx = el["width"] / 2
            ry = el["height"] / 2
            parts.append(
                f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
                f'fill="{el["backgroundColor"]}" stroke="{el["strokeColor"]}" stroke-width="2" />'
            )
        elif el["type"] == "diamond":
            cx = el["x"] + el["width"] / 2
            cy = el["y"] + el["height"] / 2
            hw = el["width"] / 2
            hh = el["height"] / 2
            pts = f"{cx},{el["y"]} {el["x"]+el["width"]},{cy} {cx},{el["y"]+el["height"]} {el["x"]},{cy}"
            parts.append(
                f'<polygon points="{pts}" fill="{el["backgroundColor"]}" '
                f'stroke="{el["strokeColor"]}" stroke-width="2" />'
            )
        elif el["type"] == "text":
            tx = el["x"]
            ty = el["y"] + (el.get("fontSize", 20))
            color = el.get("strokeColor", "#1e1e1e")
            size = el.get("fontSize", 20)
            for i, line_text in enumerate(el["text"].split("\n")):
                parts.append(
                    f'<text x="{tx}" y="{ty + i * size * 1.25}" '
                    f'font-size="{size}" font-family="sans-serif" fill="{color}">'
                    f'{line_text}</text>'
                )
        elif el["type"] == "arrow":
            x1 = el["x"]
            y1 = el["y"]
            x2 = el["x"] + el["width"]
            y2 = el["y"] + el["height"]
            dash = ' stroke-dasharray="8,4"' if el.get("strokeStyle") == "dashed" else ""
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2
            parts.append(
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                f'stroke="#1e1e1e" stroke-width="2"{dash} '
                f'marker-end="url(#arrowhead)" />'
            )
            if el.get("boundElements"):
                for be in el["boundElements"]:
                    for e2 in elements:
                        if e2["id"] == be["id"] and e2["type"] == "text":
                            parts.append(
                                f'<text x="{mx - 20}" y="{my}" '
                                f'font-size="12" font-family="sans-serif" '
                                f'fill="#666" text-anchor="middle">'
                                f'{e2["text"]}</text>'
                            )

    svg_body = "\n        ".join(parts)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ margin: 0; background: #fff; overflow: hidden; }}
svg {{ display: block; }}
</style>
</head>
<body>
<svg width="1400" height="500" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <marker id="arrowhead" markerWidth="10" markerHeight="7"
                refX="10" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#1e1e1e" />
        </marker>
    </defs>
        {svg_body}
</svg>
<script>
fetch(window.location.href, {{cache: "no-store"}})
.then(r => r.text())
.then(html => {{
    if (html !== document.documentElement.outerHTML) {{
        document.body.innerHTML = html.match(/<body[^>]*>([\\s\\S]*)<\\/body>/)[1];
    }}
}});
setInterval(() => {{
    fetch(window.location.href + "?t=" + Date.now(), {{cache: "no-store"}})
    .then(r => r.text())
    .then(html => {{
        const newBody = html.match(/<body[^>]*>([\\s\\S]*)<\\/body>/)[1];
        if (newBody !== document.body.innerHTML) {{
            document.body.innerHTML = newBody;
        }}
    }});
}}, 800);
</script>
</body>
</html>"""


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 bcl_to_excalidraw.py input.bcl output.excalidraw [--html out.html]")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        bcl_text = f.read()

    elements = parse_bcl(bcl_text)
    boxes = {}
    for el in elements:
        if el["type"] in ("rectangle", "ellipse", "diamond"):
            boxes[el["id"]] = el

    # Always write excalidraw JSON
    output = {
        "type": "excalidraw",
        "version": 2,
        "source": "bcl-to-excalidraw",
        "elements": elements,
        "appState": {
            "gridSize": 20,
            "gridStep": 5,
            "gridModeEnabled": False,
            "viewBackgroundColor": "#ffffff"
        },
        "files": {}
    }
    with open(sys.argv[2], "w") as f:
        json.dump(output, f, indent=2)

    # Also write HTML if --html flag
    html_path = None
    if "--html" in sys.argv:
        idx = sys.argv.index("--html")
        if idx + 1 < len(sys.argv):
            html_path = sys.argv[idx + 1]
    if not html_path:
        html_path = sys.argv[2].replace(".excalidraw", ".html")

    with open(html_path, "w") as f:
        f.write(render_svg(elements, boxes))

    print(f"OK: {len(elements)} elements → {sys.argv[2]} + {html_path}")


if __name__ == "__main__":
    main()
