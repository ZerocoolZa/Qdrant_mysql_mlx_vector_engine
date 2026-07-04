"""VBStyle domain implementation: localization.

i18n/l10n: locale management, translations, date/currency formatting, text direction.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import re
import time
import datetime


class DomLocalization:
    """i18n/l10n: locale management, translations, date/currency formatting, text direction."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        self._bundles = {}
        self._locale = "en_US"
        self._directions = {"ar": "rtl", "he": "rtl", "fa": "rtl", "ur": "rtl"}
        self._plural_rules = {
            "en": lambda n: 0 if n == 1 else 1,
            "ru": lambda n: 0 if n % 10 == 1 and n % 100 != 11 else (1 if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else 2),
            "fr": lambda n: 0 if n == 1 else 1,
            "zh": lambda n: 0,
            "ja": lambda n: 0,
        }

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "translate": self.translate,
            "format_date": self.format_date,
            "format_currency": self.format_currency,
            "detect_locale": self.detect_locale,
            "load_bundle": self.load_bundle,
            "set_locale": self.set_locale,
            "get_locale_metadata": self.get_locale_metadata,
            "set_text_direction": self.set_text_direction,
            "pluralize": self.pluralize,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def translate(self, params=None):
        params = params or {}
        try:
            key = params.get("key")
            if key is None:
                return (0, None, ("TRANSLATE_ERROR", "missing key", 0))
            locale = params.get("locale", self._locale)
            lang = locale.split("_")[0]
            bundle = self._bundles.get(lang) or self._bundles.get(locale) or {}
            text = bundle.get(key, params.get("fallback", key))
            substitutions = params.get("subs") or {}
            if substitutions:
                for k, v in substitutions.items():
                    text = text.replace("{" + k + "}", str(v))
            result = {"domain": "localization", "method": "translate", "data": {"key": key, "locale": locale, "text": text}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TRANSLATE_ERROR", str(e), 0))

    def format_date(self, params=None):
        params = params or {}
        try:
            ts = params.get("timestamp", time.time())
            locale = params.get("locale", self._locale)
            fmt = params.get("format", "long")
            dt = datetime.datetime.fromtimestamp(float(ts))
            lang = locale.split("_")[0]
            if fmt == "long":
                if lang == "en":
                    out = dt.strftime("%A, %B %d, %Y")
                elif lang == "de":
                    out = dt.strftime("%A, %d. %B %Y")
                elif lang == "zh" or lang == "ja":
                    out = dt.strftime("%Y年%m月%d日")
                elif lang == "fr":
                    out = dt.strftime("%A %d %B %Y")
                else:
                    out = dt.strftime("%Y-%m-%d")
            elif fmt == "short":
                if lang == "en":
                    out = dt.strftime("%m/%d/%Y")
                elif lang == "de":
                    out = dt.strftime("%d.%m.%Y")
                elif lang == "zh" or lang == "ja":
                    out = dt.strftime("%Y/%m/%d")
                else:
                    out = dt.strftime("%Y-%m-%d")
            elif fmt == "time":
                out = dt.strftime("%H:%M:%S")
            else:
                out = dt.strftime(fmt)
            result = {"domain": "localization", "method": "format_date", "data": {"timestamp": ts, "locale": locale, "format": fmt, "formatted": out}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FORMAT_DATE_ERROR", str(e), 0))

    def format_currency(self, params=None):
        params = params or {}
        try:
            amount = float(params.get("amount", 0))
            locale = params.get("locale", self._locale)
            currency = params.get("currency", "USD")
            symbols = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥", "RUB": "₽"}
            symbol = symbols.get(currency, currency + " ")
            lang = locale.split("_")[0]
            if currency in ("JPY", "KRW", "VND"):
                formatted = f"{symbol}{int(round(amount))}"
            elif lang == "de":
                formatted = f"{symbol}{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            elif lang in ("fr", "ru"):
                formatted = f"{symbol}{amount:,.2f}".replace(",", " ").replace(".", ",")
            else:
                formatted = f"{symbol}{amount:,.2f}"
            result = {"domain": "localization", "method": "format_currency", "data": {"amount": amount, "currency": currency, "locale": locale, "formatted": formatted}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FORMAT_CURRENCY_ERROR", str(e), 0))

    def detect_locale(self, params=None):
        params = params or {}
        try:
            accept = params.get("accept_language", "")
            candidates = []
            for part in accept.split(","):
                part = part.strip()
                if not part:
                    continue
                m = re.match(r"([a-zA-Z]{2,3})(?:-[a-zA-Z]{2,4})?(?:;q=([0-9.]+))?", part)
                if m:
                    lang = m.group(1).lower()
                    q = float(m.group(2)) if m.group(2) else 1.0
                    candidates.append((lang, q))
            candidates.sort(key=lambda x: x[1], reverse=True)
            detected = candidates[0][0] if candidates else "en"
            locale = detected + "_" + (params.get("region", "US") if detected == "en" else detected.upper())
            result = {"domain": "localization", "method": "detect_locale", "data": {"locale": locale, "language": detected, "candidates": [c[0] for c in candidates]}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DETECT_LOCALE_ERROR", str(e), 0))

    def load_bundle(self, params=None):
        params = params or {}
        try:
            locale = params.get("locale", self._locale)
            entries = params.get("entries") or {}
            if not isinstance(entries, dict):
                return (0, None, ("LOAD_BUNDLE_ERROR", "entries must be a dict", 0))
            self._bundles[locale] = dict(entries)
            count = len(self._bundles[locale])
            result = {"domain": "localization", "method": "load_bundle", "data": {"locale": locale, "count": count}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LOAD_BUNDLE_ERROR", str(e), 0))

    def set_locale(self, params=None):
        params = params or {}
        try:
            locale = params.get("locale")
            if not locale:
                return (0, None, ("SET_LOCALE_ERROR", "missing locale", 0))
            previous = self._locale
            self._locale = locale
            result = {"domain": "localization", "method": "set_locale", "data": {"locale": locale, "previous": previous}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SET_LOCALE_ERROR", str(e), 0))

    def get_locale_metadata(self, params=None):
        params = params or {}
        try:
            locale = params.get("locale", self._locale)
            lang = locale.split("_")[0]
            direction = self._directions.get(lang, "ltr")
            bundle = self._bundles.get(lang) or self._bundles.get(locale) or {}
            result = {"domain": "localization", "method": "get_locale_metadata", "data": {"locale": locale, "language": lang, "direction": direction, "bundle_size": len(bundle)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_LOCALE_METADATA_ERROR", str(e), 0))

    def set_text_direction(self, params=None):
        params = params or {}
        try:
            locale = params.get("locale", self._locale)
            direction = params.get("direction")
            if direction not in ("ltr", "rtl"):
                return (0, None, ("SET_TEXT_DIRECTION_ERROR", "direction must be ltr or rtl", 0))
            lang = locale.split("_")[0]
            self._directions[lang] = direction
            result = {"domain": "localization", "method": "set_text_direction", "data": {"locale": locale, "language": lang, "direction": direction}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SET_TEXT_DIRECTION_ERROR", str(e), 0))

    def pluralize(self, params=None):
        params = params or {}
        try:
            count = int(params.get("count", 0))
            locale = params.get("locale", self._locale)
            lang = locale.split("_")[0]
            rule = self._plural_rules.get(lang, self._plural_rules["en"])
            form_index = rule(count)
            forms = params.get("forms") or ["one", "other", "many"]
            form = forms[form_index] if form_index < len(forms) else forms[-1]
            result = {"domain": "localization", "method": "pluralize", "data": {"count": count, "locale": locale, "form": form, "form_index": form_index}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PLURALIZE_ERROR", str(e), 0))
