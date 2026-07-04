"""VBStyle domain implementation: cryptography.

Encryption/signing: symmetric, asymmetric, hashing, key derivation, PBKDF2.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import hashlib
import hmac
import base64
import secrets
import os
import struct
import time


class DomCryptography:
    """Cryptography domain: encrypt, decrypt, hash, sign, verify, keys."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "encrypt": self.encrypt,
            "decrypt": self.decrypt,
            "hash": self.hash,
            "sign": self.sign,
            "verify": self.verify,
            "generate_keys": self.generate_keys,
            "derive_key": self.derive_key,
            "random_bytes": self.random_bytes,
            "compare_digest": self.compare_digest,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _coerce_bytes(self, value):
        if isinstance(value, str):
            return value.encode("utf-8")
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        return str(value).encode("utf-8")

    def _xor_bytes(self, a, b):
        return bytes(x ^ y for x, y in zip(a, b))

    def _keystream(self, key, nonce, length):
        out = bytearray()
        counter = 0
        while len(out) < length:
            block = hashlib.sha256(key + nonce + struct.pack(">Q", counter)).digest()
            out += block
            counter += 1
        return bytes(out[:length])

    def encrypt(self, params=None):
        params = params or {}
        try:
            plaintext = self._coerce_bytes(params.get("plaintext", b""))
            key = self._coerce_bytes(params.get("key", b""))
            if not key:
                key = secrets.token_bytes(32)
            nonce = secrets.token_bytes(16)
            stream = self._keystream(key, nonce, len(plaintext))
            ciphertext = self._xor_bytes(plaintext, stream)
            mac = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
            payload = nonce + ciphertext + mac
            result = {"domain": "cryptography", "method": "encrypt", "data": {"ciphertext": payload, "nonce": nonce, "mac": mac, "key": key, "size": len(payload)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENCRYPT_ERROR", str(e), 0))

    def decrypt(self, params=None):
        params = params or {}
        try:
            payload = self._coerce_bytes(params.get("ciphertext", b""))
            key = self._coerce_bytes(params.get("key", b""))
            if len(payload) < 16 + 32:
                return (0, None, ("DECRYPT_ERROR", "payload too short", 0))
            nonce = payload[:16]
            mac = payload[-32:]
            ciphertext = payload[16:-32]
            expected_mac = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
            if not hmac.compare_digest(mac, expected_mac):
                return (0, None, ("DECRYPT_ERROR", "mac verification failed", 0))
            stream = self._keystream(key, nonce, len(ciphertext))
            plaintext = self._xor_bytes(ciphertext, stream)
            result = {"domain": "cryptography", "method": "decrypt", "data": {"plaintext": plaintext, "size": len(plaintext)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DECRYPT_ERROR", str(e), 0))

    def hash(self, params=None):
        params = params or {}
        try:
            data = self._coerce_bytes(params.get("data", b""))
            algorithm = params.get("algorithm", "sha256")
            if algorithm == "md5":
                digest = hashlib.md5(data).digest()
            elif algorithm == "sha1":
                digest = hashlib.sha1(data).digest()
            elif algorithm == "sha256":
                digest = hashlib.sha256(data).digest()
            elif algorithm == "sha512":
                digest = hashlib.sha512(data).digest()
            elif algorithm == "blake2b":
                digest = hashlib.blake2b(data).digest()
            else:
                return (0, None, ("HASH_ERROR", f"unknown algorithm: {algorithm}", 0))
            hexdigest = digest.hex()
            result = {"domain": "cryptography", "method": "hash", "data": {"digest": digest, "hexdigest": hexdigest, "algorithm": algorithm, "size": len(digest)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HASH_ERROR", str(e), 0))

    def sign(self, params=None):
        params = params or {}
        try:
            payload = self._coerce_bytes(params.get("payload", b""))
            key = self._coerce_bytes(params.get("key", b"secret"))
            algorithm = params.get("algorithm", "sha256")
            if algorithm not in ("sha256", "sha512", "blake2b"):
                return (0, None, ("SIGN_ERROR", f"unsupported algorithm: {algorithm}", 0))
            mac = hmac.new(key, payload, algorithm).digest()
            result = {"domain": "cryptography", "method": "sign", "data": {"signature": mac, "algorithm": algorithm, "size": len(mac)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SIGN_ERROR", str(e), 0))

    def verify(self, params=None):
        params = params or {}
        try:
            payload = self._coerce_bytes(params.get("payload", b""))
            signature = self._coerce_bytes(params.get("signature", b""))
            key = self._coerce_bytes(params.get("key", b"secret"))
            algorithm = params.get("algorithm", "sha256")
            if algorithm not in ("sha256", "sha512", "blake2b"):
                return (0, None, ("VERIFY_ERROR", f"unsupported algorithm: {algorithm}", 0))
            expected = hmac.new(key, payload, algorithm).digest()
            valid = hmac.compare_digest(expected, signature)
            result = {"domain": "cryptography", "method": "verify", "data": {"valid": valid, "algorithm": algorithm}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("VERIFY_ERROR", str(e), 0))

    def generate_keys(self, params=None):
        params = params or {}
        try:
            key_size = int(params.get("key_size", 32))
            count = int(params.get("count", 1))
            keys = [secrets.token_bytes(key_size) for _ in range(count)]
            encoded = [base64.b64encode(k).decode("ascii") for k in keys]
            result = {"domain": "cryptography", "method": "generate_keys", "data": {"keys": keys, "encoded": encoded, "count": count, "key_size": key_size}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GENERATE_KEYS_ERROR", str(e), 0))

    def derive_key(self, params=None):
        params = params or {}
        try:
            password = self._coerce_bytes(params.get("password", b""))
            salt = self._coerce_bytes(params.get("salt", b""))
            if not salt:
                salt = os.urandom(16)
            iterations = int(params.get("iterations", 100000))
            key_length = int(params.get("key_length", 32))
            algorithm = params.get("algorithm", "sha256")
            derived = hashlib.pbkdf2_hmac(algorithm, password, salt, iterations, dklen=key_length)
            result = {"domain": "cryptography", "method": "derive_key", "data": {"key": derived, "salt": salt, "iterations": iterations, "key_length": key_length, "algorithm": algorithm}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DERIVE_KEY_ERROR", str(e), 0))

    def random_bytes(self, params=None):
        params = params or {}
        try:
            count = int(params.get("count", 32))
            data = secrets.token_bytes(count)
            encoded = base64.b64encode(data).decode("ascii")
            hexstr = data.hex()
            result = {"domain": "cryptography", "method": "random_bytes", "data": {"bytes": data, "encoded": encoded, "hex": hexstr, "count": count}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RANDOM_BYTES_ERROR", str(e), 0))

    def compare_digest(self, params=None):
        params = params or {}
        try:
            a = self._coerce_bytes(params.get("a", b""))
            b = self._coerce_bytes(params.get("b", b""))
            match = hmac.compare_digest(a, b)
            same_length = len(a) == len(b)
            result = {"domain": "cryptography", "method": "compare_digest", "data": {"match": match, "same_length": same_length, "length_a": len(a), "length_b": len(b)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPARE_DIGEST_ERROR", str(e), 0))
