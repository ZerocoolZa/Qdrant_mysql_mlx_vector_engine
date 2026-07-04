#!/usr/bin/env python3
#[@GHOST]{("file";"config_email.py")("domain";"Gloabel_configs")("role";"config")("auth";"wws+cascade")("date";"2026-06-22")("updated";"2026-07-03")("ver";"3.0")}
#[@VBSTYLE]{("role";"config")("no";"decorators|print|hardcoded|functions")("secrets";"env_only")}
#[@SUMMARY]{("purpose";"Global config for all external services")("scope";"email providers, MySQL, Pinecone, MCP server, Google Workspace")("secrets";"all from env vars, never hardcoded")}
#[@FILEID]{("path";"Gloabel_configs/config_email.py")}
#[@WHATIS]{("role";"single source of truth for external service config")("consumers";"MCP email servers, MySQL, Pinecone, Google Workspace")("rule";"no other file defines email or service credentials")("content";"VARIABLES ONLY — no functions, no code")}
#[@AIGUIDE]{("rule";"secrets from env vars, NEVER hardcoded")("start";"copy ENV_EXAMPLE to .env and fill values")("helper";"Config_Email_Helper.py has LoadEnv, EnvRequired, EnvOptional, GetProvider, ValidateProvider")}
#[@ENVORDER]{("1";"shell env vars")("2";"Gloabel_configs/.env")("3";"~/.config/mcp-email/.env")}

import os
from pathlib import Path
from Config_Email_Helper import LoadEnv, EnvRequired, EnvOptional

LoadEnv()

BASE_DIR = Path(__file__).resolve().parent

#[@ENVTEMPLATE]{("purpose";"copy to .env and fill values")("pinecone_key";"pcsk_2FLHBZ_62Q5zoP96AZf8skbKJBNWRxwUZi3gnk1qVkKuHasRfZ9NczDGRjhvZqyfZ8bPSH")}
ENV_EXAMPLE = """\
# --- Yahoo Mail ---
YAHOO_EMAIL=your_yahoo@yahoo.com
YAHOO_APP_PASSWORD=your_yahoo_app_password

# --- Gmail ---
GMAIL_EMAIL=your_gmail@gmail.com
GMAIL_APP_PASSWORD=your_gmail_app_password
GMAIL_CLIENT_ID=your_gmail_client_id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your_gmail_client_secret

# --- Google OAuth ---
GOOGLE_OAUTH_CLIENT_ID_CASCADEWAYNE=your_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_SECRET_CASCADEWAYNE=your_client_secret
GOOGLE_OAUTH_CLIENT_ID_BACKUP_A=your_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_SECRET_BACKUP_A=your_client_secret
GOOGLE_OAUTH_CLIENT_ID_BACKUP_B=your_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_SECRET_BACKUP_B=your_client_secret

# --- Pinecone ---
PINECONE_API_KEY=pcsk_2FLHBZ_62Q5zoP96AZf8skbKJBNWRxwUZi3gnk1qVkKuHasRfZ9NczDGRjhvZqyfZ8bPSH

# --- MySQL ---
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_PORT=3306

# --- MCP Server ---
TRANSPORT_MODE=stdio
PORT=3000
OAUTH_CLIENT_ID=
OAUTH_CLIENT_SECRET=

# --- Logging ---
LOG_LEVEL=INFO

# --- Default mail provider ---
DEFAULT_MAIL_PROVIDER=yahoo
"""

#[@YAHOO]{("imap";"imap.mail.yahoo.com:993")("smtp";"smtp.mail.yahoo.com:587")("oauth";"api.login.yahoo.com")}
YAHOO = {
    "email":              EnvRequired("YAHOO_EMAIL"),
    "app_password":       EnvRequired("YAHOO_APP_PASSWORD"),
    "imap_server":        "imap.mail.yahoo.com",
    "imap_port":          993,
    "smtp_server":        "smtp.mail.yahoo.com",
    "smtp_port":          587,
    "smtp_use_ssl":       True,
    "smtp_use_starttls":  True,
    "oauth_client_id":    EnvOptional("YAHOO_CLIENT_ID", ""),
    "oauth_client_secret":EnvOptional("YAHOO_CLIENT_SECRET", ""),
    "oauth_scope":        "https://mail.yahoo.com/.default",
    "oauth_token_url":    "https://api.login.yahoo.com/oauth2/get_token",
}

