"""VBStyle domain implementation: accessibility.

a11y: WCAG compliance, ARIA labels, screen reader, keyboard nav, contrast.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import re


class DomAccessibility:
    """a11y: WCAG compliance, ARIA labels, screen reader, keyboard nav, contrast."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._screen_reader = False
        self._context = {}
        self._violations = []
        self._preferences = {"contrast": "normal", "motion": "allow", "font_scale": 1.0}

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "validate_wcag": self.validate_wcag,
            "generate_aria": self.generate_aria,
            "audit_contrast": self.audit_contrast,
            "test_keyboard": self.test_keyboard,
            "enable_screen_reader": self.enable_screen_reader,
            "validate_focus": self.validate_focus,
            "set_context": self.set_context,
            "check_alt_text": self.check_alt_text,
            "get_preferences": self.get_preferences,
            "report": self.report,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def validate_wcag(self, params=None):
        params = params or {}
        try:
            html = params.get("html", "")
            level = params.get("level", "AA")
            violations = []
            if not re.search(r"<img[^>]+alt=", html, re.I):
                imgs = re.findall(r"<img[^>]*>", html, re.I)
                for img in imgs:
                    if not re.search(r"\balt=", img, re.I):
                        violations.append({"rule": "1.1.1", "level": "A", "msg": "img missing alt"})
            if re.search(r"<a[^>]*href", html, re.I):
                links = re.findall(r"<a[^>]*>([^<]*)</a>", html, re.I)
                for text in links:
                    if not text.strip() and "click here" not in text.lower():
                        violations.append({"rule": "2.4.4", "level": "A", "msg": "empty link text"})
            if not re.search(r"<html[^>]*lang=", html, re.I) and "<html" in html.lower():
                violations.append({"rule": "3.1.1", "level": "A", "msg": "html missing lang"})
            if level == "AAA" and not re.search(r"<(h1|h2|h3|h4|h5|h6)", html, re.I):
                violations.append({"rule": "1.3.1", "level": "A", "msg": "no heading structure"})
            self._violations = violations
            compliant = len(violations) == 0
            result = {"domain": "accessibility", "method": "validate_wcag", "data": {"level": level, "compliant": compliant, "violations": violations, "count": len(violations)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VALIDATE_WCAG_ERROR", str(e), 0))

    def generate_aria(self, params=None):
        params = params or {}
        try:
            role = params.get("role", "button")
            label = params.get("label", "")
            attrs = params.get("attrs") or {}
            aria_parts = [f'role="{role}"']
            if label:
                aria_parts.append(f'aria-label="{label}"')
            for k, v in attrs.items():
                aria_parts.append(f'aria-{k}="{v}"')
            aria_str = " ".join(aria_parts)
            result = {"domain": "accessibility", "method": "generate_aria", "data": {"role": role, "aria": aria_str, "label": label}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GENERATE_ARIA_ERROR", str(e), 0))

    def audit_contrast(self, params=None):
        params = params or {}
        try:
            fg = params.get("foreground", "#000000")
            bg = params.get("background", "#FFFFFF")
            def parse_hex(h):
                h = h.lstrip("#")
                if len(h) == 3:
                    h = "".join(c * 2 for c in h)
                r = int(h[0:2], 16)
                g = int(h[2:4], 16)
                b = int(h[4:6], 16)
                return r, g, b
            r1, g1, b1 = parse_hex(fg)
            r2, g2, b2 = parse_hex(bg)
            def luminance(r, g, b):
                def chan(c):
                    c = c / 255.0
                    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)
            l1 = luminance(r1, g1, b1)
            l2 = luminance(r2, g2, b2)
            lighter = max(l1, l2)
            darker = min(l1, l2)
            ratio = (lighter + 0.05) / (darker + 0.05)
            passes_aa_normal = ratio >= 4.5
            passes_aa_large = ratio >= 3.0
            passes_aaa_normal = ratio >= 7.0
            result = {"domain": "accessibility", "method": "audit_contrast", "data": {"foreground": fg, "background": bg, "ratio": round(ratio, 2), "passes_aa_normal": passes_aa_normal, "passes_aa_large": passes_aa_large, "passes_aaa_normal": passes_aaa_normal}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("AUDIT_CONTRAST_ERROR", str(e), 0))

    def test_keyboard(self, params=None):
        params = params or {}
        try:
            html = params.get("html", "")
            issues = []
            interactive = re.findall(r"<(a|button|input|select|textarea)[^>]*>", html, re.I)
            tabindex = re.findall(r'tabindex="(-?\d+)"', html, re.I)
            for tb in tabindex:
                if int(tb) > 0:
                    issues.append({"msg": f"positive tabindex {tb} breaks order"})
            has_focus_style = bool(re.search(r":focus|outline", html, re.I))
            if not has_focus_style:
                issues.append({"msg": "no visible focus indicator"})
            result = {"domain": "accessibility", "method": "test_keyboard", "data": {"interactive_count": len(interactive), "tabindex_values": [int(t) for t in tabindex], "issues": issues, "pass": len(issues) == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TEST_KEYBOARD_ERROR", str(e), 0))

    def enable_screen_reader(self, params=None):
        params = params or {}
        try:
            enabled = params.get("enabled", True)
            self._screen_reader = bool(enabled)
            result = {"domain": "accessibility", "method": "enable_screen_reader", "data": {"enabled": self._screen_reader}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENABLE_SCREEN_READER_ERROR", str(e), 0))

    def validate_focus(self, params=None):
        params = params or {}
        try:
            html = params.get("html", "")
            focusable_tags = ["a", "button", "input", "select", "textarea", "[tabindex]"]
            count = 0
            for tag in focusable_tags:
                count += len(re.findall(rf"<{tag}[^>]*>", html, re.I))
            has_trap = bool(re.search(r"aria-modal|focus-trap", html, re.I))
            result = {"domain": "accessibility", "method": "validate_focus", "data": {"focusable_count": count, "has_focus_trap": has_trap, "valid": count > 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VALIDATE_FOCUS_ERROR", str(e), 0))

    def set_context(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            value = params.get("value")
            if key is None:
                return (0, None, ("SET_CONTEXT_ERROR", "missing key", 0))
            self._context[key] = value
            result = {"domain": "accessibility", "method": "set_context", "data": {"key": key, "value": value, "context_size": len(self._context)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SET_CONTEXT_ERROR", str(e), 0))

    def check_alt_text(self, params=None):
        params = params or {}
        try:
            html = params.get("html", "")
            imgs = re.findall(r"<img[^>]*>", html, re.I)
            results = []
            for img in imgs:
                alt_match = re.search(r'alt="([^"]*)"', img, re.I)
                alt = alt_match.group(1) if alt_match else None
                src_match = re.search(r'src="([^"]*)"', img, re.I)
                src = src_match.group(1) if src_match else ""
                results.append({"src": src, "alt": alt, "has_alt": alt is not None, "empty_alt": alt == ""})
            missing = sum(1 for r in results if not r["has_alt"])
            result = {"domain": "accessibility", "method": "check_alt_text", "data": {"images": results, "total": len(results), "missing_alt": missing, "pass": missing == 0}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECK_ALT_TEXT_ERROR", str(e), 0))

    def get_preferences(self, params=None):
        params = params or {}
        try:
            result = {"domain": "accessibility", "method": "get_preferences", "data": dict(self._preferences)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_PREFERENCES_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            summary = {
                "violations": len(self._violations),
                "screen_reader": self._screen_reader,
                "context_keys": list(self._context.keys()),
                "preferences": dict(self._preferences),
            }
            result = {"domain": "accessibility", "method": "report", "data": summary}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))
