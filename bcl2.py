#!/usr/bin/env python3
"""
BCL v2 → Excalidraw converter.
Full mapping: every Excalidraw element type + property.

DSL SYNTAX:
  # Shapes
  box id "label" @ (x,y) w=180 h=80 [opts]
  ellipse id "label" @ (x,y) w=180 h=80 [opts]
  diamond id "label" @ (x,y) w=180 h=80 [opts]
  text id "label" @ (x,y) size=20 [opts]
  line id @ (x,y) -> (x2,y2) -> (x3,y3) [opts]
  arrow src --> dst "label" [opts]
  arrow id @ (x,y) -> (x2,y2) "label" [opts]
  freedraw id @ (x,y) pts=[(0,0),(10,5)] [opts]

  # Tree / nesting
  frame id "label" @ (x,y) w=800 h=600 {
      box child "Child" @ (20,20) w=100 h=50
  }

  # Groups
  group id {
      box a "A" @ (100,100) w=80 h=40
      box b "B" @ (200,100) w=80 h=40
  }

  # Options (all optional, defaults shown)
  fill=#color stroke=#color strokeW=2
  strokeStyle=solid|dashed|dotted
  fillStyle=solid|hachure|cross-hatch
  roughness=0|1|2  opacity=100  angle=0
  fontSize=20 font=1|2|3|4|5
  align=left|center|right
  round=0|1|2|3  dashed  dotted

Usage:
  python3 bcl2.py input.bcl output.excalidraw
"""
import json
import sys
import re
import random
import time

FONT_MAP = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
ROUNDNESS_MAP = {0: None, 1: {"type": 1}, 2: {"type": 2}, 3: {"type": 3}}


def rid():
    return str(random.randint(1000000000, 9999999999))


def now_ms():
    return int(time.time() * 1000)


def parse_opts(line):
    """Extract optional properties from a line."""
    opts = {}
    m = re.search(r'fill=(#[0-9a-fA-F]+)', line)
    if m: opts["fill"] = m.group(1)
    m = re.search(r'stroke=(#[0-9a-fA-F]+)', line)
    if m: opts["stroke"] = m.group(1)
    m = re.search(r'strokeW=(\d+)', line)
    if m: opts["strokeW"] = int(m.group(1))
    m = re.search(r'strokeStyle=(solid|dashed|dotted)', line)
    if m: opts["strokeStyle"] = m.group(1)
    if re.search(r'\bdashed\b', line): opts["strokeStyle"] = "dashed"
    if re.search(r'\bdotted\b', line): opts["strokeStyle"] = "dotted"
    m = re.search(r'fillStyle=(solid|hachure|cross-hatch)', line)
    if m: opts["fillStyle"] = m.group(1)
    m = re.search(r'roughness=(\d)', line)
    if m: opts["roughness"] = int(m.group(1))
    m = re.search(r'opacity=(\d+)', line)
    if m: opts["opacity"] = int(m.group(1))
    m = re.search(r'angle=(-?\d+)', line)
    if m: opts["angle"] = int(m.group(1))
    m = re.search(r'fontSize=(\d+)', line)
    if m: opts["fontSize"] = int(m.group(1))
    m = re.search(r'size=(\d+)', line)
    if m: opts["fontSize"] = int(m.group(1))
    m = re.search(r'font=(\d)', line)
    if m: opts["font"] = int(m.group(1))
    m = re.search(r'align=(left|center|right)', line)
    if m: opts["align"] = m.group(1)
    m = re.search(r'round=(\d)', line)
    if m: opts["round"] = int(m.group(1))
    m = re.search(r'w=(\d+)', line)
    if m: opts["w"] = int(m.group(1))
    m = re.search(r'h=(\d+)', line)
    if m: opts["h"] = int(m.group(1))
    return opts