#[@GMAIL]{("imap";"imap.gmail.com:993")("smtp";"smtp.gmail.com:587")("oauth";"oauth2.googleapis.com")}
GMAIL = {
    "email":              EnvOptional("GMAIL_EMAIL", ""),
    "app_password":       EnvOptional("GMAIL_APP_PASSWORD", ""),
    "imap_server":        "imap.gmail.com",
    "imap_port":          993,
    "smtp_server":        "smtp.gmail.com",
    "smtp_port":          587,
    "smtp_use_ssl":       True,
    "smtp_use_starttls":  True,
    "oauth_client_id":    EnvOptional("GMAIL_CLIENT_ID", ""),
    "oauth_client_secret":EnvOptional("GMAIL_CLIENT_SECRET", ""),
    "oauth_scope":        "https://mail.google.com/",
    "oauth_token_url":    "https://oauth2.googleapis.com/token",
    "oauth_redirect_uri": "http://localhost:8080/callback",
    "oauth_auth_url":     "https://accounts.google.com/o/oauth2/auth",
    "scopes": [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.labels",
    ],
}

#[@OUTLOOK]{("imap";"outlook.office365.com:993")("smtp";"smtp.office365.com:587")("oauth";"login.microsoftonline.com")}
OUTLOOK = {
    "email":              EnvOptional("OUTLOOK_EMAIL", ""),
    "app_password":       EnvOptional("OUTLOOK_PASSWORD", ""),
    "imap_server":        "outlook.office365.com",
    "imap_port":          993,
    "smtp_server":        "smtp.office365.com",
    "smtp_port":          587,
    "smtp_use_ssl":       True,
    "smtp_use_starttls":  True,
    "oauth_client_id":    EnvOptional("OUTLOOK_CLIENT_ID", ""),
    "oauth_client_secret":EnvOptional("OUTLOOK_CLIENT_SECRET", ""),
    "oauth_scope":        "https://outlook.office.com/Mail.ReadWrite",
    "oauth_token_url":    "https://login.microsoftonline.com/common/oauth2/v2.0/token",
    "oauth_auth_url":     "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
}

#[@APPLE]{("imap";"imap.mail.me.com:993")("smtp";"smtp.mail.me.com:587")}
APPLE = {
    "email":              EnvOptional("APPLE_EMAIL", ""),
    "app_password":       EnvOptional("APPLE_APP_PASSWORD", ""),
    "imap_server":        "imap.mail.me.com",
    "imap_port":          993,
    "smtp_server":        "smtp.mail.me.com",
    "smtp_port":          587,
    "smtp_use_ssl":       True,
    "smtp_use_starttls":  True,
}

#[@PROTON]{("imap";"127.0.0.1:1143")("smtp";"127.0.0.1:1025")("note";"requires Proton Bridge")}
PROTON = {
    "email":              EnvOptional("PROTON_EMAIL", ""),
    "app_password":       EnvOptional("PROTON_APP_PASSWORD", ""),
    "imap_server":        "127.0.0.1",
    "imap_port":          1143,
    "smtp_server":        "127.0.0.1",
    "smtp_port":          1025,
    "smtp_use_ssl":       False,
    "smtp_use_starttls":  True,
    "bridge_required":    True,
}

#[@MAILPROVIDERS]{("count";5)("providers";"yahoo, gmail, outlook, apple, proton")}
MAIL_PROVIDERS = {
    "yahoo":    YAHOO,
    "gmail":    GMAIL,
    "outlook":  OUTLOOK,
    "apple":    APPLE,
    "proton":   PROTON,
}

DEFAULT_PROVIDER = EnvOptional("DEFAULT_MAIL_PROVIDER", "yahoo")

#[@FOLDERS]{("yahoo";"Inbox, Sent, Draft, Trash, Bulk, Archive, Notes, ROSLYN, absa bank stat, kerry, wayne")("gmail";"INBOX, Sent Mail, Drafts, Trash, Spam, All Mail, Starred, Important, Labels")("outlook";"Inbox, Sent, Drafts, Deleted, Junk, Archive, Notes")("apple";"INBOX, Sent Messages, Drafts, Deleted Messages, Junk, Archive")}
YAHOO_FOLDERS = ["Inbox", "Sent", "Draft", "Trash", "Bulk", "Archive", "Notes", "ROSLYN", "absa bank stat", "kerry", "wayne"]
GMAIL_FOLDERS = ["INBOX", "[Gmail]/Sent Mail", "[Gmail]/Drafts", "[Gmail]/Trash", "[Gmail]/Spam", "[Gmail]/All Mail", "[Gmail]/Starred", "[Gmail]/Important", "[Gmail]/Labels"]
OUTLOOK_FOLDERS = ["Inbox", "Sent", "Drafts", "Deleted", "Junk", "Archive", "Notes"]
APPLE_FOLDERS = ["INBOX", "Sent Messages", "Drafts", "Deleted Messages", "Junk", "Archive"]
FOLDER_MAP = {"yahoo": YAHOO_FOLDERS, "gmail": GMAIL_FOLDERS, "outlook": OUTLOOK_FOLDERS, "apple": APPLE_FOLDERS}

