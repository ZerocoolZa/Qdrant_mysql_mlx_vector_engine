"""VBStyle domain implementation: http.

HTTP protocol: status codes, headers, CORS, content negotiation, caching.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import re
import time
import uuid
from http.cookies import SimpleCookie


class DomHttp:
    """HTTP domain: status, headers, CORS, content negotiation, caching, cookies, request/response handling."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "response": {"status": 200, "headers": {}, "body": None, "cookies": {}},
            "request": {"method": "GET", "path": "/", "headers": {}, "query": {}, "body": None, "cookies": {}},
        }
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "set_status": self.set_status,
            "set_header": self.set_header,
            "get_header": self.get_header,
            "negotiate_content": self.negotiate_content,
            "handle_cors": self.handle_cors,
            "set_cache_control": self.set_cache_control,
            "parse_request": self.parse_request,
            "serialize_response": self.serialize_response,
            "redirect": self.redirect,
            "set_cookie": self.set_cookie,
            "get_cookie": self.get_cookie,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def set_status(self, params=None):
        params = params or {}
        try:
            code = int(params.get("code", 200))
            if code < 100 or code > 599:
                return (0, None, ("INVALID_STATUS", f"Invalid status code: {code}", 0))
            self.state["response"]["status"] = code
            result = {"domain": "http", "method": "set_status", "data": {"status": code}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SET_STATUS_ERROR", str(e), 0))

    def set_header(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            value = params.get("value")
            if not name:
                return (0, None, ("HEADER_NAME_REQUIRED", "name required", 0))
            self.state["response"]["headers"][name] = value
            result = {"domain": "http", "method": "set_header", "data": {"name": name, "value": value}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SET_HEADER_ERROR", str(e), 0))

    def get_header(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("HEADER_NAME_REQUIRED", "name required", 0))
            source = params.get("source", "response")
            headers = self.state["response"]["headers"] if source == "response" else self.state["request"]["headers"]
            value = headers.get(name)
            found = value is not None
            result = {"domain": "http", "method": "get_header", "data": {"name": name, "value": value, "found": found}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_HEADER_ERROR", str(e), 0))

    def negotiate_content(self, params=None):
        params = params or {}
        try:
            accept = params.get("accept", "*/*")
            supported = params.get("supported") or ["application/json", "text/html", "text/plain"]
            accept_parts = [a.split(";")[0].strip() for a in accept.split(",")]
            chosen = None
            for a in accept_parts:
                if a in supported:
                    chosen = a
                    break
            if chosen is None and "*/*" in accept_parts:
                chosen = supported[0]
            if chosen is None:
                return (0, None, ("NOT_ACCEPTABLE", f"Cannot negotiate among {supported}", 0))
            self.state["response"]["headers"]["Content-Type"] = chosen
            result = {"domain": "http", "method": "negotiate_content", "data": {"content_type": chosen, "accept": accept}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("NEGOTIATE_CONTENT_ERROR", str(e), 0))

    def handle_cors(self, params=None):
        params = params or {}
        try:
            origin = params.get("origin", "*")
            methods = params.get("methods") or ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
            headers = params.get("headers") or ["Content-Type", "Authorization"]
            max_age = int(params.get("max_age", 3600))
            creds = bool(params.get("credentials", False))
            self.state["response"]["headers"]["Access-Control-Allow-Origin"] = origin
            self.state["response"]["headers"]["Access-Control-Allow-Methods"] = ", ".join(methods)
            self.state["response"]["headers"]["Access-Control-Allow-Headers"] = ", ".join(headers)
            self.state["response"]["headers"]["Access-Control-Max-Age"] = str(max_age)
            if creds:
                self.state["response"]["headers"]["Access-Control-Allow-Credentials"] = "true"
            result = {
                "domain": "http",
                "method": "handle_cors",
                "data": {"origin": origin, "methods": methods, "credentials": creds},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HANDLE_CORS_ERROR", str(e), 0))

    def set_cache_control(self, params=None):
        params = params or {}
        try:
            directives = []
            max_age = params.get("max_age")
            if max_age is not None:
                directives.append(f"max-age={int(max_age)}")
            if params.get("public"):
                directives.append("public")
            if params.get("private"):
                directives.append("private")
            if params.get("no_cache"):
                directives.append("no-cache")
            if params.get("no_store"):
                directives.append("no-store")
            if params.get("must_revalidate"):
                directives.append("must-revalidate")
            value = ", ".join(directives) if directives else "no-cache"
            self.state["response"]["headers"]["Cache-Control"] = value
            result = {"domain": "http", "method": "set_cache_control", "data": {"cache_control": value}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SET_CACHE_CONTROL_ERROR", str(e), 0))

    def parse_request(self, params=None):
        params = params or {}
        try:
            raw = params.get("raw") or ""
            method = "GET"
            path = "/"
            headers = {}
            body = None
            lines = raw.split("\r\n") if "\r\n" in raw else raw.split("\n")
            if lines and lines[0]:
                parts = lines[0].split(" ")
                if len(parts) >= 2:
                    method = parts[0]
                    path = parts[1]
            for line in lines[1:]:
                if not line.strip():
                    break
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip()] = v.strip()
            if "?" in path:
                path, query_str = path.split("?", 1)
            body_idx = raw.find("\r\n\r\n")
            if body_idx == -1:
                body_idx = raw.find("\n\n")
            if body_idx != -1:
                body = raw[body_idx:].strip() or None
            self.state["request"] = {
                "method": method,
                "path": path,
                "headers": headers,
                "query": {},
                "body": body,
                "cookies": {},
            }
            result = {
                "domain": "http",
                "method": "parse_request",
                "data": {"method": method, "path": path, "headers": headers, "has_body": body is not None},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PARSE_REQUEST_ERROR", str(e), 0))

    def serialize_response(self, params=None):
        params = params or {}
        try:
            status = self.state["response"]["status"]
            headers = self.state["response"]["headers"]
            body = params.get("body", self.state["response"]["body"])
            if body is not None and not isinstance(body, str):
                body = str(body)
            header_lines = [f"{k}: {v}" for k, v in headers.items()]
            status_line = f"HTTP/1.1 {status}"
            serialized = status_line
            if header_lines:
                serialized += "\r\n" + "\r\n".join(header_lines)
            if body is not None:
                serialized += "\r\n\r\n" + body
            result = {
                "domain": "http",
                "method": "serialize_response",
                "data": {"serialized": serialized, "status": status, "header_count": len(headers)},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SERIALIZE_RESPONSE_ERROR", str(e), 0))

    def redirect(self, params=None):
        params = params or {}
        try:
            url = params.get("url")
            if not url:
                return (0, None, ("URL_REQUIRED", "url required", 0))
            code = int(params.get("code", 302))
            if code not in (301, 302, 303, 307, 308):
                return (0, None, ("INVALID_REDIRECT_CODE", f"Invalid redirect code: {code}", 0))
            self.state["response"]["status"] = code
            self.state["response"]["headers"]["Location"] = url
            result = {"domain": "http", "method": "redirect", "data": {"url": url, "code": code}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REDIRECT_ERROR", str(e), 0))

    def set_cookie(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            value = params.get("value", "")
            if not name:
                return (0, None, ("COOKIE_NAME_REQUIRED", "name required", 0))
            cookie = SimpleCookie()
            cookie[name] = value
            if params.get("path"):
                cookie[name]["path"] = params["path"]
            if params.get("domain"):
                cookie[name]["domain"] = params["domain"]
            if params.get("max_age") is not None:
                cookie[name]["max-age"] = int(params["max_age"])
            if params.get("secure"):
                cookie[name]["secure"] = True
            if params.get("http_only"):
                cookie[name]["httponly"] = True
            self.state["response"]["cookies"][name] = value
            header_value = cookie.output(header="").strip()
            existing = self.state["response"]["headers"].get("Set-Cookie")
            if existing:
                self.state["response"]["headers"]["Set-Cookie"] = existing + ", " + header_value
            else:
                self.state["response"]["headers"]["Set-Cookie"] = header_value
            result = {"domain": "http", "method": "set_cookie", "data": {"name": name, "value": value}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SET_COOKIE_ERROR", str(e), 0))

    def get_cookie(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("COOKIE_NAME_REQUIRED", "name required", 0))
            cookie_header = params.get("cookie_header") or self.state["request"]["headers"].get("Cookie", "")
            cookie = SimpleCookie()
            if cookie_header:
                cookie.load(cookie_header)
            value = cookie.get(name)
            found = value is not None
            result = {
                "domain": "http",
                "method": "get_cookie",
                "data": {"name": name, "value": value.value if found else None, "found": found},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GET_COOKIE_ERROR", str(e), 0))
