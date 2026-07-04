"""VBStyle domain implementation: security.

Authentication, authorization, hashing, encryption, token management.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import hashlib
import hmac
import base64
import os
import secrets
import time
import json


class DomSecurity:
    """Security domain: auth, crypto, tokens, policies."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "authenticate": self.authenticate,
            "authorize": self.authorize,
            "decrypt": self.decrypt,
            "encrypt": self.encrypt,
            "hash": self.hash,
            "lockout": self.lockout,
            "permission": self.permission,
            "policy": self.policy,
            "refresh_token": self.refresh_token,
            "revoke": self.revoke,
            "role": self.role,
            "sign": self.sign,
            "token": self.token,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def authenticate(self, params=None):
        params = params or {}
        try:
            username = params.get("username") or ""
            password = params.get("password") or ""
            store = self.state.setdefault("config", {}).setdefault("users", {})
            record = store.get(username)
            ok = False
            if record:
                digest = hashlib.sha256(password.encode()).hexdigest()
                ok = hmac.compare_digest(digest, record.get("password", ""))
            result = {"domain": "security", "method": "authenticate", "data": {"authenticated": ok, "username": username}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("AUTHENTICATE_ERROR", str(e), 0))

    def authorize(self, params=None):
        params = params or {}
        try:
            user = params.get("user") or ""
            action = params.get("action") or ""
            acl = self.state.setdefault("config", {}).setdefault("acl", {})
            roles = acl.get(user, [])
            allowed = action in roles
            result = {"domain": "security", "method": "authorize", "data": {"authorized": allowed, "user": user, "action": action}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("AUTHORIZE_ERROR", str(e), 0))

    def decrypt(self, params=None):
        params = params or {}
        try:
            ciphertext = params.get("ciphertext") or ""
            key = (params.get("key") or "default-key").encode()
            raw = base64.b64decode(ciphertext) if ciphertext else b""
            if not raw:
                result = {"domain": "security", "method": "decrypt", "data": {"plaintext": ""}}
                return (1, result, None)
            keystream = bytes((key[i % len(key)] ^ raw[i]) for i in range(len(raw)))
            plaintext = keystream.decode("utf-8", errors="replace")
            result = {"domain": "security", "method": "decrypt", "data": {"plaintext": plaintext}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DECRYPT_ERROR", str(e), 0))

    def encrypt(self, params=None):
        params = params or {}
        try:
            plaintext = params.get("plaintext") or ""
            key = (params.get("key") or "default-key").encode()
            data = plaintext.encode("utf-8")
            keystream = bytes((key[i % len(key)] ^ data[i]) for i in range(len(data)))
            ciphertext = base64.b64encode(keystream).decode("ascii")
            result = {"domain": "security", "method": "encrypt", "data": {"ciphertext": ciphertext}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENCRYPT_ERROR", str(e), 0))

    def hash(self, params=None):
        params = params or {}
        try:
            data = (params.get("data") or "").encode("utf-8")
            algo = (params.get("algorithm") or "sha256").lower()
            if algo not in hashlib.algorithms_available:
                result = {"domain": "security", "method": "hash", "data": {"algorithm": algo, "available": False}}
                return (1, result, None)
            digest = hashlib.new(algo, data).hexdigest()
            result = {"domain": "security", "method": "hash", "data": {"algorithm": algo, "digest": digest}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HASH_ERROR", str(e), 0))

    def lockout(self, params=None):
        params = params or {}
        try:
            user = params.get("user") or ""
            threshold = int(params.get("threshold", 5))
            window = int(params.get("window", 300))
            attempts = self.state.setdefault("config", {}).setdefault("attempts", {})
            now = time.time()
            rec = attempts.setdefault(user, {"count": 0, "first": now})
            if now - rec["first"] > window:
                rec["count"] = 0
                rec["first"] = now
            rec["count"] += 1
            locked = rec["count"] >= threshold
            result = {"domain": "security", "method": "lockout", "data": {"user": user, "attempts": rec["count"], "locked": locked}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LOCKOUT_ERROR", str(e), 0))

    def permission(self, params=None):
        params = params or {}
        try:
            resource = params.get("resource") or ""
            action = params.get("action") or "read"
            subject = params.get("subject") or ""
            perms = self.state.setdefault("config", {}).setdefault("permissions", {})
            key = f"{subject}:{resource}"
            if params.get("grant"):
                perms[key] = action
            granted = perms.get(key) == action
            result = {"domain": "security", "method": "permission", "data": {"subject": subject, "resource": resource, "action": action, "granted": granted}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PERMISSION_ERROR", str(e), 0))

    def policy(self, params=None):
        params = params or {}
        try:
            name = params.get("name") or ""
            rules = params.get("rules") or []
            policies = self.state.setdefault("config", {}).setdefault("policies", {})
            if name and rules:
                policies[name] = rules
            result = {"domain": "security", "method": "policy", "data": {"policies": dict(policies), "count": len(policies)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("POLICY_ERROR", str(e), 0))

    def refresh_token(self, params=None):
        params = params or {}
        try:
            old = params.get("token") or ""
            tokens = self.state.setdefault("config", {}).setdefault("tokens", {})
            if old not in tokens:
                result = {"domain": "security", "method": "refresh_token", "data": {"refreshed": False, "reason": "not_found"}}
                return (1, result, None)
            new = secrets.token_urlsafe(32)
            tokens[new] = {"issued": time.time(), "ttl": int(params.get("ttl", 3600))}
            del tokens[old]
            result = {"domain": "security", "method": "refresh_token", "data": {"refreshed": True, "token": new}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REFRESH_TOKEN_ERROR", str(e), 0))

    def revoke(self, params=None):
        params = params or {}
        try:
            token = params.get("token") or ""
            tokens = self.state.setdefault("config", {}).setdefault("tokens", {})
            existed = token in tokens
            if existed:
                del tokens[token]
            result = {"domain": "security", "method": "revoke", "data": {"revoked": existed, "token": token}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REVOKE_ERROR", str(e), 0))

    def role(self, params=None):
        params = params or {}
        try:
            user = params.get("user") or ""
            role = params.get("role")
            roles = self.state.setdefault("config", {}).setdefault("roles", {})
            if role:
                roles[user] = role
            current = roles.get(user)
            result = {"domain": "security", "method": "role", "data": {"user": user, "role": current, "roles": dict(roles)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ROLE_ERROR", str(e), 0))

    def sign(self, params=None):
        params = params or {}
        try:
            payload = (params.get("payload") or "").encode("utf-8")
            key = (params.get("key") or "secret").encode("utf-8")
            mac = hmac.new(key, payload, hashlib.sha256).hexdigest()
            result = {"domain": "security", "method": "sign", "data": {"signature": mac, "algorithm": "HMAC-SHA256"}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SIGN_ERROR", str(e), 0))

    def token(self, params=None):
        params = params or {}
        try:
            subject = params.get("subject") or ""
            ttl = int(params.get("ttl", 3600))
            value = secrets.token_urlsafe(32)
            issued = time.time()
            body = {"sub": subject, "iat": issued, "exp": issued + ttl}
            encoded = base64.urlsafe_b64encode(json.dumps(body, sort_keys=True).encode()).decode().rstrip("=")
            tokens = self.state.setdefault("config", {}).setdefault("tokens", {})
            tokens[value] = body
            result = {"domain": "security", "method": "token", "data": {"token": value, "payload": encoded, "ttl": ttl}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TOKEN_ERROR", str(e), 0))