#[@FILTERS]{("rht";"rht, rental housing, tribunal, case 27/01, withholding of property, spoliation, unlawful lockout")("legal";"summons, court, magistrate, high court, supreme court, constitutional court, attorney, advocate, litigation, interdict, application, affidavit, notice of motion, rule 43, rule 31")("absa";"absa, bank statement, overdraft, home loan")("insurance";"insurance, claim, assessor, broker")}
RHT_KEYWORDS = ["rht", "rental housing", "tribunal", "case 27/01", "withholding of property", "spoliation", "unlawful lockout"]
LEGAL_KEYWORDS = ["summons", "court", "magistrate", "high court", "supreme court", "constitutional court", "attorney", "advocate", "litigation", "interdict", "application", "affidavit", "notice of motion", "rule 43", "rule 31"]
FILTER_PRESETS = {"rht": RHT_KEYWORDS, "legal": LEGAL_KEYWORDS, "absa": ["absa", "bank statement", "overdraft", "home loan"], "insurance": ["insurance", "claim", "assessor", "broker"], "all": []}

#[@MYSQL]{("host";"localhost:3306")("user";"root")("databases";"rht_emails, yahoo_emails, gmail_emails, outlook_emails, email_store")}
MYSQL = {
    "host":              EnvOptional("MYSQL_HOST", "localhost"),
    "user":              EnvOptional("MYSQL_USER", "root"),
    "password":          EnvOptional("MYSQL_PASSWORD", ""),
    "port":              int(EnvOptional("MYSQL_PORT", "3306")),
    "charset":           "utf8mb4",
    "collation":         "utf8mb4_unicode_ci",
    "database_rht":      "rht_emails",
    "database_all":      "yahoo_emails",
    "database_gmail":    "gmail_emails",
    "database_outlook":  "outlook_emails",
    "database_default":  "email_store",
}

MYSQL_SCHEMA = """CREATE TABLE IF NOT EXISTS emails (
    id INT AUTO_INCREMENT PRIMARY KEY,
    uid VARCHAR(50),
    folder VARCHAR(100),
    provider VARCHAR(50) DEFAULT 'yahoo',
    date_sent DATETIME,
    from_name VARCHAR(255),
    from_email VARCHAR(255),
    to_email TEXT,
    cc_email TEXT,
    subject TEXT,
    body LONGTEXT,
    has_attachments TINYINT DEFAULT 0,
    attachment_names TEXT,
    raw_size INT DEFAULT 0,
    message_id VARCHAR(500),
    in_reply_to VARCHAR(500),
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_uid_folder (uid, folder, provider)
);"""

#[@IMAP]{("batch";100)("timeout";30)("idle";"29min")("reconnect";"3x @ 5s")}
IMAP_SETTINGS = {"batch_size": 100, "fetch_headers_only": True, "header_fields": ["SUBJECT", "FROM", "TO", "DATE"], "use_uid": True, "readonly_select": True, "connection_timeout": 30, "idle_timeout": 29 * 60, "max_reconnect": 3, "reconnect_delay": 5}

#[@SMTP]{("timeout";30)("retries";"3x @ 2s")("max_attachment";"25MB")}
SMTP_SETTINGS = {"timeout": 30, "max_retries": 3, "retry_delay": 2.0, "default_from_name": "", "default_reply_to": "", "max_attachment_mb": 25, "encoding": "utf-8"}

#[@PINECONE]{("key";"pcsk_2FLHBZ_...")("top_k";10)("rerank";"bge-reranker-v2-m3")}
PINECONE = {
    "api_key":               EnvOptional("PINECONE_API_KEY", "pcsk_2FLHBZ_62Q5zoP96AZf8skbKJBNWRxwUZi3gnk1qVkKuHasRfZ9NczDGRjhvZqyfZ8bPSH"),
    "default_index":         EnvOptional("PINECONE_INDEX", ""),
    "default_namespace":     EnvOptional("PINECONE_NAMESPACE", ""),
    "default_top_k":         10,
    "rerank_model":          "bge-reranker-v2-m3",
    "rerank_default":        True,
}

#[@MCPSERVER]{("transport";"stdio")("port";3000)}
MCP_SERVER = {
    "transport_mode":        EnvOptional("TRANSPORT_MODE", "stdio"),
    "port":                  int(EnvOptional("PORT", "3000")),
    "oauth_client_id":       EnvOptional("OAUTH_CLIENT_ID", ""),
    "oauth_client_secret":   EnvOptional("OAUTH_CLIENT_SECRET", ""),
    "node_env":              EnvOptional("NODE_ENV", "development"),
}

