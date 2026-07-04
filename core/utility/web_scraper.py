#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Core/utility/web_scraper.py"
# date="2026-07-03" author="Cascade" session_id="utility-scraper"
# context="Multi-method web scraper. urllib, curl, wget approaches. Globally reusable."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="web_scraper.py" domain="utility" authority="single"}
# [@SUMMARY]{summary="Web scraper with multiple backends: urllib, curl, wget. Fetch single pages or mirror entire sites."}
# [@CLASS]{class="WebScraper" domain="utility" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="FetchPage" type="command"}
# [@METHOD]{method="FetchBatch" type="command"}
# [@METHOD]{method="MirrorSite" type="command"}
# [@METHOD]{method="ExtractLinks" type="command"}
# [@METHOD]{method="ParseIndex" type="command"}
# [@METHOD]{method="SaveToDb" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}

import os
import re
import json
import time
import sqlite3
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed

sys_path = os.path.dirname(os.path.abspath(__file__))
if sys_path not in os.sys.path:
    os.sys.path.insert(0, sys_path)
from Config import (
    SCRAPER_TIMEOUT, SCRAPER_DELAY, SCRAPER_RETRIES,
    SCRAPER_MAX_WORKERS, SCRAPER_USER_AGENT, SCRAPER_DB_PATH,
    SCRAPER_TARGETS,
)

MAX_WORKERS = SCRAPER_MAX_WORKERS
DEFAULT_TIMEOUT = SCRAPER_TIMEOUT
DEFAULT_DELAY = SCRAPER_DELAY
DEFAULT_RETRIES = SCRAPER_RETRIES
DEFAULT_USER_AGENT = SCRAPER_USER_AGENT
DEFAULT_DB_PATH = SCRAPER_DB_PATH


class LinkExtractor(HTMLParser):
    """Extract all href links from HTML."""

    def __init__(self):
        super().__init__()
        self.links = []
        self.in_a = False
        self.current_href = None
        self.current_text = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.in_a = True
            for attr, value in attrs:
                if attr == "href":
                    self.current_href = value
                    self.current_text = ""

    def handle_data(self, data):
        if self.in_a:
            self.current_text = (self.current_text or "") + data

    def handle_endtag(self, tag):
        if tag == "a" and self.in_a:
            self.in_a = False
            if self.current_href:
                self.links.append({
                    "href": self.current_href,
                    "text": (self.current_text or "").strip(),
                })
            self.current_href = None
            self.current_text = None


