#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     email_ingestion.py
# Domain:   Email Ingestion Pipeline
# Authority: Email → MySQL → Qdrant ingestion and semantic search
# DB:       email_store (MySQL), email_store (Qdrant collection)
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @hardcode — NO hardcoded credentials. All from env vars.
#   @cstyle   — Coding style compliant
#   @notab    — No tabs, 4-space indent
#   @noprint  — No print statements, uses logging
#   @nodeco   — No decorators
#   @tuple3   — All methods return (ok, data, error)
#   @state    — Uses self.state dict, no self._ prefix
#   @pascal   — PascalCase classes, UPPERCASE constants
#   @log      — Rotating file logging
#   @param    — Parameterized SQL queries
#   @boot     — Boots cold: creates DB, tables, Qdrant collection if missing
#   @rate     — Rate limited: 60 IMAP requests/min max
#   @incr     — Incremental sync: only fetch new emails since last sync
# ============================================================================
#
# AI GUIDE — READ THIS FIRST
# ----------------------------------------------------------------------------
# This file implements the email ingestion pipeline:
#   1. Connects to IMAP (Yahoo: imap.mail.yahoo.com, Gmail: imap.gmail.com)
#   2. Fetches emails from configured folders
#   3. Stores in MySQL email_store database (emails table)
#   4. Embeds email content to Qdrant collection email_store (384-dim BGE-small)
#   5. Supports incremental sync (only new emails since last sync)
#   6. Handles rate limiting (60 IMAP requests/min max)
#
# Commands (via Run dispatch):
#   sync      — Fetch new emails (incremental, since last sync)
#   sync_all  — Full resync (all emails from all folders)
#   embed     — Embed stored MySQL emails to Qdrant
#   search    — Semantic search emails in Qdrant
#
# Environment variables (ALL required for respective provider):
#   YAHOO_EMAIL          — Yahoo email address
#   YAHOO_APP_PASSWORD   — Yahoo app-specific password
#   GMAIL_EMAIL          — Gmail email address
#   GMAIL_APP_PASSWORD   — Gmail app-specific password
#   MYSQL_HOST           — MySQL host (default: localhost)
#   MYSQL_USER           — MySQL user (default: root)
#   MYSQL_PASSWORD       — MySQL password (default: empty)
#   MYSQL_PORT           — MySQL port (default: 3306)
#
# Usage:
#   python3 email_ingestion.py sync --provider yahoo --limit 10
#   python3 email_ingestion.py sync_all --provider gmail
#   python3 email_ingestion.py embed --provider yahoo
#   python3 email_ingestion.py search --query "invoice payment" --limit 5
# ============================================================================

import argparse
import hashlib
import imaplib
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime
from logging.handlers import RotatingFileHandler

import mysql.connector
from mysql.connector import Error as MySQLError


# ============================================================================
# CONSTANTS
# ============================================================================
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = "email_store"
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
MAX_IMAP_PER_MIN = 60
IMAP_DELAY = 60.0 / MAX_IMAP_PER_MIN  # 1.0s between requests
BODY_TRUNCATE = 8000
EMBED_BATCH = 64
MYSQL_BATCH = 50

MYSQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
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
);
"""

IMAP_SERVERS = {
    "yahoo": {"server": "imap.mail.yahoo.com", "port": 993},
    "gmail": {"server": "imap.gmail.com", "port": 993},
    "outlook": {"server": "outlook.office365.com", "port": 993},
    "apple": {"server": "imap.mail.me.com", "port": 993},
}

FOLDER_MAP = {
    "yahoo": [
        "Inbox", "Sent", "Draft", "Trash", "Bulk", "Archive",
        "Notes", "ROSLYN", "absa bank stat", "kerry", "wayne",
    ],
    "gmail": [
        "INBOX", "[Gmail]/Sent Mail", "[Gmail]/Drafts", "[Gmail]/Trash",
        "[Gmail]/Spam", "[Gmail]/All Mail", "[Gmail]/Starred",
        "[Gmail]/Important", "[Gmail]/Labels",
    ],
    "outlook": [
        "Inbox", "Sent", "Drafts", "Deleted", "Junk",
        "Archive", "Notes",
    ],
    "apple": [
        "INBOX", "Sent Messages", "Drafts", "Deleted Messages",
        "Junk", "Archive",
    ],
}

PROVIDER_ENV = {
    "yahoo": ("YAHOO_EMAIL", "YAHOO_APP_PASSWORD"),
    "gmail": ("GMAIL_EMAIL", "GMAIL_APP_PASSWORD"),
    "outlook": ("OUTLOOK_EMAIL", "OUTLOOK_PASSWORD"),
    "apple": ("APPLE_EMAIL", "APPLE_APP_PASSWORD"),
}

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_ingestion.log")


# ============================================================================
# CLASSES HEADER
# ----------------------------------------------------------------------------
# Class:  EmailIngestion
# Domain: Email ingestion pipeline
# Authority: IMAP fetch → MySQL store → Qdrant embed → semantic search
# Dependencies: imaplib, mysql.connector, sentence_transformers, urllib
# ============================================================================


class EmailIngestion:
    """Email ingestion pipeline: IMAP → MySQL → Qdrant with semantic search."""

    def __init__(self):
        self.state = {
            "provider": None,
            "email": None,
            "password": None,
            "imap_conn": None,
            "mysql_conn": None,
            "last_request": 0.0,
            "request_count": 0,
            "model": None,
            "sync_state_file": os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "email_sync_state.json",
            ),
        }
        self.logger = logging.getLogger("email_ingestion")
        self.SetupLogging()

    # ========================================================================
    # LOGGING SETUP
    # ========================================================================
    def SetupLogging(self):
        """Configure rotating file + console logging."""
        handler_file = RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3
        )
        handler_file.setFormatter(logging.Formatter(LOG_FORMAT))
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(logging.Formatter(LOG_FORMAT))
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            self.logger.addHandler(handler_file)
            self.logger.addHandler(console)

    # ========================================================================
    # RUN — DISPATCH ENTRY POINT
    # ========================================================================
    def Run(self, command, params=None):
        """Dispatch entry point. Returns Tuple3 (ok, data, error)."""
        if params is None:
            params = {}
        DISPATCH = {
            "sync": self.Sync,
            "sync_all": self.SyncAll,
            "embed": self.Embed,
            "search": self.Search,
        }
        handler = DISPATCH.get(command)
        if handler is None:
            return (False, None, "Unknown command: %s. Available: %s" % (
                command, ", ".join(DISPATCH.keys())))
        return handler(params)

    # ========================================================================
    # CREDENTIAL VALIDATION
    # ========================================================================
    def ValidateCredentials(self, provider):
        """Validate that env vars for the given provider are set. Returns Tuple3."""
        env_keys = PROVIDER_ENV.get(provider)
        if env_keys is None:
            return (False, None, "Unknown provider: %s" % provider)
        email_key, pass_key = env_keys
        email_val = os.environ.get(email_key, "")
        pass_val = os.environ.get(pass_key, "")
        if not email_val or not pass_val:
            missing = []
            if not email_val:
                missing.append(email_key)
            if not pass_val:
                missing.append(pass_key)
            return (False, None,
                    "Missing environment variables: %s. "
                    "Set them in your shell or .env file." % ", ".join(missing))
        self.state["provider"] = provider
        self.state["email"] = email_val
        self.state["password"] = pass_val
        return (True, {"email": email_val, "provider": provider}, "")

    # ========================================================================
    # IMAP CONNECTION
    # ========================================================================
    def ConnectImap(self):
        """Connect to IMAP server for the configured provider. Returns Tuple3."""
        provider = self.state.get("provider")
        if provider is None:
            return (False, None, "Provider not set. Call ValidateCredentials first.")
        srv_info = IMAP_SERVERS.get(provider)
        if srv_info is None:
            return (False, None, "No IMAP server for provider: %s" % provider)
        server = srv_info["server"]
        port = srv_info["port"]
        email_addr = self.state.get("email")
        password = self.state.get("password")
        if not email_addr or not password:
            return (False, None, "Email or password not set in state.")
        try:
            self.logger.info("Connecting to IMAP %s:%d as %s", server, port, email_addr)
            conn = imaplib.IMAP4_SSL(server, port)
            typ, data = conn.login(email_addr, password)
            if typ != "OK":
                return (False, None, "IMAP login failed: %s" % str(data))
            self.state["imap_conn"] = conn
            self.logger.info("IMAP connected and logged in: %s", email_addr)
            return (True, {"server": server, "port": port}, "")
        except imaplib.IMAP4.error as exc:
            self.logger.error("IMAP error for %s: %s", email_addr, str(exc))
            return (False, None, "IMAP connection failed: %s" % str(exc))
        except OSError as exc:
            self.logger.error("Network error connecting to %s:%d: %s", server, port, str(exc))
            return (False, None, "Network error: %s" % str(exc))
        except Exception as exc:
            self.logger.error("Unexpected IMAP error: %s", str(exc))
            return (False, None, "Unexpected error: %s" % str(exc))

    def DisconnectImap(self):
        """Close and logout IMAP connection if open."""
        conn = self.state.get("imap_conn")
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            try:
                conn.logout()
            except Exception:
                pass
            self.state["imap_conn"] = None

    # ========================================================================
    # RATE LIMITING
    # ========================================================================
    def Throttle(self):
        """Enforce rate limit: 60 IMAP requests per minute max."""
        now = time.time()
        elapsed = now - self.state["last_request"]
        if elapsed < IMAP_DELAY:
            time.sleep(IMAP_DELAY - elapsed)
        self.state["last_request"] = time.time()
        self.state["request_count"] += 1

    # ========================================================================
    # MYSQL — BOOT COLD, CONNECT, STORE
    # ========================================================================
    def ConnectMysql(self, database="email_store"):
        """Connect to MySQL, creating database and tables if missing. Returns Tuple3."""
        host = os.environ.get("MYSQL_HOST", "localhost")
        user = os.environ.get("MYSQL_USER", "root")
        password = os.environ.get("MYSQL_PASSWORD", "")
        port = int(os.environ.get("MYSQL_PORT", "3306"))
        try:
            conn = mysql.connector.connect(
                host=host, user=user, password=password, port=port,
                charset="utf8mb4", collation="utf8mb4_unicode_ci",
            )
            cur = conn.cursor()
            cur.execute(
                "CREATE DATABASE IF NOT EXISTS %s "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci" % database
            )
            conn.database = database
            cur.execute(MYSQL_SCHEMA)
            conn.commit()
            cur.close()
            self.state["mysql_conn"] = conn
            self.logger.info("MySQL connected: %s:%d/%s", host, port, database)
            return (True, {"database": database}, "")
        except MySQLError as exc:
            self.logger.error("MySQL error: %s", str(exc))
            return (False, None, "MySQL error: %s" % str(exc))

    def CloseMysql(self):
        """Close MySQL connection if open."""
        conn = self.state.get("mysql_conn")
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self.state["mysql_conn"] = None

    def StoreEmail(self, email_data):
        """Store a single email dict in MySQL. Returns Tuple3 (ok, row_id, error)."""
        conn = self.state.get("mysql_conn")
        if conn is None:
            return (False, None, "MySQL connection not established.")
        sql = (
            "INSERT INTO emails "
            "(uid, folder, provider, date_sent, from_name, from_email, "
            "to_email, cc_email, subject, body, has_attachments, "
            "attachment_names, raw_size, message_id, in_reply_to) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE fetched_at = CURRENT_TIMESTAMP"
        )
        params = (
            email_data.get("uid", ""),
            email_data.get("folder", ""),
            email_data.get("provider", ""),
            email_data.get("date_sent"),
            email_data.get("from_name", ""),
            email_data.get("from_email", ""),
            email_data.get("to_email", ""),
            email_data.get("cc_email", ""),
            email_data.get("subject", ""),
            email_data.get("body", ""),
            email_data.get("has_attachments", 0),
            email_data.get("attachment_names", ""),
            email_data.get("raw_size", 0),
            email_data.get("message_id", ""),
            email_data.get("in_reply_to", ""),
        )
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            row_id = cur.lastrowid
            cur.close()
            return (True, row_id, "")
        except MySQLError as exc:
            self.logger.error("MySQL store error for UID %s: %s",
                              email_data.get("uid", "?"), str(exc))
            return (False, None, "MySQL store error: %s" % str(exc))

    def GetExistingUids(self, folder, provider):
        """Return set of UIDs already stored for a folder/provider. Returns Tuple3."""
        conn = self.state.get("mysql_conn")
        if conn is None:
            return (False, None, "MySQL connection not established.")
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT uid FROM emails WHERE folder = %s AND provider = %s",
                (folder, provider),
            )
            uids = {row[0] for row in cur.fetchall()}
            cur.close()
            return (True, uids, "")
        except MySQLError as exc:
            self.logger.error("MySQL query error: %s", str(exc))
            return (False, None, "MySQL query error: %s" % str(exc))

    def GetLastSyncDate(self, provider):
        """Get last sync date for provider from state file. Returns Tuple3."""
        state_file = self.state.get("sync_state_file")
        if not os.path.exists(state_file):
            return (True, None, "")
        try:
            with open(state_file, "r") as f:
                all_state = json.load(f)
            date_str = all_state.get(provider, {}).get("last_sync")
            return (True, date_str, "")
        except (ValueError, OSError) as exc:
            self.logger.warning("Could not read sync state: %s", str(exc))
            return (True, None, "")

    def SaveSyncDate(self, provider, date_str):
        """Save last sync date for provider to state file. Returns Tuple3."""
        state_file = self.state.get("sync_state_file")
        all_state = {}
        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    all_state = json.load(f)
            except (ValueError, OSError):
                pass
        if provider not in all_state:
            all_state[provider] = {}
        all_state[provider]["last_sync"] = date_str
        try:
            with open(state_file, "w") as f:
                json.dump(all_state, f, indent=2)
            return (True, True, "")
        except OSError as exc:
            self.logger.error("Could not save sync state: %s", str(exc))
            return (False, None, "Could not save sync state: %s" % str(exc))

    # ========================================================================
    # QDRANT — COLLECTION, EMBED, SEARCH
    # ========================================================================
    def QdrantRequest(self, method, path, payload=None, timeout=60):
        """Make HTTP request to Qdrant. Returns parsed JSON or raises."""
        url = QDRANT_URL + path
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())

    def EnsureQdrantCollection(self):
        """Create Qdrant collection if it doesn't exist. Returns Tuple3."""
        try:
            info = self.QdrantRequest("GET", "/collections/%s" % QDRANT_COLLECTION)
            count = info.get("result", {}).get("points_count", 0)
            self.logger.info("Qdrant collection '%s' exists: %d points",
                             QDRANT_COLLECTION, count)
            return (True, {"points_count": count}, "")
        except urllib.error.HTTPError:
            pass
        except Exception as exc:
            self.logger.warning("Qdrant check error: %s", str(exc))
        try:
            payload = {
                "vectors": {"size": EMBED_DIM, "distance": "Cosine"},
                "optimizers_config": {"default_segment_number": 4},
            }
            self.QdrantRequest("PUT", "/collections/%s" % QDRANT_COLLECTION, payload)
            self.logger.info("Qdrant collection '%s' created (%d-dim, Cosine)",
                             QDRANT_COLLECTION, EMBED_DIM)
            return (True, {"created": True}, "")
        except Exception as exc:
            self.logger.error("Failed to create Qdrant collection: %s", str(exc))
            return (False, None, "Qdrant collection error: %s" % str(exc))

    def GetEmbedModel(self):
        """Lazy-load the BGE sentence transformer model. Returns Tuple3."""
        if self.state.get("model") is not None:
            return (True, self.state["model"], "")
        try:
            from sentence_transformers import SentenceTransformer
            self.logger.info("Loading embedding model: %s", EMBED_MODEL_NAME)
            model = SentenceTransformer(EMBED_MODEL_NAME)
            self.state["model"] = model
            self.logger.info("Model loaded.")
            return (True, model, "")
        except ImportError as exc:
            return (False, None,
                    "sentence_transformers not installed: %s. "
                    "Install with: pip install sentence-transformers" % str(exc))
        except Exception as exc:
            return (False, None, "Model load error: %s" % str(exc))

    def EmbedTexts(self, texts):
        """Embed a list of texts. Returns Tuple3 (ok, vectors, error)."""
        ok, model, err = self.GetEmbedModel()
        if not ok:
            return (False, None, err)
        try:
            vectors = model.encode(texts, show_progress_bar=False, batch_size=EMBED_BATCH)
            return (True, [v.tolist() for v in vectors], "")
        except Exception as exc:
            return (False, None, "Embed error: %s" % str(exc))

    def StableId(self, text, uid, folder):
        """Generate stable integer ID from content hash."""
        h = hashlib.sha256()
        h.update((text or "").encode("utf-8", errors="replace")[:500])
        h.update(str(uid).encode())
        h.update(str(folder).encode())
        return int.from_bytes(h.digest()[:8], "big") % (2 ** 62)

    def UpsertPoints(self, points, timeout=120):
        """Upsert points to Qdrant. Returns Tuple3."""
        try:
            self.QdrantRequest(
                "PUT",
                "/collections/%s/points?wait=true" % QDRANT_COLLECTION,
                {"points": points},
                timeout=timeout,
            )
            return (True, len(points), "")
        except Exception as exc:
            return (False, None, "Qdrant upsert error: %s" % str(exc))

    # ========================================================================
    # EMAIL PARSING
    # ========================================================================
    def DecodeHeader(self, raw):
        """Decode an email header value to a readable string."""
        if raw is None:
            return ""
        try:
            return str(make_header(decode_header(raw)))
        except Exception:
            return str(raw)

    def ParseEmail(self, raw_bytes, uid, folder, provider):
        """Parse raw email bytes into a dict. Returns Tuple3."""
        try:
            msg = message_from_bytes(raw_bytes)
            subject = self.DecodeHeader(msg.get("Subject", ""))
            from_raw = msg.get("From", "")
            from_decoded = self.DecodeHeader(from_raw)
            from_addrs = getaddresses([from_decoded])
            from_name = from_addrs[0][0] if from_addrs else ""
            from_email = from_addrs[0][1] if from_addrs else ""
            to_decoded = self.DecodeHeader(msg.get("To", ""))
            cc_decoded = self.DecodeHeader(msg.get("Cc", ""))
            date_raw = msg.get("Date", "")
            date_sent = None
            if date_raw:
                try:
                    date_sent = parsedate_to_datetime(date_raw)
                except Exception:
                    date_sent = None
            message_id = msg.get("Message-ID", "")
            in_reply_to = msg.get("In-Reply-To", "")
            body = self.ExtractBody(msg)
            has_attachments = 0
            attachment_names = []
            for part in msg.walk():
                content_disp = part.get("Content-Disposition", "")
                if "attachment" in content_disp.lower():
                    has_attachments = 1
                    fname = part.get_filename()
                    if fname:
                        attachment_names.append(self.DecodeHeader(fname))
            email_data = {
                "uid": str(uid),
                "folder": folder,
                "provider": provider,
                "date_sent": date_sent,
                "from_name": from_name,
                "from_email": from_email,
                "to_email": to_decoded,
                "cc_email": cc_decoded,
                "subject": subject,
                "body": body[:BODY_TRUNCATE],
                "has_attachments": has_attachments,
                "attachment_names": ", ".join(attachment_names),
                "raw_size": len(raw_bytes),
                "message_id": message_id or "",
                "in_reply_to": in_reply_to or "",
            }
            return (True, email_data, "")
        except Exception as exc:
            return (False, None, "Parse error for UID %s: %s" % (uid, str(exc)))

    def ExtractBody(self, msg):
        """Extract text body from email message object."""
        body_parts = []
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                cdisp = part.get("Content-Disposition", "")
                if "attachment" in cdisp.lower():
                    continue
                if ctype == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            body_parts.append(
                                payload.decode(charset, errors="replace")
                            )
                    except Exception:
                        pass
                elif ctype == "text/html" and not body_parts:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            body_parts.append(
                                payload.decode(charset, errors="replace")
                            )
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    body_parts.append(payload.decode(charset, errors="replace"))
            except Exception:
                pass
        return "\n".join(body_parts)

    # ========================================================================
    # FOLDER FETCH
    # ========================================================================
    def FetchFolder(self, folder, provider, limit=None, since_date=None):
        """Fetch emails from a single IMAP folder. Returns Tuple3 (ok, count, error)."""
        conn = self.state.get("imap_conn")
        if conn is None:
            return (False, 0, "IMAP not connected.")
        self.Throttle()
        try:
            typ, _ = conn.select(folder, readonly=True)
            if typ != "OK":
                self.logger.warning("Cannot select folder '%s': %s", folder, typ)
                return (True, 0, "")  # folder may not exist, skip gracefully
        except imaplib.IMAP4.error as exc:
            self.logger.warning("IMAP select error for '%s': %s", folder, str(exc))
            return (True, 0, "")

        self.Throttle()
        if since_date:
            search_criteria = '(SINCE %s)' % since_date
        else:
            search_criteria = "ALL"
        try:
            typ, data = conn.uid("search", None, search_criteria)
        except imaplib.IMAP4.error as exc:
            self.logger.warning("IMAP search error in '%s': %s", folder, str(exc))
            return (True, 0, "")
        if typ != "OK":
            self.logger.warning("Search failed in '%s': %s", folder, typ)
            return (True, 0, "")

        uids = data[0].split() if data[0] else []
        if limit and len(uids) > limit:
            uids = uids[-limit:]  # most recent

        ok, existing, err = self.GetExistingUids(folder, provider)
        if not ok:
            existing = set()
        new_uids = [u for u in uids if u.decode() not in existing]
        self.logger.info("Folder '%s': %d total, %d new", folder, len(uids), len(new_uids))

        stored = 0
        for uid in new_uids:
            self.Throttle()
            try:
                typ, fetch_data = conn.uid("fetch", uid, "(RFC822)")
            except imaplib.IMAP4.error as exc:
                self.logger.warning("Fetch error UID %s: %s", uid.decode(), str(exc))
                continue
            if typ != "OK" or not fetch_data or not fetch_data[0]:
                continue
            raw_bytes = fetch_data[0][1]
            if not raw_bytes:
                continue
            ok, email_data, err = self.ParseEmail(
                raw_bytes, uid.decode(), folder, provider
            )
            if not ok:
                self.logger.warning("Parse failed: %s", err)
                continue
            ok, _, err = self.StoreEmail(email_data)
            if ok:
                stored += 1
            else:
                self.logger.warning("Store failed: %s", err)
        self.logger.info("Folder '%s': stored %d emails", folder, stored)
        return (True, stored, "")

    # ========================================================================
    # COMMAND: SYNC (incremental)
    # ========================================================================
    def Sync(self, params):
        """Incremental sync: fetch new emails since last sync date. Returns Tuple3."""
        provider = params.get("provider", "yahoo")
        limit = params.get("limit")
        ok, _, err = self.ValidateCredentials(provider)
        if not ok:
            return (False, None, err)
        ok, _, err = self.ConnectMysql()
        if not ok:
            return (False, None, err)
        ok, _, err = self.ConnectImap()
        if not ok:
            self.CloseMysql()
            return (False, None, err)
        ok, since_date, _ = self.GetLastSyncDate(provider)
        if since_date:
            self.logger.info("Incremental sync since: %s", since_date)
        else:
            self.logger.info("First sync — fetching all (incremental mode).")
            since_date = None
        folders = FOLDER_MAP.get(provider, [])
        total_stored = 0
        errors = []
        for folder in folders:
            ok, count, err = self.FetchFolder(
                folder, provider, limit=limit, since_date=since_date
            )
            if ok:
                total_stored += count
            else:
                errors.append("%s: %s" % (folder, err))
        self.DisconnectImap()
        self.CloseMysql()
        now_str = time.strftime("%d-%b-%Y")
        self.SaveSyncDate(provider, now_str)
        result = {
            "provider": provider,
            "stored": total_stored,
            "folders": len(folders),
            "errors": errors,
        }
        self.logger.info("Sync complete: %d stored, %d errors", total_stored, len(errors))
        return (True, result, "")

    # ========================================================================
    # COMMAND: SYNC_ALL (full resync)
    # ========================================================================
    def SyncAll(self, params):
        """Full resync: fetch all emails from all folders. Returns Tuple3."""
        provider = params.get("provider", "yahoo")
        limit = params.get("limit")
        ok, _, err = self.ValidateCredentials(provider)
        if not ok:
            return (False, None, err)
        ok, _, err = self.ConnectMysql()
        if not ok:
            return (False, None, err)
        ok, _, err = self.ConnectImap()
        if not ok:
            self.CloseMysql()
            return (False, None, err)
        folders = FOLDER_MAP.get(provider, [])
        total_stored = 0
        errors = []
        for folder in folders:
            ok, count, err = self.FetchFolder(
                folder, provider, limit=limit, since_date=None
            )
            if ok:
                total_stored += count
            else:
                errors.append("%s: %s" % (folder, err))
        self.DisconnectImap()
        self.CloseMysql()
        now_str = time.strftime("%d-%b-%Y")
        self.SaveSyncDate(provider, now_str)
        result = {
            "provider": provider,
            "stored": total_stored,
            "folders": len(folders),
            "errors": errors,
        }
        self.logger.info("SyncAll complete: %d stored, %d errors",
                         total_stored, len(errors))
        return (True, result, "")

    # ========================================================================
    # COMMAND: EMBED (MySQL → Qdrant)
    # ========================================================================
    def Embed(self, params):
        """Embed stored MySQL emails to Qdrant. Returns Tuple3."""
        provider = params.get("provider")
        limit = params.get("limit")
        ok, _, err = self.ConnectMysql()
        if not ok:
            return (False, None, err)
        ok, _, err = self.EnsureQdrantCollection()
        if not ok:
            self.CloseMysql()
            return (False, None, err)
        conn = self.state.get("mysql_conn")
        try:
            cur = conn.cursor(dictionary=True)
            if provider:
                cur.execute(
                    "SELECT * FROM emails WHERE provider = %s ORDER BY id", (provider,)
                )
            else:
                cur.execute("SELECT * FROM emails ORDER BY id")
            rows = cur.fetchall()
            cur.close()
        except MySQLError as exc:
            self.CloseMysql()
            return (False, None, "MySQL query error: %s" % str(exc))
        if limit:
            rows = rows[:limit]
        total = len(rows)
        self.logger.info("Embedding %d emails to Qdrant...", total)
        embedded = 0
        batch_texts = []
        batch_meta = []
        for row in rows:
            text = "Subject: %s\nFrom: %s <%s>\nDate: %s\n\n%s" % (
                row.get("subject", ""),
                row.get("from_name", ""),
                row.get("from_email", ""),
                str(row.get("date_sent", "")),
                row.get("body", "")[:BODY_TRUNCATE],
            )
            point_id = self.StableId(text, row.get("uid"), row.get("folder"))
            batch_texts.append(text)
            batch_meta.append({
                "id": point_id,
                "source": "email",
                "mysql_id": row.get("id"),
                "uid": row.get("uid"),
                "folder": row.get("folder"),
                "provider": row.get("provider"),
                "from_name": row.get("from_name"),
                "from_email": row.get("from_email"),
                "subject": row.get("subject", "")[:200],
                "date_sent": str(row.get("date_sent", "")),
            })
            if len(batch_texts) >= EMBED_BATCH:
                ok, vectors, err = self.EmbedTexts(batch_texts)
                if not ok:
                    self.logger.error("Embed batch error: %s", err)
                    batch_texts = []
                    batch_meta = []
                    continue
                points = []
                for vec, meta in zip(vectors, batch_meta):
                    points.append({"id": meta["id"], "vector": vec, "payload": meta})
                ok, cnt, err = self.UpsertPoints(points)
                if ok:
                    embedded += cnt
                else:
                    self.logger.error("Upsert error: %s", err)
                batch_texts = []
                batch_meta = []
        if batch_texts:
            ok, vectors, err = self.EmbedTexts(batch_texts)
            if ok:
                points = []
                for vec, meta in zip(vectors, batch_meta):
                    points.append({"id": meta["id"], "vector": vec, "payload": meta})
                ok, cnt, err = self.UpsertPoints(points)
                if ok:
                    embedded += cnt
                else:
                    self.logger.error("Upsert error: %s", err)
            else:
                self.logger.error("Embed batch error: %s", err)
        self.CloseMysql()
        result = {"total": total, "embedded": embedded}
        self.logger.info("Embed complete: %d/%d embedded", embedded, total)
        return (True, result, "")

    # ========================================================================
    # COMMAND: SEARCH (semantic search Qdrant)
    # ========================================================================
    def Search(self, params):
        """Semantic search emails in Qdrant. Returns Tuple3."""
        query = params.get("query", "")
        limit = params.get("limit", 10)
        provider = params.get("provider")
        if not query:
            return (False, None, "No query provided. Use --query 'search text'.")
        ok, _, err = self.EnsureQdrantCollection()
        if not ok:
            return (False, None, err)
        ok, vectors, err = self.EmbedTexts([query])
        if not ok:
            return (False, None, err)
        query_vector = vectors[0]
        search_payload = {
            "vector": query_vector,
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
        }
        if provider:
            search_payload["filter"] = {
                "must": [{"key": "provider", "match": {"value": provider}}]
            }
        try:
            result = self.QdrantRequest(
                "POST",
                "/collections/%s/points/search" % QDRANT_COLLECTION,
                search_payload,
            )
            hits = result.get("result", [])
            results = []
            for hit in hits:
                payload = hit.get("payload", {})
                results.append({
                    "score": hit.get("score", 0),
                    "subject": payload.get("subject", ""),
                    "from_name": payload.get("from_name", ""),
                    "from_email": payload.get("from_email", ""),
                    "folder": payload.get("folder", ""),
                    "provider": payload.get("provider", ""),
                    "date_sent": payload.get("date_sent", ""),
                    "uid": payload.get("uid", ""),
                    "mysql_id": payload.get("mysql_id"),
                })
            self.logger.info("Search '%s': %d results", query, len(results))
            return (True, results, "")
        except Exception as exc:
            return (False, None, "Qdrant search error: %s" % str(exc))


# ============================================================================
# CLI ENTRY POINT
# ============================================================================
def ParseArgs():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Email → MySQL → Qdrant ingestion pipeline"
    )
    parser.add_argument("command", choices=["sync", "sync_all", "embed", "search"],
                        help="Command to run")
    parser.add_argument("--provider", default="yahoo",
                        help="Email provider (yahoo, gmail, outlook, apple)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max emails to fetch/embed")
    parser.add_argument("--query", default="",
                        help="Search query (for search command)")
    return parser.parse_args()


def Main():
    """CLI entry point."""
    args = ParseArgs()
    ingestion = EmailIngestion()
    params = {
        "provider": args.provider,
        "limit": args.limit,
        "query": args.query,
    }
    ok, data, error = ingestion.Run(args.command, params)
    if ok:
        sys.stderr.write("SUCCESS: %s\n" % json.dumps(data, default=str, indent=2))
        sys.exit(0)
    else:
        sys.stderr.write("ERROR: %s\n" % error)
        sys.exit(1)


if __name__ == "__main__":
    Main()