def base_el(el_id, el_type, x, y, w, h, opts):
    """Create base element with all common properties."""
    return {
        "id": el_id, "type": el_type,
        "x": x, "y": y, "width": w, "height": h,
        "angle": opts.get("angle", 0),
        "strokeColor": opts.get("stroke", "#1e1e1e"),
        "backgroundColor": opts.get("fill", "transparent"),
        "fillStyle": opts.get("fillStyle", "solid"),
        "strokeWidth": opts.get("strokeW", 2),
        "strokeStyle": opts.get("strokeStyle", "solid"),
        "roughness": opts.get("roughness", 1),
        "opacity": opts.get("opacity", 100),
        "groupIds": [], "frameId": None,
        "index": "a0",
        "roundness": ROUNDNESS_MAP.get(opts.get("round", 3), {"type": 3}),
        "seed": random.randint(1000, 9999),
        "version": 1,
        "versionNonce": random.randint(1000, 9999),
        "isDeleted": False, "boundElements": [],
        "updated": now_ms(), "link": None, "locked": False
    }


def make_shape(el_id, shape, label, x, y, opts):
    w = opts.get("w", 180)
    h = opts.get("h", 80)
    el = base_el(el_id, shape, x, y, w, h, opts)
    elements = [el]
    if label:
        text_id = f"{el_id}-t"
        el["boundElements"] = [{"id": text_id, "type": "text"}]
        # Auto-size text to fit inside shape
        fs = opts.get("fontSize", 16)
        label_text = label.replace("\\n", "\n")
        lines = label_text.split("\n")
        text_w = min(w - 20, max(len(l) for l in lines) * fs * 0.65)
        text_h = min(h - 10, len(lines) * fs * 1.25)
        tx = x + (w - text_w) / 2
        ty = y + (h - text_h) / 2
        t = base_el(text_id, "text", tx, ty, text_w, text_h, opts)
        t["strokeColor"] = "#1e1e1e"
        t["backgroundColor"] = "transparent"
        t["text"] = label_text
        t["fontSize"] = fs
        t["fontFamily"] = opts.get("font", 5)
        t["textAlign"] = "center"
        t["verticalAlign"] = "middle"
        t["containerId"] = el_id
        t["originalText"] = label_text
        t["autoResize"] = False
        t["lineHeight"] = 1.25
        t["roundness"] = None
        elements.append(t)
    return elements, el


def make_text(el_id, text, x, y, opts):
    fs = opts.get("fontSize", 20)
    text_clean = text.replace("\\n", "\n")
    lines = text_clean.split("\n")
    w = max(len(l) for l in lines) * fs * 0.65
    h = len(lines) * fs * 1.25
    el = base_el(el_id, "text", x, y, w, h, opts)
    el["strokeColor"] = opts.get("stroke", "#1e1e1e")
    el["backgroundColor"] = "transparent"
    el["text"] = text_clean
    el["fontSize"] = fs
    el["fontFamily"] = opts.get("font", 5)
    el["textAlign"] = opts.get("align", "left")
    el["verticalAlign"] = "top"
    el["containerId"] = None
    el["originalText"] = text_clean
    el["autoResize"] = False
    el["lineHeight"] = 1.25
    el["roundness"] = None
    el["boundElements"] = []
    return [el], el


def make_line(el_id, x, y, points, opts):
    w = max(p[0] for p in points) - min(p[0] for p in points)
    h = max(p[1] for p in points) - min(p[1] for p in points)
    el = base_el(el_id, "line", x, y, w, h, opts)
    el["points"] = points
    el["lastCommittedPoint"] = None
    el["startArrowhead"] = None
    el["endArrowhead"] = None
    el["boundElements"] = []
    return [el], el


