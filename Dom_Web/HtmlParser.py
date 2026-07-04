#!/usr/bin/env python3
"""
#[@GHOST]{[@file<HtmlParser.py>][@state<active>][@date<2026-07-03>][@ver<2.0>][@auth<Cascade>]}
#[@VBSTYLE]{[@auth<system>][@role<web_component>][@return<Tuple3>][@orch<WebScraping>][@mem<none>][@db<none>]}
#[@FILEID]{[@path<HtmlParser.py>][@hash<placeholder>]}
#[@SUMMARY]{HTML parser for extracting structured data from HTML content}
#[@CLASS]{HtmlParser}
#[@METHOD]{__init__, parse, _create_parser, extract_text, extract_links, Run}
"""

from html.parser import HTMLParser
from typing import Optional, Tuple, List, Dict, Any
from urllib.parse import urljoin


class HtmlParser:
    """
    HTML parser for extracting structured data from HTML content.
    Uses Python's HTMLParser for token-level parsing.
    """

    def __init__(self, mem=None, db=None, param=None):
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
        try:
            parser = self._create_parser()
            parser.feed(html_content)
            return (1, self.state['current_data'], None)
        except Exception as e:
            return (0, None, (22, f"Extract error: {str(e)}", 0))

    def extract_links(self, html_content: str, base_url: Optional[str] = None) -> Tuple[int, List[str], Optional[Tuple]]:
        success, result, error = self.parse(html_content)
        if not success:
            return (0, [], error)
        links = result['links']
        if base_url:
            links = [urljoin(base_url, link) for link in links]
        return (1, links, None)

    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
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
            if not html_content:
                return (0, None, (25, "Missing required param: html", 0))
            return self.extract_links(html_content, params.get('base_url'))
        else:
            return (0, None, (26, f"Unknown command: {command}", 0))
