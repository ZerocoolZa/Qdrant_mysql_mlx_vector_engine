class DomArchive:
    """Archive operations: compress, decompress, encrypt, decrypt, split, join, create."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "compress": self.compress,
            "create": self.create,
            "decompress": self.decompress,
            "decrypt": self.decrypt,
            "encrypt": self.encrypt,
            "join": self.join,
            "split": self.split,
        }
        handler = handlers.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def compress(self, params=None):
        params = params or {}
        try:
            import zlib, base64
            data = params.get("data", "")
            if isinstance(data, str):
                data = data.encode("utf-8")
            level = int(params.get("level", 6))
            compressed = zlib.compress(data, level)
            encoded = base64.b64encode(compressed).decode("ascii")
            result = {"domain": "archive", "method": "compress", "data": {"original_bytes": len(data), "compressed_bytes": len(compressed), "encoded": encoded, "ratio": round(len(compressed) / max(len(data), 1), 4)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPRESS_ERROR", str(e), 0))

    def create(self, params=None):
        params = params or {}
        try:
            import json, zlib, base64
            name = params.get("name", "archive")
            files = params.get("files", {})
            manifest = {"name": name, "files": list(files.keys()), "count": len(files)}
            payload = {}
            for fname, content in files.items():
                if isinstance(content, str):
                    content = content.encode("utf-8")
                payload[fname] = base64.b64encode(zlib.compress(content)).decode("ascii")
            archive = json.dumps({"manifest": manifest, "payload": payload})
            result = {"domain": "archive", "method": "create", "data": {"name": name, "manifest": manifest, "archive": archive, "size": len(archive)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CREATE_ERROR", str(e), 0))

    def decompress(self, params=None):
        params = params or {}
        try:
            import zlib, base64
            encoded = params.get("encoded", "")
            compressed = base64.b64decode(encoded)
            data = zlib.decompress(compressed)
            text = data.decode("utf-8", "replace")
            result = {"domain": "archive", "method": "decompress", "data": {"bytes": len(data), "text": text}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DECOMPRESS_ERROR", str(e), 0))

    def decrypt(self, params=None):
        params = params or {}
        try:
            import base64
            data = params.get("data", "")
            key = params.get("key", "")
            if isinstance(data, str):
                data = data.encode("utf-8")
            key_bytes = key.encode("utf-8") if isinstance(key, str) else key
            decoded = base64.b64decode(data)
            out = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(decoded)) if key_bytes else decoded
            text = out.decode("utf-8", "replace")
            result = {"domain": "archive", "method": "decrypt", "data": {"bytes": len(out), "text": text}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DECRYPT_ERROR", str(e), 0))

    def encrypt(self, params=None):
        params = params or {}
        try:
            import base64
            data = params.get("data", "")
            key = params.get("key", "")
            if isinstance(data, str):
                data = data.encode("utf-8")
            key_bytes = key.encode("utf-8") if isinstance(key, str) else key
            if not key_bytes:
                return (0, None, ("ENCRYPT_ERROR", "missing key", 0))
            xored = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data))
            encoded = base64.b64encode(xored).decode("ascii")
            result = {"domain": "archive", "method": "encrypt", "data": {"bytes": len(xored), "encoded": encoded}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENCRYPT_ERROR", str(e), 0))

    def join(self, params=None):
        params = params or {}
        try:
            parts = params.get("parts", [])
            combined = b""
            for p in parts:
                if isinstance(p, str):
                    combined += p.encode("utf-8")
                elif isinstance(p, (bytes, bytearray)):
                    combined += bytes(p)
            result = {"domain": "archive", "method": "join", "data": {"parts": len(parts), "bytes": len(combined), "text": combined.decode("utf-8", "replace")}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("JOIN_ERROR", str(e), 0))

    def split(self, params=None):
        params = params or {}
        try:
            import base64
            data = params.get("data", "")
            if isinstance(data, str):
                data = data.encode("utf-8")
            chunk_size = int(params.get("chunk_size", 1024))
            if chunk_size <= 0:
                return (0, None, ("SPLIT_ERROR", "invalid chunk_size", 0))
            parts = [base64.b64encode(data[i:i + chunk_size]).decode("ascii") for i in range(0, len(data), chunk_size)]
            result = {"domain": "archive", "method": "split", "data": {"parts": parts, "count": len(parts), "total_bytes": len(data)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SPLIT_ERROR", str(e), 0))