def make_arrow_between(el_id, src, dst, label, opts):
    # Smart edge routing: find nearest edges between src and dst
    src_cx = src["x"] + src["width"] / 2
    src_cy = src["y"] + src["height"] / 2
    dst_cx = dst["x"] + dst["width"] / 2
    dst_cy = dst["y"] + dst["height"] / 2

    # Determine start point: nearest edge of src toward dst
    if dst_cy > src_cy + src["height"] / 2:
        # dst is below — start from bottom
        sx = src_cx
        sy = src["y"] + src["height"]
    elif dst_cy < src_cy - src["height"] / 2:
        # dst is above — start from top
        sx = src_cx
        sy = src["y"]
    elif dst_cx > src_cx:
        # dst is to the right — start from right edge
        sx = src["x"] + src["width"]
        sy = src_cy
    else:
        # dst is to the left — start from left edge
        sx = src["x"]
        sy = src_cy

    # Determine end point: nearest edge of dst toward src
    if src_cy > dst_cy + dst["height"] / 2:
        # src is below — end at bottom of dst
        dx = dst_cx
        dy = dst["y"] + dst["height"]
    elif src_cy < dst_cy - dst["height"] / 2:
        # src is above — end at top of dst
        dx = dst_cx
        dy = dst["y"]
    elif src_cx > dst_cx:
        # src is to the right — end at right edge of dst
        dx = dst["x"] + dst["width"]
        dy = dst_cy
    else:
        # src is to the left — end at left edge of dst
        dx = dst["x"]
        dy = dst_cy

    el = base_el(el_id, "arrow", sx, sy, dx - sx, dy - sy, opts)
    el["points"] = [[0, 0], [dx - sx, dy - sy]]
    el["startBinding"] = {"elementId": src["id"], "focus": 0, "gap": 1}
    el["endBinding"] = {"elementId": dst["id"], "focus": 0, "gap": 1}
    el["lastCommittedPoint"] = None
    el["startArrowhead"] = None
    el["endArrowhead"] = "arrow"
    elements = [el]
    if label:
        text_id = f"{el_id}-t"
        el["boundElements"] = [{"id": text_id, "type": "text"}]
        mx = (sx + dx) / 2 - 30
        my = (sy + dy) / 2 - 10
        label_text = label.replace("\\n", "\n")
        t = base_el(text_id, "text", mx, my, 60, 20, opts)
        t["strokeColor"] = "#666"
        t["backgroundColor"] = "transparent"
        t["text"] = label_text
        t["fontSize"] = 12
        t["fontFamily"] = 5
        t["textAlign"] = "center"
        t["verticalAlign"] = "middle"
        t["containerId"] = el_id
        t["originalText"] = label_text
        t["autoResize"] = False
        t["lineHeight"] = 1.25
        t["roundness"] = None
        t["boundElements"] = []
        elements.append(t)
    return elements


def make_arrow_points(el_id, x, y, points, label, opts):
    w = points[-1][0] - points[0][0]
    h = points[-1][1] - points[0][1]
    el = base_el(el_id, "arrow", x, y, w, h, opts)
    el["points"] = points
    el["startBinding"] = None
    el["endBinding"] = None
    el["lastCommittedPoint"] = None
    el["startArrowhead"] = None
    el["endArrowhead"] = "arrow"
    elements = [el]
    if label:
        text_id = f"{el_id}-t"
        el["boundElements"] = [{"id": text_id, "type": "text"}]
        t = base_el(text_id, "text", x + w / 2 - 30, y + h / 2 - 10, 60, 20, opts)
        t["strokeColor"] = "#666"
        t["backgroundColor"] = "transparent"
        t["text"] = label
        t["fontSize"] = 12
        t["fontFamily"] = 5
        t["textAlign"] = "center"
        t["verticalAlign"] = "middle"
        t["containerId"] = el_id
        t["originalText"] = label
        t["autoResize"] = False
        t["lineHeight"] = 1.25
        t["roundness"] = None
        t["boundElements"] = []
        elements.append(t)
    return elements


def make_frame(el_id, label, x, y, opts):
    w = opts.get("w", 400)
    h = opts.get("h", 300)
    el = base_el(el_id, "frame", x, y, w, h, opts)
    el["name"] = label or el_id
    el["boundElements"] = []
    return [el], el


