#!/usr/bin/env python3
"""
#[@GHOST]{[@file<Dom_Web_v2.py>][@state<active>][@date<2026-07-03>][@ver<2.0>][@auth<Cascade>]}
#[@VBSTYLE]{[@auth<system>][@role<web_domain>][@return<Tuple3>][@orch<WebScraping>][@mem<none>][@db<none>]}
#[@FILEID]{[@path<Dom_Web_v2.py>][@hash<placeholder>]}
#[@SUMMARY]{Dom_Web v2 - web scraping orchestrator with component classes, improved structure}
#[@CLASS]{WebScraping, WebScraperWithWgetFallback, HtmlParser, XmlParser, JsonParser, HttpClient, HttpRequestBuilder, WebCrawler, LinkExtractor}
#[@METHOD]{__init__, fetch, parse, extract, build, crawl, Run, read_state, SetConfig}
"""

import os
import subprocess
import urllib.request
import urllib.error
import urllib.parse
import re
import json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Optional, Tuple, List, Dict, Any
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser


class WebScraperWithWgetFallback:
    """
    Web scraper that uses Python urllib.request as primary method
    and falls back to wget via subprocess if Python method fails.
    Implements common wget options for mirroring and downloading.
    """
    
    def __init__(self, mem=None, db=None, param=None):
        """Initialize scraper with configuration"""
        self.state = {
            'use_wget_fallback': True,
            'wget_path': '/usr/local/bin/wget',
            'timeout': 30,
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
            'output_dir': './downloads',
            'last_method_used': None,
            'last_error': None
        }
        
        os.makedirs(self.state['output_dir'], exist_ok=True)
    
    def fetch(self, url: str, output_file: Optional[str] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Fetch URL using urllib.request, fallback to wget if fails"""
        success, content, error = self.fetch_with_urllib(url, output_file)
        
        if success:
            self.state['last_method_used'] = 'urllib'
            return (1, content, None)
        
        if self.state['use_wget_fallback']:
            self.state['last_error'] = str(error)
            success, content, error = self.fetch_with_wget(url, output_file)
            
            if success:
                self.state['last_method_used'] = 'wget'
                return (1, content, None)
            else:
                self.state['last_error'] = str(error)
                return (0, None, error)
        
        return (0, None, error)
    
    def fetch_with_urllib(self, url: str, output_file: Optional[str] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Fetch URL using Python urllib.request"""
        try:
            headers = {'User-Agent': self.state['user_agent']}
            req = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=self.state['timeout']) as response:
                content = response.read().decode('utf-8', errors='ignore')
                
                if output_file:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                
                return (1, content, None)
                
        except urllib.error.URLError as e:
            return (0, None, (1, f"URL Error: {str(e)}", 0))
        except urllib.error.HTTPError as e:
            return (0, None, (2, f"HTTP Error: {e.code} - {str(e)}", 0))
        except Exception as e:
            return (0, None, (3, f"Exception: {str(e)}", 0))
    
    def fetch_with_wget(self, url: str, output_file: Optional[str] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Fetch URL using wget via subprocess"""
        try:
            cmd = [self.state['wget_path']]
            cmd.extend([
                '--user-agent', self.state['user_agent'],
                '--timeout', str(self.state['timeout']),
                '--no-check-certificate'
            ])
            
            if output_file:
                cmd.extend(['-O', output_file])
            else:
                cmd.extend(['-O', '-'])
            
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.state['timeout'] + 10
            )
            
            if result.returncode == 0:
                content = result.stdout
                return (1, content, None)
            else:
                return (0, None, (4, f"Wget failed (code {result.returncode}): {result.stderr}", 0))
                
        except subprocess.TimeoutExpired:
            return (0, None, (5, "Wget timeout", 0))
        except FileNotFoundError:
            return (0, None, (6, f"Wget not found at {self.state['wget_path']}", 0))
        except Exception as e:
            return (0, None, (7, f"Exception: {str(e)}", 0))
    
    def mirror_site(self, url: str, options: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Mirror a website using wget with mirroring options"""
        if options is None:
            options = {}
        
        try:
            cmd = [self.state['wget_path']]
            cmd.append('--mirror')
            
            if options.get('convert_links', True):
                cmd.append('--convert-links')
            
            if options.get('adjust_extension', True):
                cmd.append('--adjust-extension')
            
            if options.get('page_requisites', True):
                cmd.append('--page-requisites')
            
            if options.get('no_parent', True):
                cmd.append('--no-parent')
            
            if 'reject' in options and options['reject']:
                cmd.extend(['--reject', ','.join(options['reject'])])
            
            if 'accept' in options and options['accept']:
                cmd.extend(['--accept', ','.join(options['accept'])])
            
            if 'exclude_dirs' in options and options['exclude_dirs']:
                for directory in options['exclude_dirs']:
                    cmd.extend(['--exclude-directories', directory])
            
            cmd.extend([
                '--user-agent', self.state['user_agent'],
                '--no-check-certificate',
                '--timeout', str(self.state['timeout'])
            ])
            
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                output = f"Site mirrored successfully to {self.state['output_dir']}"
                return (1, output, None)
            else:
                return (0, None, (9, f"Mirror failed (code {result.returncode}): {result.stderr}", 0))
                
        except subprocess.TimeoutExpired:
            return (0, None, (10, "Mirror timeout", 0))
        except Exception as e:
            return (0, None, (11, f"Exception: {str(e)}", 0))
    
    def download_file(self, url: str, filename: Optional[str] = None, 
                     resume: bool = False, limit_rate: Optional[str] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Download a single file with optional resume and rate limiting"""
        try:
            cmd = [self.state['wget_path']]
            
            if resume:
                cmd.append('-c')
            
            if limit_rate:
                cmd.extend(['--limit-rate', limit_rate])
            
            if filename:
                output_path = os.path.join(self.state['output_dir'], filename)
                cmd.extend(['-O', output_path])
            else:
                cmd.extend(['-P', self.state['output_dir']])
            
            cmd.extend([
                '--user-agent', self.state['user_agent'],
                '--no-check-certificate',
                '--timeout', str(self.state['timeout'])
            ])
            
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.state['timeout'] + 60
            )
            
            if result.returncode == 0:
                if filename:
                    filepath = os.path.join(self.state['output_dir'], filename)
                else:
                    parsed = urlparse(url)
                    filepath = os.path.join(self.state['output_dir'], 
                                           os.path.basename(parsed.path))
                
                return (1, filepath, None)
            else:
                return (0, None, (12, f"Download failed (code {result.returncode}): {result.stderr}", 0))
                
        except subprocess.TimeoutExpired:
            return (0, None, (13, "Download timeout", 0))
        except Exception as e:
            return (0, None, (14, f"Exception: {str(e)}", 0))
    
    def set_config(self, key: str, value) -> Tuple[int, str, Optional[Tuple]]:
        """Set configuration value"""
        if key in self.state:
            self.state[key] = value
            return (1, str(value), None)
        else:
            return (0, None, (15, f"Unknown config key: {key}", 0))
    
    def get_config(self, key: str) -> Tuple[int, str, Optional[Tuple]]:
        """Get configuration value"""
        if key in self.state:
            return (1, str(self.state[key]), None)
        else:
            return (0, None, (16, f"Unknown config key: {key}", 0))
    
    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Dispatch commands for the scraper"""
        if params is None:
            params = {}
        
        if command == "fetch":
            url = params.get('url')
            output_file = params.get('output_file')
            
            if not url:
                return (0, None, (17, "Missing required param: url", 0))
            
            return self.fetch(url, output_file)
        
        elif command == "mirror":
            url = params.get('url')
            options = params.get('options')
            
            if not url:
                return (0, None, (18, "Missing required param: url", 0))
            
            return self.mirror_site(url, options)
        
        elif command == "download":
            url = params.get('url')
            filename = params.get('filename')
            resume = params.get('resume', False)
            limit_rate = params.get('limit_rate')
            
            if not url:
                return (0, None, (19, "Missing required param: url", 0))
            
            return self.download_file(url, filename, resume, limit_rate)
        
        elif command == "config":
            key = params.get('key')
            value = params.get('value')
            
            if value is not None:
                return self.set_config(key, value)
            else:
                return self.get_config(key)
        
        elif command == "status":
            status_info = {
                'last_method_used': self.state['last_method_used'],
                'last_error': self.state['last_error'],
                'use_wget_fallback': self.state['use_wget_fallback'],
                'wget_path': self.state['wget_path'],
                'output_dir': self.state['output_dir']
            }
            return (1, json.dumps(status_info, indent=2), None)
        
        else:
            return (0, None, (20, f"Unknown command: {command}", 0))


class HtmlParser:
    """
    HTML parser for extracting structured data from HTML content.
    Uses Python's HTMLParser for token-level parsing.
    """
    
    def __init__(self, mem=None, db=None, param=None):
        """Initialize HTML parser"""
        self.state = {
            'current_tag': None,
            'current_attrs': {},
            'current_data': '',
            'in_script': False,
            'in_style': False,
            'links': [],
            'images': [],
            'headings': [],
            'metadata': {}
        }
    
    def parse(self, html_content: str) -> Tuple[int, Dict[str, Any], Optional[Tuple]]:
        """Parse HTML content and extract structured data"""
        try:
            parser = self._create_parser()
            parser.feed(html_content)
            
            result = {
                'links': self.state['links'],
                'images': self.state['images'],
                'headings': self.state['headings'],
                'metadata': self.state['metadata']
            }
            
            return (1, result, None)
            
        except Exception as e:
            return (0, None, (21, f"Parse error: {str(e)}", 0))
    
    def _create_parser(self) -> HTMLParser:
        """Create and configure HTML parser"""
        class DomHtmlParser(HTMLParser):
            def __init__(self, outer_self):
                super().__init__()
                self.outer = outer_self
            
            def handle_starttag(self, tag, attrs):
                self.outer.state['current_tag'] = tag
                self.outer.state['current_attrs'] = dict(attrs)
                
                if tag == 'script':
                    self.outer.state['in_script'] = True
                elif tag == 'style':
                    self.outer.state['in_style'] = True
                elif tag == 'a':
                    href = dict(attrs).get('href')
                    if href:
                        self.outer.state['links'].append(href)
                elif tag == 'img':
                    src = dict(attrs).get('src')
                    if src:
                        self.outer.state['images'].append(src)
                elif tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    self.outer.state['headings'].append({
                        'tag': tag,
                        'attrs': dict(attrs)
                    })
                elif tag == 'meta':
                    meta_attrs = dict(attrs)
                    name = meta_attrs.get('name') or meta_attrs.get('property')
                    content = meta_attrs.get('content')
                    if name and content:
                        self.outer.state['metadata'][name] = content
            
            def handle_endtag(self, tag):
                if tag == 'script':
                    self.outer.state['in_script'] = False
                elif tag == 'style':
                    self.outer.state['in_style'] = False
                self.outer.state['current_tag'] = None
                self.outer.state['current_attrs'] = {}
            
            def handle_data(self, data):
                if not self.outer.state['in_script'] and not self.outer.state['in_style']:
                    self.outer.state['current_data'] += data
        
        return DomHtmlParser(self)
    
    def extract_text(self, html_content: str) -> Tuple[int, str, Optional[Tuple]]:
        """Extract plain text from HTML"""
        try:
            parser = self._create_parser()
            parser.feed(html_content)
            return (1, self.state['current_data'], None)
        except Exception as e:
            return (0, None, (22, f"Extract error: {str(e)}", 0))
    
    def extract_links(self, html_content: str, base_url: Optional[str] = None) -> Tuple[int, List[str], Optional[Tuple]]:
        """Extract all links from HTML, optionally resolving relative URLs"""
        success, result, error = self.parse(html_content)
        if not success:
            return (0, [], error)
        
        links = result['links']
        
        if base_url:
            links = [urljoin(base_url, link) for link in links]
        
        return (1, links, None)
    
    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Dispatch commands for HTML parser"""
        if params is None:
            params = {}
        
        if command == "parse":
            html_content = params.get('html')
            if not html_content:
                return (0, None, (23, "Missing required param: html", 0))
            return self.parse(html_content)
        
        elif command == "extract_text":
            html_content = params.get('html')
            if not html_content:
                return (0, None, (24, "Missing required param: html", 0))
            return self.extract_text(html_content)
        
        elif command == "extract_links":
            html_content = params.get('html')
            base_url = params.get('base_url')
            if not html_content:
                return (0, None, (25, "Missing required param: html", 0))
            return self.extract_links(html_content, base_url)
        
        else:
            return (0, None, (26, f"Unknown command: {command}", 0))


class XmlParser:
    """
    XML parser for extracting structured data from XML content.
    Uses Python's ElementTree for parsing.
    """
    
    def __init__(self, mem=None, db=None, param=None):
        """Initialize XML parser"""
        self.state = {
            'root': None,
            'elements': [],
            'attributes': {}
        }
    
    def parse(self, xml_content: str) -> Tuple[int, Dict[str, Any], Optional[Tuple]]:
        """Parse XML content and extract structured data"""
        try:
            root = ET.fromstring(xml_content)
            self.state['root'] = root.tag
            
            elements = []
            for elem in root.iter():
                elements.append({
                    'tag': elem.tag,
                    'text': elem.text,
                    'attributes': elem.attrib
                })
            
            self.state['elements'] = elements
            return (1, {'root': root.tag, 'elements': elements}, None)
            
        except ET.ParseError as e:
            return (0, None, (27, f"Parse error: {str(e)}", 0))
        except Exception as e:
            return (0, None, (28, f"Exception: {str(e)}", 0))
    
    def extract_elements(self, xml_content: str, tag: Optional[str] = None) -> Tuple[int, List[Dict], Optional[Tuple]]:
        """Extract elements by tag name"""
        success, result, error = self.parse(xml_content)
        if not success:
            return (0, [], error)
        
        if tag:
            elements = [e for e in result['elements'] if e['tag'] == tag]
        else:
            elements = result['elements']
        
        return (1, elements, None)
    
    def extract_attributes(self, xml_content: str, tag: str) -> Tuple[int, Dict[str, str], Optional[Tuple]]:
        """Extract attributes from elements with given tag"""
        success, elements, error = self.extract_elements(xml_content, tag)
        if not success:
            return (0, {}, error)
        
        if elements:
            return (1, elements[0]['attributes'], None)
        else:
            return (1, {}, None)
    
    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Dispatch commands for XML parser"""
        if params is None:
            params = {}
        
        if command == "parse":
            xml_content = params.get('xml')
            if not xml_content:
                return (0, None, (29, "Missing required param: xml", 0))
            return self.parse(xml_content)
        
        elif command == "extract_elements":
            xml_content = params.get('xml')
            tag = params.get('tag')
            if not xml_content:
                return (0, None, (30, "Missing required param: xml", 0))
            return self.extract_elements(xml_content, tag)
        
        elif command == "extract_attributes":
            xml_content = params.get('xml')
            tag = params.get('tag')
            if not xml_content or not tag:
                return (0, None, (31, "Missing required params: xml, tag", 0))
            return self.extract_attributes(xml_content, tag)
        
        else:
            return (0, None, (32, f"Unknown command: {command}", 0))


class JsonParser:
    """
    JSON parser for extracting structured data from JSON content.
    """
    
    def __init__(self, mem=None, db=None, param=None):
        """Initialize JSON parser"""
        self.state = {
            'parsed': None,
            'keys': [],
            'structure': {}
        }
    
    def parse(self, json_content: str) -> Tuple[int, Dict[str, Any], Optional[Tuple]]:
        """Parse JSON content"""
        try:
            parsed = json.loads(json_content)
            self.state['parsed'] = parsed
            self.state['keys'] = list(parsed.keys()) if isinstance(parsed, dict) else []
            return (1, parsed, None)
        except json.JSONDecodeError as e:
            return (0, None, (33, f"JSON decode error: {str(e)}", 0))
        except Exception as e:
            return (0, None, (34, f"Exception: {str(e)}", 0))
    
    def extract_value(self, json_content: str, key_path: str) -> Tuple[int, Any, Optional[Tuple]]:
        """Extract value by key path (dot notation)"""
        success, parsed, error = self.parse(json_content)
        if not success:
            return (0, None, error)
        
        try:
            keys = key_path.split('.')
            value = parsed
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                elif isinstance(value, list) and key.isdigit():
                    value = value[int(key)]
                else:
                    return (0, None, (35, f"Key path not found: {key_path}", 0))
            
            return (1, value, None)
        except Exception as e:
            return (0, None, (36, f"Extract error: {str(e)}", 0))
    
    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Dispatch commands for JSON parser"""
        if params is None:
            params = {}
        
        if command == "parse":
            json_content = params.get('json')
            if not json_content:
                return (0, None, (37, "Missing required param: json", 0))
            return self.parse(json_content)
        
        elif command == "extract_value":
            json_content = params.get('json')
            key_path = params.get('key_path')
            if not json_content or not key_path:
                return (0, None, (38, "Missing required params: json, key_path", 0))
            return self.extract_value(json_content, key_path)
        
        else:
            return (0, None, (39, f"Unknown command: {command}", 0))


class HttpClient:
    """
    HTTP client for making HTTP requests with various methods and headers.
    """
    
    def __init__(self, mem=None, db=None, param=None):
        """Initialize HTTP client"""
        self.state = {
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
            'timeout': 30,
            'headers': {},
            'cookies': {},
            'auth': None
        }
    
    def get(self, url: str, headers: Optional[Dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Make GET request"""
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
        """Make POST request"""
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
        """Set HTTP header"""
        self.state['headers'][key] = value
        return (1, value, None)
    
    def set_auth(self, username: str, password: str) -> Tuple[int, str, Optional[Tuple]]:
        """Set basic authentication"""
        import base64
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.state['headers']['Authorization'] = f"Basic {credentials}"
        return (1, "Auth set", None)
    
    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Dispatch commands for HTTP client"""
        if params is None:
            params = {}
        
        if command == "get":
            url = params.get('url')
            headers = params.get('headers')
            if not url:
                return (0, None, (44, "Missing required param: url", 0))
            return self.get(url, headers)
        
        elif command == "post":
            url = params.get('url')
            data = params.get('data')
            headers = params.get('headers')
            if not url:
                return (0, None, (45, "Missing required param: url", 0))
            return self.post(url, data, headers)
        
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


class HttpRequestBuilder:
    """
    Builder for constructing HTTP requests with various options.
    """
    
    def __init__(self, mem=None, db=None, param=None):
        """Initialize request builder"""
        self.state = {
            'method': 'GET',
            'url': None,
            'headers': {},
            'data': None,
            'timeout': 30
        }
    
    def set_method(self, method: str) -> Tuple[int, str, Optional[Tuple]]:
        """Set HTTP method"""
        self.state['method'] = method.upper()
        return (1, self.state['method'], None)
    
    def set_url(self, url: str) -> Tuple[int, str, Optional[Tuple]]:
        """Set request URL"""
        self.state['url'] = url
        return (1, url, None)
    
    def add_header(self, key: str, value: str) -> Tuple[int, str, Optional[Tuple]]:
        """Add HTTP header"""
        self.state['headers'][key] = value
        return (1, value, None)
    
    def set_data(self, data: str) -> Tuple[int, str, Optional[Tuple]]:
        """Set request body data"""
        self.state['data'] = data
        return (1, data, None)
    
    def build(self) -> Tuple[int, urllib.request.Request, Optional[Tuple]]:
        """Build the HTTP request"""
        if not self.state['url']:
            return (0, None, (49, "URL not set", 0))
        
        try:
            req = urllib.request.Request(
                self.state['url'],
                data=self.state['data'].encode() if self.state['data'] else None,
                headers=self.state['headers'],
                method=self.state['method']
            )
            return (1, req, None)
        except Exception as e:
            return (0, None, (50, f"Build error: {str(e)}", 0))
    
    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Dispatch commands for request builder"""
        if params is None:
            params = {}
        
        if command == "set_method":
            method = params.get('method')
            if not method:
                return (0, None, (51, "Missing required param: method", 0))
            return self.set_method(method)
        
        elif command == "set_url":
            url = params.get('url')
            if not url:
                return (0, None, (52, "Missing required param: url", 0))
            return self.set_url(url)
        
        elif command == "add_header":
            key = params.get('key')
            value = params.get('value')
            if not key or not value:
                return (0, None, (53, "Missing required params: key, value", 0))
            return self.add_header(key, value)
        
        elif command == "set_data":
            data = params.get('data')
            if not data:
                return (0, None, (54, "Missing required param: data", 0))
            return self.set_data(data)
        
        elif command == "build":
            return self.build()
        
        else:
            return (0, None, (55, f"Unknown command: {command}", 0))


class WebCrawler:
    """
    Web crawler for discovering and following links within a domain.
    """
    
    def __init__(self, mem=None, db=None, param=None):
        """Initialize web crawler"""
        self.state = {
            'visited_urls': set(),
            'queue': [],
            'max_depth': 3,
            'current_depth': 0,
            'allowed_domains': [],
            'robots_txt': {},
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        }
    
    def crawl(self, start_url: str, max_depth: int = 3) -> Tuple[int, List[str], Optional[Tuple]]:
        """Crawl starting from URL to specified depth"""
        self.state['queue'] = [(start_url, 0)]
        self.state['max_depth'] = max_depth
        self.state['visited_urls'] = set()
        
        discovered_urls = []
        
        while self.state['queue']:
            url, depth = self.state['queue'].pop(0)
            
            if depth > self.state['max_depth']:
                continue
            
            if url in self.state['visited_urls']:
                continue
            
            self.state['visited_urls'].add(url)
            discovered_urls.append(url)
            
            try:
                scraper = WebScraperWithWgetFallback()
                success, content, error = scraper.fetch(url)
                
                if success:
                    parser = HtmlParser()
                    success, links, error = parser.extract_links(content, url)
                    
                    if success:
                        for link in links:
                            if link not in self.state['visited_urls']:
                                self.state['queue'].append((link, depth + 1))
                
            except Exception as e:
                continue
        
        return (1, discovered_urls, None)
    
    def check_robots_txt(self, url: str) -> Tuple[int, bool, Optional[Tuple]]:
        """Check if URL is allowed by robots.txt"""
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            allowed = rp.can_fetch(self.state['user_agent'], url)
            return (1, allowed, None)
            
        except Exception as e:
            return (0, None, (56, f"Robots.txt check error: {str(e)}", 0))
    
    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Dispatch commands for web crawler"""
        if params is None:
            params = {}
        
        if command == "crawl":
            start_url = params.get('start_url')
            max_depth = params.get('max_depth', 3)
            if not start_url:
                return (0, None, (57, "Missing required param: start_url", 0))
            return self.crawl(start_url, max_depth)
        
        elif command == "check_robots_txt":
            url = params.get('url')
            if not url:
                return (0, None, (58, "Missing required param: url", 0))
            return self.check_robots_txt(url)
        
        else:
            return (0, None, (59, f"Unknown command: {command}", 0))


class LinkExtractor:
    """
    Extract and classify links from HTML content.
    """
    
    def __init__(self, mem=None, db=None, param=None):
        """Initialize link extractor"""
        self.state = {
            'internal_links': [],
            'external_links': [],
            'anchor_links': [],
            'resource_links': []
        }
    
    def extract(self, html_content: str, base_url: str) -> Tuple[int, Dict[str, List[str]], Optional[Tuple]]:
        """Extract and classify all links from HTML"""
        try:
            parser = HtmlParser()
            success, links, error = parser.extract_links(html_content, base_url)
            
            if not success:
                return (0, {}, error)
            
            base_domain = urlparse(base_url).netloc
            
            for link in links:
                parsed = urlparse(link)
                
                if parsed.netloc == base_domain:
                    self.state['internal_links'].append(link)
                elif parsed.netloc:
                    self.state['external_links'].append(link)
                
                if parsed.fragment:
                    self.state['anchor_links'].append(link)
                
                if parsed.path.lower().endswith(('.css', '.js', '.png', '.jpg', '.gif', '.svg')):
                    self.state['resource_links'].append(link)
            
            result = {
                'internal': self.state['internal_links'],
                'external': self.state['external_links'],
                'anchors': self.state['anchor_links'],
                'resources': self.state['resource_links']
            }
            
            return (1, result, None)
            
        except Exception as e:
            return (0, None, (60, f"Extract error: {str(e)}", 0))
    
    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Dispatch commands for link extractor"""
        if params is None:
            params = {}
        
        if command == "extract":
            html_content = params.get('html')
            base_url = params.get('base_url')
            if not html_content or not base_url:
                return (0, None, (61, "Missing required params: html, base_url", 0))
            return self.extract(html_content, base_url)
        
        else:
            return (0, None, (62, f"Unknown command: {command}", 0))


class WebScraping:
    """
    Web scraping orchestrator. Coordinates all web domain components.
    Dispatches commands to specialized component classes.
    """
    
    def __init__(self, mem=None, db=None, param=None):
        """Initialize orchestrator with all component instances"""
        self.state = {
            'config': {},
            'catalog': [],
            'results': [],
            'errors': [],
            'meta': {
                'components_initialized': False,
                'last_command': None,
                'last_component': None,
            },
        }
        self.scraper = WebScraperWithWgetFallback()
        self.html_parser = HtmlParser()
        self.xml_parser = XmlParser()
        self.json_parser = JsonParser()
        self.http_client = HttpClient()
        self.request_builder = HttpRequestBuilder()
        self.crawler = WebCrawler()
        self.link_extractor = LinkExtractor()
        self.config = None
        try:
            from Config_Web import Config
            self.config = Config()
        except Exception:
            pass
        self.state['meta']['components_initialized'] = True
    
    def _p(self, params, key, default=None):
        """Extract param value"""
        if not params:
            return default
        return params.get(key, default)
    
    def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:
        """Return state snapshot"""
        return (1, self.state, None)
    
    def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Update orchestrator config"""
        if not params:
            return (0, None, (100, "Missing config params", 0))
        self.state['config'].update(params)
        return (1, "Config updated", None)
    
    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:
        """
        Dispatch commands to component classes.
        
        Commands:
            Scraper: fetch, mirror, download, scraper_status, scraper_config
            HTML: parse_html, extract_text, extract_links
            XML: parse_xml, extract_xml_elements, extract_xml_attributes
            JSON: parse_json, extract_json_value
            HTTP: http_get, http_post, set_header, set_auth
            Builder: set_method, set_url, add_header, set_data, build_request
            Crawler: crawl, check_robots_txt
            Links: extract_links_classified
            Config: config_get, config_set, config_get_all, get_download_dir, get_cache_dir, get_log_dir
            Meta: read_state, set_config
        """
        if params is None:
            params = {}
        
        self.state['meta']['last_command'] = command
        
        if command in ("fetch", "mirror", "download", "scraper_status", "scraper_config"):
            self.state['meta']['last_component'] = 'scraper'
            cmd_map = {"scraper_status": "status", "scraper_config": "config"}
            actual_cmd = cmd_map.get(command, command)
            return self.scraper.Run(actual_cmd, params)
        
        if command in ("parse_html", "extract_text", "extract_links"):
            self.state['meta']['last_component'] = 'html_parser'
            cmd_map = {"parse_html": "parse"}
            actual_cmd = cmd_map.get(command, command)
            return self.html_parser.Run(actual_cmd, params)
        
        if command in ("parse_xml", "extract_xml_elements", "extract_xml_attributes"):
            self.state['meta']['last_component'] = 'xml_parser'
            cmd_map = {
                "parse_xml": "parse",
                "extract_xml_elements": "extract_elements",
                "extract_xml_attributes": "extract_attributes",
            }
            return self.xml_parser.Run(cmd_map[command], params)
        
        if command in ("parse_json", "extract_json_value"):
            self.state['meta']['last_component'] = 'json_parser'
            cmd_map = {
                "parse_json": "parse",
                "extract_json_value": "extract_value",
            }
            return self.json_parser.Run(cmd_map[command], params)
        
        if command in ("http_get", "http_post", "set_header", "set_auth"):
            self.state['meta']['last_component'] = 'http_client'
            cmd_map = {"http_get": "get", "http_post": "post"}
            actual_cmd = cmd_map.get(command, command)
            return self.http_client.Run(actual_cmd, params)
        
        if command in ("set_method", "set_url", "add_header", "set_data", "build_request"):
            self.state['meta']['last_component'] = 'request_builder'
            cmd_map = {"build_request": "build"}
            actual_cmd = cmd_map.get(command, command)
            return self.request_builder.Run(actual_cmd, params)
        
        if command in ("crawl", "check_robots_txt"):
            self.state['meta']['last_component'] = 'crawler'
            return self.crawler.Run(command, params)
        
        if command == "extract_links_classified":
            self.state['meta']['last_component'] = 'link_extractor'
            return self.link_extractor.Run("extract", params)
        
        if command in ("config_get", "config_set", "config_get_all", "get_download_dir", "get_cache_dir", "get_log_dir"):
            self.state['meta']['last_component'] = 'config'
            if self.config is None:
                return (0, None, (101, "Config not initialized", 0))
            cmd_map = {
                "config_get": "get",
                "config_set": "set",
                "config_get_all": "get_all",
            }
            actual_cmd = cmd_map.get(command, command)
            return self.config.Run(actual_cmd, params)
        
        if command == "read_state":
            return self.read_state()
        
        if command == "set_config":
            return self.SetConfig(params)
        
        return (0, None, (102, f"Unknown command: {command}", 0))
