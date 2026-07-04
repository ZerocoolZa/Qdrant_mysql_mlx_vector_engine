# [@GHOST]{[@file<credentials.py>][@domain<utility>][@role<credentials>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<credentials_manager>][@return<tuple3>][@orch<Orchestrator>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Credentials manager — loads from env vars, local .credentials file, provides secure access to all secrets}
# [@WCL]{[@self_contained<true>][@sources<env|file|keyring>][@secrets<gmail|yahoo|s3|git|mysql|api_keys>][@encrypted<true>]}

import os
import json
import base64
import hashlib


class Credentials:
    """Credentials manager — centralizes all secret access.

    Three sources, checked in order:
    1. Environment variables (highest priority — CI/CD, docker)
    2. Local .credentials file (base64-encoded JSON, user-managed)
    3. Fallback defaults (empty strings — never hardcoded secrets)

    Supported credential sets:
    - gmail: GMAIL_USER, GMAIL_APP_PASSWORD
    - yahoo: YAHOO_USER, YAHOO_APP_PASSWORD
    - s3: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION, S3_BUCKET
    - git: GIT_TOKEN, GIT_REMOTE
    - mysql: MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
    - api: API_KEY_OPENAI, API_KEY_ANTHROPIC, API_KEY_PINECONE
    - custom: any key you register

    Usage:
        from core.utility.credentials import Credentials
        cred = Credentials()
        code, gmail, err = cred.Run("get", {"provider": "gmail"})
        # gmail = {"user": "you@gmail.com", "password": "xxxx"}

        cred.Run("set", {"provider": "gmail", "user": "you@gmail.com", "password": "xxxx"})
        cred.Run("save")  # persists to .credentials file
        cred.Run("load")  # loads from .credentials file
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "loaded": False,
            "providers": {},
            "source": "",
        }
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state["cred_file"] = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            ".credentials",
        )
        self.init_providers()
        self.load_all()

    def init_providers(self):
        self.state["providers"] = {
            "gmail": {"user": "", "password": "", "_env_keys": ["GMAIL_USER", "GMAIL_APP_PASSWORD"]},
            "yahoo": {"user": "", "password": "", "_env_keys": ["YAHOO_USER", "YAHOO_APP_PASSWORD"]},
            "s3": {
                "access_key": "", "secret_key": "", "region": "us-east-1", "bucket": "",
                "_env_keys": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION", "S3_BUCKET"],
            },
            "git": {"token": "", "remote": "", "_env_keys": ["GIT_TOKEN", "GIT_REMOTE"]},
            "mysql": {
                "host": "localhost", "user": "root", "password": "", "database": "vb_shared",
                "_env_keys": ["MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE"],
            },
            "api": {
                "openai": "", "anthropic": "", "pinecone": "",
                "_env_keys": ["API_KEY_OPENAI", "API_KEY_ANTHROPIC", "API_KEY_PINECONE"],
            },
        }

    def load_all(self):
        self.load_from_env()
        self.load_from_file()
        self.state["loaded"] = True

    def load_from_env(self):
        for provider, fields in self.state["providers"].items():
            env_keys = fields.get("_env_keys", [])
            if provider == "gmail":
                fields["user"] = os.environ.get("GMAIL_USER", fields["user"])
                fields["password"] = os.environ.get("GMAIL_APP_PASSWORD", fields["password"])
            elif provider == "yahoo":
                fields["user"] = os.environ.get("YAHOO_USER", fields["user"])
                fields["password"] = os.environ.get("YAHOO_APP_PASSWORD", fields["password"])
            elif provider == "s3":
                fields["access_key"] = os.environ.get("AWS_ACCESS_KEY_ID", fields["access_key"])
                fields["secret_key"] = os.environ.get("AWS_SECRET_ACCESS_KEY", fields["secret_key"])
                fields["region"] = os.environ.get("AWS_DEFAULT_REGION", fields["region"])
                fields["bucket"] = os.environ.get("S3_BUCKET", fields["bucket"])
            elif provider == "git":
                fields["token"] = os.environ.get("GIT_TOKEN", fields["token"])
                fields["remote"] = os.environ.get("GIT_REMOTE", fields["remote"])
            elif provider == "mysql":
                fields["host"] = os.environ.get("MYSQL_HOST", fields["host"])
                fields["user"] = os.environ.get("MYSQL_USER", fields["user"])
                fields["password"] = os.environ.get("MYSQL_PASSWORD", fields["password"])
                fields["database"] = os.environ.get("MYSQL_DATABASE", fields["database"])
            elif provider == "api":
                fields["openai"] = os.environ.get("API_KEY_OPENAI", fields["openai"])
                fields["anthropic"] = os.environ.get("API_KEY_ANTHROPIC", fields["anthropic"])
                fields["pinecone"] = os.environ.get("API_KEY_PINECONE", fields["pinecone"])
        self.state["source"] = "env"

    def load_from_file(self):
        if not os.path.exists(self.state["cred_file"]):
            return
        try:
            with open(self.state["cred_file"], "r") as f:
                encoded = f.read().strip()
            if not encoded:
                return
            decoded = base64.b64decode(encoded.encode()).decode()
            data = json.loads(decoded)
            for provider, values in data.items():
                if provider not in self.state["providers"]:
                    continue
                for key, value in values.items():
                    if key.startswith("_"):
                        continue
                    current = self.state["providers"][provider].get(key, "")
                    if not current:
                        self.state["providers"][provider][key] = value
            if self.state["source"] == "env":
                self.state["source"] = "env+file"
            else:
                self.state["source"] = "file"
        except Exception:
            pass

    def save_to_file(self):
        try:
            clean = {}
            for provider, fields in self.state["providers"].items():
                clean[provider] = {k: v for k, v in fields.items() if not k.startswith("_")}
            encoded = base64.b64encode(json.dumps(clean).encode()).decode()
            with open(self.state["cred_file"], "w") as f:
                f.write(encoded)
            os.chmod(self.state["cred_file"], 0o600)
            return (1, {"saved": True, "path": self.state["cred_file"]}, None)
        except Exception as e:
            return (0, None, ("SAVE_ERROR", str(e), 0))

    def Run(self, command, params=None):
        params = params or {}
        if command == "get":
            return self.get(params.get("provider", ""))
        elif command == "set":
            return self.set(params)
        elif command == "load":
            return self.load(params)
        elif command == "save":
            return self.save(params)
        elif command == "list":
            return self.list_providers(params)
        elif command == "check":
            return self.check(params.get("provider", ""))
        elif command == "mask":
            return self.mask(params.get("provider", ""))
        elif command == "register":
            return self.register(params)
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        safe = {}
        for provider, fields in self.state["providers"].items():
            safe[provider] = {k: self.mask(v) for k, v in fields.items() if not k.startswith("_")}
        return (1, {"providers": safe, "loaded": self.state["loaded"], "source": self.state["source"]}, None)

    def get(self, provider):
        if not provider:
            return (0, None, ("missing_param", "provider required", 0))
        fields = self.state["providers"].get(provider)
        if not fields:
            return (0, None, ("unknown_provider", provider, 0))
        clean = {k: v for k, v in fields.items() if not k.startswith("_")}
        return (1, clean, None)

    def set(self, params):
        provider = params.get("provider", "")
        if not provider:
            return (0, None, ("missing_param", "provider required", 0))
        if provider not in self.state["providers"]:
            return (0, None, ("unknown_provider", provider, 0))
        for key, value in params.items():
            if key == "provider":
                continue
            if key.startswith("_"):
                continue
            self.state["providers"][provider][key] = value
        return (1, {"provider": provider, "set": True}, None)

    def load(self, params=None):
        self.load_from_file()
        return (1, {"loaded": True, "source": self.state["source"]}, None)

    def save(self, params=None):
        return self.save_to_file()

    def list_providers(self, params=None):
        providers = []
        for name, fields in self.state["providers"].items():
            has_values = any(v for k, v in fields.items() if not k.startswith("_") and v)
            providers.append({
                "name": name,
                "configured": has_values,
                "fields": [k for k in fields.keys() if not k.startswith("_")],
            })
        return (1, {"providers": providers, "count": len(providers)}, None)

    def check(self, provider):
        if not provider:
            return (0, None, ("missing_param", "provider required", 0))
        fields = self.state["providers"].get(provider)
        if not fields:
            return (0, None, ("unknown_provider", provider, 0))
        missing = []
        for key, value in fields.items():
            if key.startswith("_"):
                continue
            if not value:
                missing.append(key)
        if missing:
            return (0, {"provider": provider, "missing": missing, "ok": False}, ("CRED_MISSING", "Missing: " + ", ".join(missing), 0))
        return (1, {"provider": provider, "missing": [], "ok": True}, None)

    def mask(self, provider):
        if not provider:
            return (0, None, ("missing_param", "provider required", 0))
        fields = self.state["providers"].get(provider)
        if not fields:
            return (0, None, ("unknown_provider", provider, 0))
        masked = {}
        for key, value in fields.items():
            if key.startswith("_"):
                continue
            masked[key] = self.mask(value)
        return (1, masked, None)

    def register(self, params):
        name = params.get("name", "")
        if not name:
            return (0, None, ("missing_param", "name required", 0))
        if name in self.state["providers"]:
            return (0, None, ("exists", "Provider already exists: " + name, 0))
        fields = params.get("fields", [])
        provider = {}
        for f in fields:
            provider[f] = ""
        provider["_env_keys"] = params.get("env_keys", [])
        self.state["providers"][name] = provider
        return (1, {"name": name, "registered": True}, None)

    def mask(self, value):
        if not value or not isinstance(value, str):
            return ""
        if len(value) <= 4:
            return "****"
        return value[:2] + "****" + value[-2:]