def parse_bcl(text):
    lines = text.split("\n")
    elements = []
    boxes = {}
    frame_stack = []
    group_stack = []
    idx = [0]

    def next_idx():
        idx[0] += 1
        return f"a{idx[0]}"

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("#"):
            i += 1
            continue

        opts = parse_opts(line)

        # --- frame block ---
        m = re.match(r'frame\s+(\w+)\s+"([^"]*)"\s+@\s+\((\d+),\s*(\d+)\)', line)
        if m and "{" in line:
            fid, label, fx, fy = m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
            frame_els, frame_el = make_frame(fid, label, fx, fy, opts)
            for e in frame_els:
                e["index"] = next_idx()
            elements.extend(frame_els)
            frame_stack.append(fid)
            i += 1
            continue

        # --- group block ---
        m = re.match(r'group\s+(\w+)\s*\{', line)
        if m:
            group_stack.append(m.group(1))
            i += 1
            continue

        # --- close block ---
        if line == "}":
            if frame_stack:
                frame_stack.pop()
            elif group_stack:
                group_stack.pop()
            i += 1
            continue

        # --- arrow src --> dst ---
        m = re.match(r'arrow\s+(\w+)\s*-->\s*(\w+)(?:\s+"([^"]*)")?', line)
        if m:
            src_id, dst_id, label = m.groups()
            if src_id in boxes and dst_id in boxes:
                arr_id = f"arr-{src_id}-{dst_id}"
                arr_els = make_arrow_between(arr_id, boxes[src_id], boxes[dst_id], label, opts)
                for e in arr_els:
                    e["index"] = next_idx()
                    if frame_stack:
                        e["frameId"] = frame_stack[-1]
                    if group_stack:
                        e["groupIds"] = list(group_stack)
                elements.extend(arr_els)
            i += 1
            continue

        # --- arrow with points ---
        m = re.match(r'arrow\s+(\w+)\s+@\s+\((\d+),\s*(\d+)\)\s*->\s*\((\d+),\s*(\d+)\)(?:\s+"([^"]*)")?', line)
        if m:
            aid, ax, ay, dx, dy, label = m.groups()
            pts = [[0, 0], [int(dx) - int(ax), int(dy) - int(ay)]]
            arr_els = make_arrow_points(aid, int(ax), int(ay), pts, label, opts)
            for e in arr_els:
                e["index"] = next_idx()
                if frame_stack:
                    e["frameId"] = frame_stack[-1]
                if group_stack:
                    e["groupIds"] = list(group_stack)
            elements.extend(arr_els)
            i += 1
            continue

        # --- line with points ---
        m = re.match(r'line\s+(\w+)\s+@\s+\((\d+),\s*(\d+)\)\s*(.*)', line)
        if m:
            lid, lx, ly, rest = m.groups()
            pts = []
            for pm in re.finditer(r'\((\d+),\s*(\d+)\)', rest):
                pts.append([int(pm.group(1)) - int(lx), int(pm.group(2)) - int(ly)])
            if pts:
                line_els, line_el = make_line(lid, int(lx), int(ly), pts, opts)
                for e in line_els:
                    e["index"] = next_idx()
                    if frame_stack:
                        e["frameId"] = frame_stack[-1]
                    if group_stack:
                        e["groupIds"] = list(group_stack)
                elements.extend(line_els)
            i += 1
            continue

        # --- shape: box/ellipse/diamond ---
        m = re.match(r'(box|ellipse|diamond)\s+(\w+)\s+"([^"]*)"\s+@\s+\((\d+),\s*(\d+)\)', line)
        if m:
            shape_kw, el_id, label, x, y = m.groups()
            shape_map = {"box": "rectangle", "ellipse": "ellipse", "diamond": "diamond"}
            els, el = make_shape(el_id, shape_map[shape_kw], label, int(x), int(y), opts)
            for e in els:
                e["index"] = next_idx()
                if frame_stack:
                    e["frameId"] = frame_stack[-1]
                if group_stack:
                    e["groupIds"] = list(group_stack)
            elements.extend(els)
            boxes[el_id] = el
            i += 1
            continue

        # --- text ---
        m = re.match(r'text\s+(\w+)\s+"([^"]*)"\s+@\s+\((\d+),\s*(\d+)\)', line)
        if m:
            el_id, text_content, x, y = m.groups()
            els, el = make_text(el_id, text_content, int(x), int(y), opts)
            for e in els:
                e["index"] = next_idx()
                if frame_stack:
                    e["frameId"] = frame_stack[-1]
                if group_stack:
                    e["groupIds"] = list(group_stack)
            elements.extend(els)
            i += 1
            continue

        i += 1

    return elements, boxes


