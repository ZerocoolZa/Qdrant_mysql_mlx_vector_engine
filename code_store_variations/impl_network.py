class DomNetwork:
    """Network operations: sockets, HTTP, DNS, streaming, websockets."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "accept": self.accept,
            "delete": self.delete,
            "disconnect": self.disconnect,
            "download": self.download,
            "listen": self.listen,
            "patch": self.patch,
            "ping": self.ping,
            "poll": self.poll,
            "post": self.post,
            "put": self.put,
            "recv": self.recv,
            "resolve": self.resolve,
            "send": self.send,
            "stream": self.stream,
            "trace": self.trace,
            "upload": self.upload,
            "websocket": self.websocket,
        }
        handler = handlers.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def _http_request(self, method, url, headers=None, body=None, timeout=10):
        import urllib.request
        req = urllib.request.Request(url, data=body, method=method)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            return {"status": resp.status, "headers": dict(resp.headers), "body": data.decode("utf-8", "replace")}

    def accept(self, params=None):
        params = params or {}
        try:
            import socket
            host = params.get("host", "127.0.0.1")
            port = int(params.get("port", 0))
            backlog = int(params.get("backlog", 1))
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((host, port))
            srv.listen(backlog)
            srv.settimeout(float(params.get("timeout", 0.5)))
            bound = srv.getsockname()
            conn = None
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                addr = None
            finally:
                if conn:
                    conn.close()
                srv.close()
            result = {"domain": "network", "method": "accept", "data": {"host": bound[0], "port": bound[1], "peer": addr}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ACCEPT_ERROR", str(e), 0))

    def delete(self, params=None):
        params = params or {}
        try:
            url = params.get("url")
            if not url:
                return (0, None, ("DELETE_ERROR", "missing url", 0))
            resp = self._http_request("DELETE", url, params.get("headers"), None, int(params.get("timeout", 10)))
            result = {"domain": "network", "method": "delete", "data": resp}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DELETE_ERROR", str(e), 0))

    def disconnect(self, params=None):
        params = params or {}
        try:
            key = params.get("key", "default")
            conn = self.state["results"].pop(key, None) if isinstance(self.state.get("results"), dict) else None
            if conn and hasattr(conn, "close"):
                conn.close()
            result = {"domain": "network", "method": "disconnect", "data": {"key": key, "closed": conn is not None}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DISCONNECT_ERROR", str(e), 0))

    def download(self, params=None):
        params = params or {}
        try:
            import urllib.request
            url = params.get("url")
            if not url:
                return (0, None, ("DOWNLOAD_ERROR", "missing url", 0))
            dest = params.get("dest")
            with urllib.request.urlopen(url, timeout=int(params.get("timeout", 30))) as resp:
                data = resp.read()
            if dest:
                with open(dest, "wb") as f:
                    f.write(data)
            result = {"domain": "network", "method": "download", "data": {"bytes": len(data), "dest": dest, "body": data.decode("utf-8", "replace") if not dest else None}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DOWNLOAD_ERROR", str(e), 0))

    def listen(self, params=None):
        params = params or {}
        try:
            import socket
            host = params.get("host", "127.0.0.1")
            port = int(params.get("port", 0))
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((host, port))
            srv.listen(int(params.get("backlog", 5)))
            bound = srv.getsockname()
            srv.close()
            result = {"domain": "network", "method": "listen", "data": {"host": bound[0], "port": bound[1]}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LISTEN_ERROR", str(e), 0))

    def patch(self, params=None):
        params = params or {}
        try:
            url = params.get("url")
            if not url:
                return (0, None, ("PATCH_ERROR", "missing url", 0))
            body = params.get("body")
            if isinstance(body, (dict, list)):
                import json
                body = json.dumps(body).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            resp = self._http_request("PATCH", url, params.get("headers"), body, int(params.get("timeout", 10)))
            result = {"domain": "network", "method": "patch", "data": resp}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PATCH_ERROR", str(e), 0))

    def ping(self, params=None):
        params = params or {}
        try:
            import socket, time
            host = params.get("host", "127.0.0.1")
            port = int(params.get("port", 80))
            count = int(params.get("count", 3))
            timeout = float(params.get("timeout", 2))
            replies = []
            for _ in range(count):
                start = time.time()
                try:
                    s = socket.create_connection((host, port), timeout=timeout)
                    elapsed = round((time.time() - start) * 1000, 2)
                    replies.append({"ok": True, "ms": elapsed})
                    s.close()
                except Exception:
                    replies.append({"ok": False, "ms": None})
            ok_count = sum(1 for r in replies if r["ok"])
            result = {"domain": "network", "method": "ping", "data": {"host": host, "port": port, "replies": replies, "ok": ok_count, "total": count}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PING_ERROR", str(e), 0))

    def poll(self, params=None):
        params = params or {}
        try:
            import socket
            host = params.get("host", "127.0.0.1")
            port = int(params.get("port", 80))
            timeout = float(params.get("timeout", 2))
            try:
                s = socket.create_connection((host, port), timeout=timeout)
                s.close()
                reachable = True
            except Exception:
                reachable = False
            result = {"domain": "network", "method": "poll", "data": {"host": host, "port": port, "reachable": reachable}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("POLL_ERROR", str(e), 0))

    def post(self, params=None):
        params = params or {}
        try:
            url = params.get("url")
            if not url:
                return (0, None, ("POST_ERROR", "missing url", 0))
            body = params.get("body")
            if isinstance(body, (dict, list)):
                import json
                body = json.dumps(body).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            resp = self._http_request("POST", url, params.get("headers"), body, int(params.get("timeout", 10)))
            result = {"domain": "network", "method": "post", "data": resp}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("POST_ERROR", str(e), 0))

    def put(self, params=None):
        params = params or {}
        try:
            url = params.get("url")
            if not url:
                return (0, None, ("PUT_ERROR", "missing url", 0))
            body = params.get("body")
            if isinstance(body, (dict, list)):
                import json
                body = json.dumps(body).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            resp = self._http_request("PUT", url, params.get("headers"), body, int(params.get("timeout", 10)))
            result = {"domain": "network", "method": "put", "data": resp}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PUT_ERROR", str(e), 0))

    def recv(self, params=None):
        params = params or {}
        try:
            import socket
            host = params.get("host", "127.0.0.1")
            port = int(params.get("port", 0))
            size = int(params.get("size", 1024))
            timeout = float(params.get("timeout", 1))
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((host, port))
            srv.listen(1)
            srv.settimeout(timeout)
            data = b""
            try:
                conn, _ = srv.accept()
                conn.settimeout(timeout)
                data = conn.recv(size)
                conn.close()
            except socket.timeout:
                data = b""
            finally:
                srv.close()
            result = {"domain": "network", "method": "recv", "data": {"bytes": len(data), "payload": data.decode("utf-8", "replace")}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RECV_ERROR", str(e), 0))

    def resolve(self, params=None):
        params = params or {}
        try:
            import socket
            hostname = params.get("host")
            if not hostname:
                return (0, None, ("RESOLVE_ERROR", "missing host", 0))
            info = socket.getaddrinfo(hostname, None)
            addrs = list({i[4][0] for i in info})
            result = {"domain": "network", "method": "resolve", "data": {"host": hostname, "addresses": addrs}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RESOLVE_ERROR", str(e), 0))

    def send(self, params=None):
        params = params or {}
        try:
            import socket
            host = params.get("host", "127.0.0.1")
            port = int(params.get("port", 0))
            message = params.get("message", "")
            timeout = float(params.get("timeout", 2))
            payload = message.encode("utf-8") if isinstance(message, str) else message
            sent = 0
            try:
                s = socket.create_connection((host, port), timeout=timeout)
                sent = s.send(payload)
                s.close()
            except Exception:
                sent = 0
            result = {"domain": "network", "method": "send", "data": {"host": host, "port": port, "sent": sent}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SEND_ERROR", str(e), 0))

    def stream(self, params=None):
        params = params or {}
        try:
            import urllib.request
            url = params.get("url")
            if not url:
                return (0, None, ("STREAM_ERROR", "missing url", 0))
            chunk_size = int(params.get("chunk_size", 4096))
            max_chunks = int(params.get("max_chunks", 10))
            chunks = []
            total = 0
            with urllib.request.urlopen(url, timeout=int(params.get("timeout", 30))) as resp:
                for _ in range(max_chunks):
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
            result = {"domain": "network", "method": "stream", "data": {"chunks": len(chunks), "bytes": total}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STREAM_ERROR", str(e), 0))

    def trace(self, params=None):
        params = params or {}
        try:
            import socket, time
            host = params.get("host", "127.0.0.1")
            port = int(params.get("port", 80))
            max_hops = int(params.get("max_hops", 8))
            timeout = float(params.get("timeout", 1))
            hops = []
            reached = False
            for ttl in range(1, max_hops + 1):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(timeout)
                try:
                    s.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
                except Exception:
                    pass
                start = time.time()
                try:
                    s.connect((host, port))
                    elapsed = round((time.time() - start) * 1000, 2)
                    hops.append({"ttl": ttl, "reached": True, "ms": elapsed})
                    reached = True
                    s.close()
                    break
                except Exception:
                    hops.append({"ttl": ttl, "reached": False, "ms": None})
                finally:
                    try:
                        s.close()
                    except Exception:
                        pass
            result = {"domain": "network", "method": "trace", "data": {"host": host, "hops": hops, "reached": reached}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TRACE_ERROR", str(e), 0))

    def upload(self, params=None):
        params = params or {}
        try:
            import urllib.request, json as _json
            url = params.get("url")
            if not url:
                return (0, None, ("UPLOAD_ERROR", "missing url", 0))
            path = params.get("path")
            data = open(path, "rb").read() if path else params.get("data", b"").encode("utf-8") if isinstance(params.get("data"), str) else params.get("data", b"")
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", params.get("content_type", "application/octet-stream"))
            with urllib.request.urlopen(req, timeout=int(params.get("timeout", 30))) as resp:
                resp_data = resp.read().decode("utf-8", "replace")
            result = {"domain": "network", "method": "upload", "data": {"status": resp.status, "bytes_sent": len(data), "response": resp_data}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("UPLOAD_ERROR", str(e), 0))

    def websocket(self, params=None):
        params = params or {}
        try:
            import socket, base64, os as _os
            host = params.get("host", "127.0.0.1")
            port = int(params.get("port", 80))
            path = params.get("path", "/")
            message = params.get("message", "")
            timeout = float(params.get("timeout", 2))
            key = base64.b64encode(_os.urandom(16)).decode("utf-8")
            handshake = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n\r\n"
            )
            upgraded = False
            try:
                s = socket.create_connection((host, port), timeout=timeout)
                s.send(handshake.encode("utf-8"))
                resp = s.recv(4096).decode("utf-8", "replace")
                upgraded = "101" in resp.split("\r\n")[0] if resp else False
                s.close()
            except Exception:
                upgraded = False
            result = {"domain": "network", "method": "websocket", "data": {"host": host, "port": port, "upgraded": upgraded, "message": message}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WEBSOCKET_ERROR", str(e), 0))
