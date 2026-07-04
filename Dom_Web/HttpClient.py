#!/usr/bin/env python3
"""
#[@GHOST]{[@file<HttpClient.py>][@state<active>][@date<2026-07-03>][@ver<2.0>][@auth<Cascade>]}
#[@VBSTYLE]{[@auth<system>][@role<web_component>][@return<Tuple3>][@orch<WebScraping>][@mem<none>][@db<none>]}
#[@FILEID]{[@path<HttpClient.py>][@hash<placeholder>]}
#[@SUMMARY]{HTTP client for GET/POST requests with headers and auth}
#[@CLASS]{HttpClient}
#[@METHOD]{__init__, get, post, set_header, set_auth, Run}
"""

import urllib.request
import urllib.error
from typing import Optional, Tuple, Dict


class HttpClient:
    """
    HTTP client for making HTTP requests with various methods and headers.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
            'timeout': 30,
            'headers': {},
            'cookies': {},
            'auth': None
        }

    def get(self, url: str, headers: Optional[Dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        try:
            req_headers = self.state['headers'].copy()
            if headers:
                req_headers.update(headers)
            req = urllib.request.Request(url, headers=req_headers, method='GET')
            with urllib.request.urlopen(req, timeout=self.state['timeout']) as response:
                content = response.read().decode('utf-8', errors='ignore')
                return (1, content, None)
        except urllib.error.HTTPError as e:
            return (0, None, (40, f"HTTP Error {e.code}: {str(e)}", 0))
        except Exception as e:
            return (0, None, (41, f"Exception: {str(e)}", 0))

    def post(self, url: str, data: Optional[str] = None, headers: Optional[Dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        try:
            req_headers = self.state['headers'].copy()
            if headers:
                req_headers.update(headers)
            req_headers['Content-Type'] = 'application/json'
            req = urllib.request.Request(url, data=data.encode() if data else None,
                                         headers=req_headers, method='POST')
            with urllib.request.urlopen(req, timeout=self.state['timeout']) as response:
                content = response.read().decode('utf-8', errors='ignore')
                return (1, content, None)
        except urllib.error.HTTPError as e:
            return (0, None, (42, f"HTTP Error {e.code}: {str(e)}", 0))
        except Exception as e:
            return (0, None, (43, f"Exception: {str(e)}", 0))

    def set_header(self, key: str, value: str) -> Tuple[int, str, Optional[Tuple]]:
        self.state['headers'][key] = value
        return (1, value, None)

    def set_auth(self, username: str, password: str) -> Tuple[int, str, Optional[Tuple]]:
        import base64
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.state['headers']['Authorization'] = f"Basic {credentials}"
        return (1, "Auth set", None)

    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        if params is None:
            params = {}
        if command == "get":
            url = params.get('url')
            if not url:
                return (0, None, (44, "Missing required param: url", 0))
            return self.get(url, params.get('headers'))
        elif command == "post":
            url = params.get('url')
            if not url:
                return (0, None, (45, "Missing required param: url", 0))
            return self.post(url, params.get('data'), params.get('headers'))
        elif command == "set_header":
            key = params.get('key')
            value = params.get('value')
            if not key or not value:
                return (0, None, (46, "Missing required params: key, value", 0))
            return self.set_header(key, value)
        elif command == "set_auth":
            username = params.get('username')
            password = params.get('password')
            if not username or not password:
                return (0, None, (47, "Missing required params: username, password", 0))
            return self.set_auth(username, password)
        else:
            return (0, None, (48, f"Unknown command: {command}", 0))