def render_svg(elements, boxes):
    zone_prefixes = ("zone_",)
    parts = []
    # Zones first (low opacity)
    for el in elements:
        if any(el["id"].startswith(p) for p in zone_prefixes) and el["type"] == "rectangle":
            parts.append(
                f'<rect x="{el["x"]}" y="{el["y"]}" width="{el["width"]}" '
                f'height="{el["height"]}" fill="{el["backgroundColor"]}" '
                f'stroke="{el["strokeColor"]}" stroke-width="3" rx="12" '
                f'opacity="0.25" />'
            )
    # Non-zone elements
    for el in elements:
        if any(el["id"].startswith(p) for p in zone_prefixes):
            continue
        if el["type"] == "rectangle":
            parts.append(
                f'<rect x="{el["x"]}" y="{el["y"]}" width="{el["width"]}" '
                f'height="{el["height"]}" fill="{el["backgroundColor"]}" '
                f'stroke="{el["strokeColor"]}" stroke-width="{el["strokeWidth"]}" rx="8" />'
            )
        elif el["type"] == "ellipse":
            cx = el["x"] + el["width"] / 2
            cy = el["y"] + el["height"] / 2
            parts.append(
                f'<ellipse cx="{cx}" cy="{cy}" rx="{el["width"]/2}" ry="{el["height"]/2}" '
                f'fill="{el["backgroundColor"]}" stroke="{el["strokeColor"]}" '
                f'stroke-width="{el["strokeWidth"]}" />'
            )
        elif el["type"] == "diamond":
            cx = el["x"] + el["width"] / 2
            cy = el["y"] + el["height"] / 2
            pts = f"{cx},{el["y"]} {el["x"]+el["width"]},{cy} {cx},{el["y"]+el["height"]} {el["x"]},{cy}"
            parts.append(
                f'<polygon points="{pts}" fill="{el["backgroundColor"]}" '
                f'stroke="{el["strokeColor"]}" stroke-width="{el["strokeWidth"]}" />'
            )
        elif el["type"] == "text":
            tx = el["x"]
            ty = el["y"] + el.get("fontSize", 20)
            color = el.get("strokeColor", "#1e1e1e")
            size = el.get("fontSize", 20)
            for li, lt in enumerate(el["text"].split("\n")):
                parts.append(
                    f'<text x="{tx}" y="{ty + li * size * 1.25}" '
                    f'font-size="{size}" font-family="sans-serif" fill="{color}">'
                    f'{lt}</text>'
                )
        elif el["type"] == "arrow":
            x1 = el["x"]
            y1 = el["y"]
            x2 = el["x"] + el["width"]
            y2 = el["y"] + el["height"]
            dash = ' stroke-dasharray="8,4"' if el.get("strokeStyle") == "dashed" else ""
            dash = ' stroke-dasharray="2,4"' if el.get("strokeStyle") == "dotted" else dash
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2
            parts.append(
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                f'stroke="{el.get("strokeColor", "#1e1e1e")}" '
                f'stroke-width="{el.get("strokeWidth", 2)}"{dash} '
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
        elif el["type"] == "line":
            pts = " ".join(
                f"{el["x"] + p[0]},{el["y"] + p[1]}" for p in el.get("points", [])
            )
            parts.append(
                f'<polyline points="{pts}" fill="none" '
                f'stroke="{el.get("strokeColor", "#1e1e1e")}" '
                f'stroke-width="{el.get("strokeWidth", 2)}" />'
            )
        elif el["type"] == "frame":
            parts.append(
                f'<rect x="{el["x"]}" y="{el["y"]}" width="{el["width"]}" '
                f'height="{el["height"]}" fill="none" stroke="#aaa" '
                f'stroke-width="1" stroke-dasharray="4,4" rx="4" />'
            )
            parts.append(
                f'<text x="{el["x"] + 8}" y="{el["y"] + 20}" '
                f'font-size="14" font-family="sans-serif" fill="#999">'
                f'{el.get("name", el["id"])}</text>'
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
<svg width="1400" height="700" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <marker id="arrowhead" markerWidth="10" markerHeight="7"
                refX="10" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#1e1e1e" />
        </marker>
    </defs>
        {svg_body}
<script>
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
</svg>
</body>
</html>"""


def validate_bcl(text):
    """Validate BCL source before parsing. Returns (errors, warnings)."""
    errors = []
    warnings = []
    seen_ids = set()
    shape_ids = set()
    valid_types = {"box", "ellipse", "diamond", "text", "line", "arrow", "frame", "group"}
    valid_colors = re.compile(r'^#[0-9a-fA-F]{3,8}$')
    valid_fill = {"solid", "hachure", "cross-hatch"}
    valid_stroke_style = {"solid", "dashed", "dotted"}
    valid_align = {"left", "center", "right"}
    brace_depth = 0
    line_num = 0

    for raw_line in text.split("\n"):
        line_num += 1
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Track braces
        brace_depth += line.count("{") - line.count("}")
        if brace_depth < 0:
            errors.append(f"Line {line_num}: Unexpected '}}' — no matching '{{'")

        # Check known element types
        first_word = line.split()[0] if line.split() else ""
        if first_word and first_word not in valid_types and not line.startswith("}"):
            errors.append(f"Line {line_num}: Unknown element type '{first_word}'. Valid: {sorted(valid_types)}")

        # Validate colors
        for color_match in re.finditer(r'(?:fill|stroke)=(#[0-9a-fA-F]+)', line):
            color = color_match.group(1)
            if not valid_colors.match(color):
                errors.append(f"Line {line_num}: Invalid color '{color}'. Use #rrggbb format.")

        # Validate fillStyle
        m = re.search(r'fillStyle=(\w+)', line)
        if m and m.group(1) not in valid_fill:
            errors.append(f"Line {line_num}: Invalid fillStyle '{m.group(1)}'. Valid: {sorted(valid_fill)}")

        # Validate strokeStyle
        m = re.search(r'strokeStyle=(\w+)', line)
        if m and m.group(1) not in valid_stroke_style:
            errors.append(f"Line {line_num}: Invalid strokeStyle '{m.group(1)}'. Valid: {sorted(valid_stroke_style)}")

        # Validate align
        m = re.search(r'align=(\w+)', line)
        if m and m.group(1) not in valid_align:
            errors.append(f"Line {line_num}: Invalid align '{m.group(1)}'. Valid: {sorted(valid_align)}")

        # Validate numeric ranges
        m = re.search(r'opacity=(\d+)', line)
        if m and not (0 <= int(m.group(1)) <= 100):
            errors.append(f"Line {line_num}: opacity must be 0-100, got {m.group(1)}")

        m = re.search(r'roughness=(\d+)', line)
        if m and not (0 <= int(m.group(1)) <= 2):
            errors.append(f"Line {line_num}: roughness must be 0-2, got {m.group(1)}")

        m = re.search(r'strokeW=(\d+)', line)
        if m and not (1 <= int(m.group(1)) <= 4):
            warnings.append(f"Line {line_num}: strokeW typically 1-4, got {m.group(1)}")

        m = re.search(r'font=(\d+)', line)
        if m and not (1 <= int(m.group(1)) <= 5):
            errors.append(f"Line {line_num}: font must be 1-5, got {m.group(1)}")

        # Check for duplicate IDs
        id_match = re.match(r'(?:box|ellipse|diamond|text|line|frame|group)\s+(\w+)', line)
        if id_match:
            el_id = id_match.group(1)
            if el_id in seen_ids:
                errors.append(f"Line {line_num}: Duplicate ID '{el_id}' — IDs must be unique")
            seen_ids.add(el_id)
            if first_word in ("box", "ellipse", "diamond"):
                shape_ids.add(el_id)

        # Check arrow references
        arrow_match = re.match(r'arrow\s+(\w+)\s*-->\s*(\w+)', line)
        if arrow_match:
            src, dst = arrow_match.groups()
            if src not in shape_ids and src not in seen_ids:
                warnings.append(f"Line {line_num}: Arrow source '{src}' not yet defined (define before arrow)")
            if dst not in shape_ids and dst not in seen_ids:
                warnings.append(f"Line {line_num}: Arrow target '{dst}' not yet defined (define before arrow)")

        # Check for missing @ position
        if first_word in ("box", "ellipse", "diamond", "text") and "@" not in line:
            errors.append(f"Line {line_num}: Missing '@ (x,y)' position for {first_word}")

        # Check for missing ID (line starts with shape keyword then quote)
        if first_word in ("box", "ellipse", "diamond", "text", "line"):
            after_kw = line[len(first_word):].strip()
            if after_kw.startswith('"'):
                errors.append(f"Line {line_num}: {first_word} missing ID — syntax is '{first_word} id \"label\" @ (x,y)'")

        # Check for missing label on shapes
        if first_word in ("box", "ellipse", "diamond") and '"' not in line:
            warnings.append(f"Line {line_num}: {first_word} has no label (empty quotes)")

    if brace_depth > 0:
        errors.append(f"Unclosed '{{' — {brace_depth} block(s) not closed with '}}'")

    # Check for position overlaps (shapes at exact same position)
    positions = {}
    for raw in text.split("\n"):
        m = re.match(r'(box|ellipse|diamond)\s+(\w+)\s+"[^"]*"\s+@\s+\((\d+),\s*(\d+)\)', raw.strip())
        if m:
            el_type, el_id, px, py = m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
            key = (px, py)
            if key in positions:
                warnings.append(f"Position ({px},{py}): '{el_id}' overlaps with '{positions[key]}'")
            else:
                positions[key] = el_id

    return errors, warnings


def sanitize_elements(elements):
    """Fix common issues in generated elements to prevent extension errors."""
    fixes = []
    for el in elements:
        # Ensure boundElements is a list, not None
        if el.get("boundElements") is None:
            el["boundElements"] = []
            fixes.append(f"Fixed: {el['id']} boundElements null -> []")

        # Ensure groupIds is a list
        if not isinstance(el.get("groupIds"), list):
            el["groupIds"] = []

        # Clamp opacity 0-100
        if el.get("opacity", 100) < 0:
            el["opacity"] = 0
            fixes.append(f"Fixed: {el['id']} opacity clamped to 0")
        elif el.get("opacity", 100) > 100:
            el["opacity"] = 100
            fixes.append(f"Fixed: {el['id']} opacity clamped to 100")

        # Ensure width/height are positive (skip arrows — they use relative points)
        if el["type"] != "arrow":
            if el.get("width", 0) < 0:
                el["width"] = abs(el["width"])
                fixes.append(f"Fixed: {el['id']} negative width -> positive")
            if el.get("height", 0) < 0:
                el["height"] = abs(el["height"])
                fixes.append(f"Fixed: {el['id']} negative height -> positive")

        # Ensure strokeWidth is valid
        if el.get("strokeWidth", 2) < 1:
            el["strokeWidth"] = 1
        elif el.get("strokeWidth", 2) > 19:
            el["strokeWidth"] = 19

        # Ensure valid fillStyle
        if el.get("fillStyle") not in ("solid", "hachure", "cross-hatch"):
            el["fillStyle"] = "solid"
            fixes.append(f"Fixed: {el['id']} invalid fillStyle -> solid")

        # Ensure valid strokeStyle
        if el.get("strokeStyle") not in ("solid", "dashed", "dotted"):
            el["strokeStyle"] = "solid"

        # Text elements must have text field
        if el["type"] == "text" and not el.get("text"):
            el["text"] = ""
            fixes.append(f"Fixed: {el['id']} empty text -> empty string")

        # Arrows must have points
        if el["type"] == "arrow" and not el.get("points"):
            el["points"] = [[0, 0], [0, 0]]
            fixes.append(f"Fixed: {el['id']} missing points -> default")

        # Ensure seed and versionNonce are ints
        if not isinstance(el.get("seed"), int):
            el["seed"] = random.randint(1000, 9999)
        if not isinstance(el.get("versionNonce"), int):
            el["versionNonce"] = random.randint(1000, 9999)

    return fixes


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 bcl2.py input.bcl output.excalidraw")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        bcl_text = f.read()

    # Step 1: Validate BCL source
    errors, warnings = validate_bcl(bcl_text)
    if errors:
        print("ERRORS — fix these before generating:")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  ⚠ {w}")

    # Step 2: Parse BCL
    elements, boxes = parse_bcl(bcl_text)

    # Step 3: Sanitize elements (auto-fix issues)
    fixes = sanitize_elements(elements)
    if fixes:
        print(f"AUTO-FIXED {len(fixes)} issue(s):")
        for f in fixes:
            print(f"  → {f}")

    # Step 4: Generate output
    output = {
        "type": "excalidraw",
        "version": 2,
        "source": "bcl2-converter",
        "elements": elements,
        "appState": {
            "gridSize": 20,
            "gridStep": 5,
            "gridModeEnabled": False,
            "viewBackgroundColor": "#ffffff"
        },
        "files": {}
    }

    # Step 5: Validate output JSON before writing
    REQUIRED_FIELDS = {"id", "type", "x", "y", "width", "height", "angle",
                       "strokeColor", "backgroundColor", "fillStyle", "strokeWidth",
                       "strokeStyle", "roughness", "opacity", "groupIds", "frameId",
                       "index", "roundness", "seed", "version", "versionNonce",
                       "isDeleted", "boundElements", "updated", "link", "locked"}
    VALID_TYPES = {"rectangle", "ellipse", "diamond", "text", "line", "arrow",
                   "freedraw", "image", "frame", "magicframe", "iframe", "embeddable"}
    output_errors = []
    for el in elements:
        missing = REQUIRED_FIELDS - set(el.keys())
        if missing:
            output_errors.append(f"Element '{el.get('id','?')}': missing fields {missing}")
        if el.get("type") not in VALID_TYPES:
            output_errors.append(f"Element '{el.get('id','?')}': invalid type '{el.get('type')}'")
        if not isinstance(el.get("id"), str) or not el["id"]:
            output_errors.append(f"Element at index {elements.index(el)}: missing/empty id")
        if el.get("type") == "text" and "text" not in el:
            output_errors.append(f"Text element '{el['id']}': missing 'text' field")
        if el.get("type") == "arrow" and "points" not in el:
            output_errors.append(f"Arrow element '{el['id']}': missing 'points' field")
        if el.get("type") == "arrow" and "endArrowhead" not in el:
            output_errors.append(f"Arrow element '{el['id']}': missing 'endArrowhead' field")

    if output_errors:
        print("OUTPUT VALIDATION FAILED:")
        for e in output_errors:
            print(f"  ✗ {e}")
        sys.exit(1)

    # Step 6: Write files
    with open(sys.argv[2], "w") as f:
        json.dump(output, f, indent=2)

    html_path = sys.argv[2].replace(".excalidraw", ".html")
    with open(html_path, "w") as f:
        f.write(render_svg(elements, boxes))

    # Step 7: Verify written file is valid JSON
    try:
        with open(sys.argv[2]) as f:
            json.load(f)
    except json.JSONDecodeError as e:
        print(f"FATAL: Output file is invalid JSON: {e}")
        sys.exit(1)

    print(f"OK: {len(elements)} elements -> {sys.argv[2]} + {html_path}")


if __name__ == "__main__":
    main()