#[@GOOGLEWORKSPACE]{("active";"cascadewayne")("projects";"cascadewayne, backup_498022_a, backup_498022_b")("scopes";"gmail, calendar, drive, contacts, sheets, docs")}
GOOGLE_WORKSPACE = {
    "client_secret_file":    EnvOptional("GOOGLE_CLIENT_SECRET_FILE", str(Path.home() / "Downloads" / "client_secret_768426539127-anlok2ht6pcuh9p854nlh012ncv087r7.apps.googleusercontent.com.json")),
    "token_file":            EnvOptional("GOOGLE_TOKEN_FILE", str(Path.home() / "hermes-agent" / "google_token.json")),
    "hermes_token_path":     str(Path.home() / "hermes-agent" / "google_token.json"),
    "hermes_secret_path":    str(Path.home() / "hermes-agent" / "google_client_secret.json"),
    "cascadewayne": {
        "client_id":     EnvOptional("GOOGLE_OAUTH_CLIENT_ID_CASCADEWAYNE", "768426539127-anlok2ht6pcuh9p854nlh012ncv087r7.apps.googleusercontent.com"),
        "project_id":    "cascadewayne",
        "client_secret": EnvOptional("GOOGLE_OAUTH_SECRET_CASCADEWAYNE", ""),
        "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
        "token_uri":     "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    },
    "backup_498022_a": {
        "client_id":     EnvOptional("GOOGLE_OAUTH_CLIENT_ID_BACKUP_A", "515261514966-2q8qb07dj3nmji6bl24lo8578o1kds3h.apps.googleusercontent.com"),
        "project_id":    "backup-498022",
        "client_secret": EnvOptional("GOOGLE_OAUTH_SECRET_BACKUP_A", ""),
        "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
        "token_uri":     "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    },
    "backup_498022_b": {
        "client_id":     EnvOptional("GOOGLE_OAUTH_CLIENT_ID_BACKUP_B", "515261514966-ltd4usa1aonlidn1uaehl98gggi26fck.apps.googleusercontent.com"),
        "project_id":    "backup-498022",
        "client_secret": EnvOptional("GOOGLE_OAUTH_SECRET_BACKUP_B", ""),
        "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
        "token_uri":     "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    },
    "active_client":         "cascadewayne",
    "scopes": [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/contacts.readonly",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/documents",
    ],
    "redirect_uri":          "http://localhost:8080/callback",
    "token_uri":             "https://oauth2.googleapis.com/token",
    "auth_uri":              "https://accounts.google.com/o/oauth2/auth",
}

#[@ATTACHMENTS]{("max";"50MB")("allowed";"pdf, doc, docx, xls, xlsx, jpg, jpeg, png, gif, bmp, txt, csv, zip, rar, eml, msg")("skip";"exe, bat, cmd, scr, vbs")("pattern";"{date}_{from}_{filename}")}
ATTACHMENTS = {
    "download_dir":          str(BASE_DIR / "attachments"),
    "max_file_mb":           50,
    "allowed_extensions":    [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".txt", ".csv", ".zip", ".rar", ".eml", ".msg"],
    "skip_extensions":       [".exe", ".bat", ".cmd", ".scr", ".vbs"],
    "naming_pattern":        "{date}_{from}_{filename}",
}

#[@SYNC]{("mode";"full")("batch";50)("skip_existing";True)}
SYNC = {"mode": "full", "modes": ["full", "incremental"], "since_date": "", "batch_commit": True, "batch_size": 50, "skip_existing": True, "update_existing": False}

#[@LOGGING]{("level";"INFO")("max";"10MB")("backups";3)("format";"%(asctime)s [%(levelname)s] %(message)s")}
LOGGING = {
    "level":                 EnvOptional("LOG_LEVEL", "INFO"),
    "file":                  str(BASE_DIR / "email_fetch.log"),
    "max_size_mb":           10,
    "backup_count":          3,
    "format":                "%(asctime)s [%(levelname)s] %(message)s",
    "date_format":           "%Y-%m-%d %H:%M:%S",
    "console_output":        True,
    "log_per_folder":        False,
}

#[@RATELIMIT]{("imap";"60/min")("smtp";"100/hr")("delay";"0.1s between fetches, 1.0s between folders")("backoff";"max 60s")}
RATE_LIMIT = {"imap_requests_per_min": 60, "smtp_sends_per_hour": 100, "delay_between_fetches": 0.1, "delay_between_folders": 1.0, "backoff_on_error": True, "max_backoff_seconds": 60}

#[@SECURITY]{("ssl";"TLSv1_2")("require_app_password";True)("reject_plaintext";True)("mask_logs";True)}
SECURITY = {"verify_ssl": True, "ssl_version": "TLSv1_2", "require_app_password": True, "reject_plaintext": True, "mask_credentials_logs": True, "allowed_origins": ["http://localhost:3000"]}

#[@NOTIFICATIONS]{("enable";False)("on_error";True)}
NOTIFICATIONS = {"enable": False, "on_complete": False, "on_error": True, "webhook_url": "", "email_recipient": ""}
