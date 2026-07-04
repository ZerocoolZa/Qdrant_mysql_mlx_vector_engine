#!/usr/bin/env python3
#[@GHOST]{("file";"config_email_helper.py")("domain";"Gloabel_configs")("role";"helper")("auth";"wws+cascade")("date";"2026-07-03")("ver";"1.0")}
#[@VBSTYLE]{("role";"helper")("no";"decorators|print|hardcoded")}
#[@SUMMARY]{("purpose";"Env loader + getter/validator functions for Config_Email")("consumers";"any module importing Config_Email")}
#[@FILEID]{("path";"Gloabel_configs/config_email_helper.py")}
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
_CENTRAL_ENV_PATH = Path.home() / ".config" / "mcp-email" / ".env"


def LoadEnvFile(env_path):
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)
    except ImportError:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val


def LoadEnv():
    LoadEnvFile(_CENTRAL_ENV_PATH)
    LoadEnvFile(BASE_DIR / ".env")


def EnvRequired(name):
    val = os.environ.get(name, "")
    if not val:
        sys.exit("ERROR: Environment variable " + name + " is required but not set.")
    return val


def EnvOptional(name, default=""):
    return os.environ.get(name, default)


def GetProvider(config, name=None):
    if name is None:
        name = config.get("DEFAULT_PROVIDER", "yahoo")
    return config.get("MAIL_PROVIDERS", {}).get(name.lower(), {})


def GetFolders(config, provider=None):
    if provider is None:
        provider = config.get("DEFAULT_PROVIDER", "yahoo")
    return config.get("FOLDER_MAP", {}).get(provider.lower(), [])


def GetMysqlConfig(config, database=None):
    mysql = config.get("MYSQL", {})
    cfg = {
        "host": mysql.get("host", "localhost"),
        "user": mysql.get("user", "root"),
        "password": mysql.get("password", ""),
        "port": mysql.get("port", 3306),
        "charset": mysql.get("charset", "utf8mb4"),
    }
    cfg["database"] = database or mysql.get("database_default", "email_store")
    return cfg


def GetFilterKeywords(config, preset="all"):
    return config.get("FILTER_PRESETS", {}).get(preset, [])


def ValidateProvider(config, name=None):
    if name is None:
        name = config.get("DEFAULT_PROVIDER", "yahoo")
    provider = config.get("MAIL_PROVIDERS", {}).get(name.lower())
    if not provider:
        return (False, "Unknown provider: " + name)
    if not provider.get("email"):
        return (False, name + ": email not set (check env var)")
    if not provider.get("app_password") and not provider.get("oauth_client_id"):
        return (False, name + ": no app_password or oauth credentials set")
    return (True, "")


def ValidateAll(config):
    return ValidateProvider(config, config.get("DEFAULT_PROVIDER", "yahoo"))