class TextExtractor(HTMLParser):
    """Extract text content and meta description from HTML."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta_description = ""
        self.text_parts = []
        self.in_title = False
        self.in_script = False
        self.in_style = False
        self.in_meta = False
        self.meta_attr = None

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True
        elif tag == "script":
            self.in_script = True
        elif tag == "style":
            self.in_style = True
        elif tag == "meta":
            attrs_dict = dict(attrs)
            if attrs_dict.get("name") == "description":
                self.meta_description = attrs_dict.get("content", "")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "script":
            self.in_script = False
        elif tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.in_script or self.in_style:
            return
        if self.in_title:
            self.title += data
        stripped = data.strip()
        if stripped:
            self.text_parts.append(stripped)

    def get_text(self, max_length=500):
        return " ".join(self.text_parts)[:max_length]


class WebScraper:
    """Multi-backend web scraper. Supports urllib, curl, and wget approaches."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "base_url": None,
            "output_dir": None,
            "db_path": DEFAULT_DB_PATH,
            "timeout": DEFAULT_TIMEOUT,
            "delay": DEFAULT_DELAY,
            "retries": DEFAULT_RETRIES,
            "max_workers": MAX_WORKERS,
            "user_agent": DEFAULT_USER_AGENT,
            "pages_fetched": 0,
            "pages_failed": 0,
            "links_found": 0,
            "bytes_downloaded": 0,
            "errors": [],
        }
        if param:
            self.set_config(param)

    def Run(self, command, params=None):
        params = params or {}
        if command == "fetch_page":
            return self.FetchPage(params)
        elif command == "fetch_batch":
            return self.FetchBatch(params)
        elif command == "mirror_site":
            return self.MirrorSite(params)
        elif command == "extract_links":
            return self.ExtractLinks(params)
        elif command == "parse_index":
            return self.ParseIndex(params)
        elif command == "save_to_db":
            return self.SaveToDb(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params=None):
        if not params:
            return (1, dict(self.state), None)
        for key in ("base_url", "output_dir", "db_path", "timeout", "delay",
                     "retries", "max_workers", "user_agent"):
            if key in params:
                self.state[key] = params[key]
        return (1, dict(self.state), None)

    def _fetch_urllib(self, url, timeout=None):
        """Fetch URL using urllib (pure Python, no external deps)."""
        timeout = timeout or self.state["timeout"]
        req = urllib.request.Request(url, headers={
            "User-Agent": self.state["user_agent"],
        })
        resp = urllib.request.urlopen(req, timeout=timeout)
        encoding = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(encoding, errors="replace")

    def _fetch_curl(self, url, timeout=None):
        """Fetch URL using curl CLI."""
        timeout = timeout or self.state["timeout"]
        result = subprocess.run(
            ["curl", "-sL", "--max-time", str(timeout),
             "-A", self.state["user_agent"], url],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        if result.returncode != 0:
            raise RuntimeError("curl failed: " + result.stderr)
        return result.stdout

    def _fetch_wget(self, url, output_dir=None):
        """Fetch URL using wget CLI (saves to file)."""
        output_dir = output_dir or self.state["output_dir"] or "/tmp"
        os.makedirs(output_dir, exist_ok=True)
        result = subprocess.run(
            ["wget", "-q", "--no-check-certificate",
             "-U", self.state["user_agent"],
             "-P", output_dir, url],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError("wget failed: " + result.stderr)
        parsed = urllib.parse.urlparse(url)
        filename = os.path.join(output_dir, parsed.path.lstrip("/") or "index.html")
        if os.path.isfile(filename):
            with open(filename, "r", errors="replace") as f:
                return f.read()
        return ""

    def _fetch_with_retry(self, url, method="urllib"):
        """Fetch with retry logic."""
        last_error = None
        for attempt in range(self.state["retries"] + 1):
            try:
                if method == "urllib":
                    return self._fetch_urllib(url)
                elif method == "curl":
                    return self._fetch_curl(url)
                elif method == "wget":
                    return self._fetch_wget(url)
                else:
                    return self._fetch_urllib(url)
            except Exception as e:
                last_error = str(e)
                if attempt < self.state["retries"]:
                    time.sleep(self.state["delay"] * (attempt + 1))
        raise RuntimeError("Fetch failed after " + str(self.state["retries"] + 1) + " attempts: " + last_error)

    def FetchPage(self, params):
        """Fetch a single page. Returns (1, data, None) or (0, None, error)."""
        url = self._p(params, "url")
        if not url:
            return (0, None, ("MISSING_PARAM", "url is required", 0))
        method = self._p(params, "method", "urllib")
        extract_text = self._p(params, "extract_text", False)
        extract_links = self._p(params, "extract_links", False)

        try:
            html = self._fetch_with_retry(url, method)
            self.state["pages_fetched"] += 1
            self.state["bytes_downloaded"] += len(html)

            result = {"url": url, "html": html, "length": len(html)}

            if extract_text:
                parser = TextExtractor()
                parser.feed(html)
                result["title"] = parser.title.strip()
                result["description"] = parser.meta_description
                result["text"] = parser.get_text(1000)

            if extract_links:
                parser = LinkExtractor()
                parser.feed(html)
                result["links"] = parser.links
                self.state["links_found"] += len(parser.links)

            return (1, result, None)
        except Exception as e:
            self.state["pages_failed"] += 1
            self.state["errors"].append({"url": url, "error": str(e)})
            return (0, None, ("FETCH_FAILED", str(e), 0))

    def FetchBatch(self, params):
        """Fetch multiple URLs in parallel. Returns (1, results, None)."""
        urls = self._p(params, "urls")
        if not urls:
            return (0, None, ("MISSING_PARAM", "urls list is required", 0))
        method = self._p(params, "method", "urllib")
        extract_text = self._p(params, "extract_text", False)
        extract_links = self._p(params, "extract_links", False)
        max_workers = self._p(params, "max_workers", self.state["max_workers"])

        results = []
        errors = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {}
            for url in urls:
                future = executor.submit(self.FetchPage, {
                    "url": url,
                    "method": method,
                    "extract_text": extract_text,
                    "extract_links": extract_links,
                })
                future_to_url[future] = url
                time.sleep(self.state["delay"])

            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    status, data, error = future.result()
                    if status == 1:
                        results.append(data)
                    else:
                        errors.append({"url": url, "error": str(error)})
                except Exception as e:
                    errors.append({"url": url, "error": str(e)})

        return (1, {"results": results, "errors": errors,
                     "fetched": len(results), "failed": len(errors)}, None)

    def MirrorSite(self, params):
        """Mirror an entire site using wget."""
        url = self._p(params, "url")
        if not url:
            return (0, None, ("MISSING_PARAM", "url is required", 0))
        output_dir = self._p(params, "output_dir", self.state["output_dir"])
        if not output_dir:
            return (0, None, ("MISSING_PARAM", "output_dir is required", 0))
        depth = self._p(params, "depth", 3)
        convert_links = self._p(params, "convert_links", True)
        page_requisites = self._p(params, "page_requisites", True)
        no_parent = self._p(params, "no_parent", True)

        os.makedirs(output_dir, exist_ok=True)

        cmd = ["wget", "--mirror", "--no-check-certificate",
               "-U", self.state["user_agent"],
               "-P", output_dir,
               "--level=" + str(depth)]
        if convert_links:
            cmd.append("--convert-links")
        if page_requisites:
            cmd.append("--page-requisites")
        if no_parent:
            cmd.append("--no-parent")
        cmd.append(url)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0 and result.stderr:
                self.state["errors"].append({"url": url, "error": result.stderr})
            self.state["pages_fetched"] += 1
            return (1, {"output_dir": output_dir, "url": url,
                         "stderr": result.stderr[:500]}, None)
        except subprocess.TimeoutExpired:
            return (0, None, ("TIMEOUT", "wget timed out after 600s", 0))
        except Exception as e:
            return (0, None, ("WGET_FAILED", str(e), 0))

    def ExtractLinks(self, params):
        """Extract links from HTML content or a URL."""
        html = self._p(params, "html")
        url = self._p(params, "url")
        if not html and not url:
            return (0, None, ("MISSING_PARAM", "html or url is required", 0))
        if url and not html:
            status, data, error = self.FetchPage({"url": url, "method": "urllib"})
            if status != 1:
                return (0, None, error)
            html = data["html"]

        parser = LinkExtractor()
        parser.feed(html)
        links = parser.links
        self.state["links_found"] += len(links)
        return (1, {"links": links, "count": len(links)}, None)

    def ParseIndex(self, params):
        """Parse an index page: extract links with their adjacent text as descriptions."""
        url = self._p(params, "url")
        html = self._p(params, "html")
        if not html and not url:
            return (0, None, ("MISSING_PARAM", "html or url is required", 0))
        if url and not html:
            status, data, error = self.FetchPage({"url": url, "method": "urllib"})
            if status != 1:
                return (0, None, error)
            html = data["html"]

        base_url = self._p(params, "base_url", url or "")
        if base_url and not base_url.endswith("/"):
            base_url = base_url.rsplit("/", 1)[0] + "/"

        parser = LinkExtractor()
        parser.feed(html)

        entries = []
        seen = set()
        for link in parser.links:
            href = link["href"]
            text = link["text"]
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            if href.startswith("http") and base_url and base_url not in href:
                continue
            if not href.startswith("http") and base_url:
                href = urllib.parse.urljoin(base_url, href)
            if href in seen:
                continue
            seen.add(href)
            entries.append({"url": href, "text": text})

        return (1, {"entries": entries, "count": len(entries)}, None)

    def SaveToDb(self, params):
        """Save scraped data to SQLite. Simple schema: id, url, text."""
        db_path = self._p(params, "db_path", self.state["db_path"])
        table = self._p(params, "table", "scraped_pages")
        data = self._p(params, "data")
        if not data:
            return (0, None, ("MISSING_PARAM", "data is required", 0))

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute("CREATE TABLE IF NOT EXISTS " + table + " ("
                     "id INTEGER PRIMARY KEY, "
                     "url TEXT NOT NULL UNIQUE, "
                     "text TEXT)")

        if isinstance(data, dict):
            data = [data]

        inserted = 0
        for item in data:
            url = item.get("url", "")
            text = item.get("text", "")
            if not text:
                parser = TextExtractor()
                parser.feed(item.get("html", ""))
                text = parser.get_text(2000)
            if url:
                cur.execute("INSERT OR REPLACE INTO " + table +
                             " (url, text) VALUES (?, ?)",
                             (url, text))
                inserted += 1

        conn.commit()
        conn.close()
        return (1, {"inserted": inserted, "table": table, "db_path": db_path}, None)


if __name__ == "__main__":
    scraper = WebScraper()

    # Demo: fetch ss64.com/mac/ index
    status, data, error = scraper.Run("parse_index", {
        "url": "https://ss64.com/mac/",
        "base_url": "https://ss64.com/mac/",
    })

    if status == 1:
        entries = data["entries"]
        print("Found " + str(len(entries)) + " links")
        for entry in entries[:10]:
            print("  " + entry["url"] + " -> " + entry["text"][:60])
    else:
        print("Error: " + str(error))
