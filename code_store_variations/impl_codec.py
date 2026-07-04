import base64 as _b64
import hashlib
import json as _json
import urllib.parse as _url
import zlib


class DomCodec:
    """Encoding/decoding utilities: base64, hex, url, hash, checksum, compress, serialize."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "base64": self.base64,
            "checksum": self.checksum,
            "compress": self.compress,
            "decode": self.decode,
            "decompress": self.decompress,
            "deserialize": self.deserialize,
            "encode": self.encode,
            "hash": self.hash,
            "hex": self.hex,
            "serialize": self.serialize,
            "url_decode": self.url_decode,
            "url_encode": self.url_encode,
        }
        if command in handlers:
            return handlers[command](params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def _to_bytes(self, value):
        if isinstance(value, bytes):
            return value
        return str(value).encode("utf-8")

    def encode(self, params=None):
        params = params or {}
        try:
            value = params.get("value", "")
            scheme = params.get("scheme", "utf-8")
            data = self._to_bytes(value)
            if scheme == "base64":
                encoded = _b64.b64encode(data).decode("ascii")
            elif scheme == "hex":
                encoded = data.hex()
            elif scheme == "url":
                encoded = _url.quote(str(value))
            else:
                encoded = data.decode("utf-8")
            result = {"domain": "codec", "method": "encode", "data": {"encoded": encoded, "scheme": scheme}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENCODE_ERROR", str(e), 0))

    def decode(self, params=None):
        params = params or {}
        try:
            value = params.get("value", "")
            scheme = params.get("scheme", "utf-8")
            if scheme == "base64":
                decoded = _b64.b64decode(value).decode("utf-8")
            elif scheme == "hex":
                decoded = bytes.fromhex(value).decode("utf-8")
            elif scheme == "url":
                decoded = _url.unquote(str(value))
            else:
                decoded = str(value)
            result = {"domain": "codec", "method": "decode", "data": {"decoded": decoded, "scheme": scheme}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DECODE_ERROR", str(e), 0))

    def base64(self, params=None):
        params = params or {}
        try:
            value = params.get("value", "")
            action = params.get("action", "encode")
            if action == "decode":
                decoded = _b64.b64decode(value).decode("utf-8")
                result = {"domain": "codec", "method": "base64", "data": {"action": "decode", "result": decoded}}
            else:
                encoded = _b64.b64encode(self._to_bytes(value)).decode("ascii")
                result = {"domain": "codec", "method": "base64", "data": {"action": "encode", "result": encoded}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BASE64_ERROR", str(e), 0))

    def hex(self, params=None):
        params = params or {}
        try:
            value = params.get("value", "")
            action = params.get("action", "encode")
            if action == "decode":
                decoded = bytes.fromhex(value).decode("utf-8")
                result = {"domain": "codec", "method": "hex", "data": {"action": "decode", "result": decoded}}
            else:
                encoded = self._to_bytes(value).hex()
                result = {"domain": "codec", "method": "hex", "data": {"action": "encode", "result": encoded}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HEX_ERROR", str(e), 0))

    def url_encode(self, params=None):
        params = params or {}
        try:
            value = params.get("value", "")
            encoded = _url.quote(str(value))
            result = {"domain": "codec", "method": "url_encode", "data": {"encoded": encoded}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("URL_ENCODE_ERROR", str(e), 0))

    def url_decode(self, params=None):
        params = params or {}
        try:
            value = params.get("value", "")
            decoded = _url.unquote(str(value))
            result = {"domain": "codec", "method": "url_decode", "data": {"decoded": decoded}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("URL_DECODE_ERROR", str(e), 0))

    def hash(self, params=None):
        params = params or {}
        try:
            value = params.get("value", "")
            algo = params.get("algo", "sha256")
            data = self._to_bytes(value)
            if algo == "md5":
                digest = hashlib.md5(data).hexdigest()
            elif algo == "sha1":
                digest = hashlib.sha1(data).hexdigest()
            elif algo == "sha512":
                digest = hashlib.sha512(data).hexdigest()
            else:
                digest = hashlib.sha256(data).hexdigest()
            result = {"domain": "codec", "method": "hash", "data": {"algo": algo, "digest": digest}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HASH_ERROR", str(e), 0))

    def checksum(self, params=None):
        params = params or {}
        try:
            value = params.get("value", "")
            data = self._to_bytes(value)
            crc = zlib.crc32(data) & 0xFFFFFFFF
            result = {"domain": "codec", "method": "checksum", "data": {"crc32": crc, "size": len(data)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECKSUM_ERROR", str(e), 0))

    def compress(self, params=None):
        params = params or {}
        try:
            value = params.get("value", "")
            data = self._to_bytes(value)
            compressed = zlib.compress(data)
            result = {"domain": "codec", "method": "compress", "data": {"compressed": compressed, "original_size": len(data), "compressed_size": len(compressed)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPRESS_ERROR", str(e), 0))

    def decompress(self, params=None):
        params = params or {}
        try:
            value = params.get("value", b"")
            if isinstance(value, str):
                value = value.encode("latin-1")
            decompressed = zlib.decompress(value).decode("utf-8")
            result = {"domain": "codec", "method": "decompress", "data": {"decompressed": decompressed, "size": len(decompressed)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DECOMPRESS_ERROR", str(e), 0))

    def serialize(self, params=None):
        params = params or {}
        try:
            value = params.get("value")
            data = _json.dumps(value, default=str)
            result = {"domain": "codec", "method": "serialize", "data": {"serialized": data, "size": len(data)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SERIALIZE_ERROR", str(e), 0))

    def deserialize(self, params=None):
        params = params or {}
        try:
            value = params.get("value", "")
            data = _json.loads(value)
            result = {"domain": "codec", "method": "deserialize", "data": {"deserialized": data}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DESERIALIZE_ERROR", str(e), 0))
