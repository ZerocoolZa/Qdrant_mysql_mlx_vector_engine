#!/usr/bin/env python3
"""
#[@GHOST]{[@file<WebScraperWithWgetFallback.py>][@state<active>][@date<2026-07-03>][@ver<2.0>][@auth<Cascade>]}
#[@VBSTYLE]{[@auth<system>][@role<web_component>][@return<Tuple3>][@orch<WebScraping>][@mem<none>][@db<none>]}
#[@FILEID]{[@path<WebScraperWithWgetFallback.py>][@hash<placeholder>]}
#[@SUMMARY]{Web scraper with urllib primary and wget fallback}
#[@CLASS]{WebScraperWithWgetFallback}
#[@METHOD]{__init__, fetch, fetch_with_urllib, fetch_with_wget, mirror_site, download_file, set_config, get_config, Run}
"""

import os
import subprocess
import urllib.request
import urllib.error
import json
from typing import Optional, Tuple
from urllib.parse import urlparse


class WebScraperWithWgetFallback:
    """
    Web scraper that uses Python urllib.request as primary method
    and falls back to wget via subprocess if Python method fails.
    """

    def __init__(self, mem=None, db=None, param=None):
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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.state['timeout'] + 10)
            if result.returncode == 0:
                return (1, result.stdout, None)
            else:
                return (0, None, (4, f"Wget failed (code {result.returncode}): {result.stderr}", 0))
        except subprocess.TimeoutExpired:
            return (0, None, (5, "Wget timeout", 0))
        except FileNotFoundError:
            return (0, None, (6, f"Wget not found at {self.state['wget_path']}", 0))
        except Exception as e:
            return (0, None, (7, f"Exception: {str(e)}", 0))

    def mirror_site(self, url: str, options: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        if options is None:
            options = {}
        try:
            cmd = [self.state['wget_path'], '--mirror']
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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                return (1, f"Site mirrored successfully to {self.state['output_dir']}", None)
            else:
                return (0, None, (9, f"Mirror failed (code {result.returncode}): {result.stderr}", 0))
        except subprocess.TimeoutExpired:
            return (0, None, (10, "Mirror timeout", 0))
        except Exception as e:
            return (0, None, (11, f"Exception: {str(e)}", 0))

    def download_file(self, url: str, filename: Optional[str] = None,
                      resume: bool = False, limit_rate: Optional[str] = None) -> Tuple[int, str, Optional[Tuple]]:
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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.state['timeout'] + 60)
            if result.returncode == 0:
                if filename:
                    filepath = os.path.join(self.state['output_dir'], filename)
                else:
                    parsed = urlparse(url)
                    filepath = os.path.join(self.state['output_dir'], os.path.basename(parsed.path))
                return (1, filepath, None)
            else:
                return (0, None, (12, f"Download failed (code {result.returncode}): {result.stderr}", 0))
        except subprocess.TimeoutExpired:
            return (0, None, (13, "Download timeout", 0))
        except Exception as e:
            return (0, None, (14, f"Exception: {str(e)}", 0))

    def set_config(self, key: str, value) -> Tuple[int, str, Optional[Tuple]]:
        if key in self.state:
            self.state[key] = value
            return (1, str(value), None)
        return (0, None, (15, f"Unknown config key: {key}", 0))

    def get_config(self, key: str) -> Tuple[int, str, Optional[Tuple]]:
        if key in self.state:
            return (1, str(self.state[key]), None)
        return (0, None, (16, f"Unknown config key: {key}", 0))

    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        if params is None:
            params = {}
        if command == "fetch":
            url = params.get('url')
            if not url:
                return (0, None, (17, "Missing required param: url", 0))
            return self.fetch(url, params.get('output_file'))
        elif command == "mirror":
            url = params.get('url')
            if not url:
                return (0, None, (18, "Missing required param: url", 0))
            return self.mirror_site(url, params.get('options'))
        elif command == "download":
            url = params.get('url')
            if not url:
                return (0, None, (19, "Missing required param: url", 0))
            return self.download_file(url, params.get('filename'), params.get('resume', False), params.get('limit_rate'))
        elif command == "config":
            key = params.get('key')
            value = params.get('value')
            if value is not None:
                return self.set_config(key, value)
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
