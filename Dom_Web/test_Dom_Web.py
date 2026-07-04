#!/usr/bin/env python3
"""
#[@GHOST]{[@file<test_Dom_Web.py>][@state<active>][@date<2026-07-03>][@ver<1.0>][@auth<Cascade>]}
#[@VBSTYLE]{[@auth<system>][@role<test>][@return<Tuple3>][@orch<none>][@mem<none>][@db<none>]}
#[@FILEID]{[@path<test_Dom_Web.py>][@hash<placeholder>]}
#[@SUMMARY]{Test Dom_Web domain classes}
#[@CLASS]{TestDomWeb}
#[@METHOD]{__init__, test_all, test_scraper, test_parser, test_http, test_crawler, test_link_extractor, test_config, Run}
"""

import sys
import os
from typing import Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Dom_Web import (
    WebScraping,
    WebScraperWithWgetFallback,
    HtmlParser,
    XmlParser,
    JsonParser,
    HttpClient,
    HttpRequestBuilder,
    WebCrawler,
    LinkExtractor
)
from Config_Web import Config


class TestDomWeb:
    """Test suite for Dom_Web domain classes"""
    
    def __init__(self, mem=None, db=None, param=None):
        """Initialize test suite"""
        self.state = {
            'results': [],
            'passed': 0,
            'failed': 0
        }
    
    def _record_result(self, test_name: str, passed: bool, message: str = ""):
        """Record test result"""
        self.state['results'].append({
            'test': test_name,
            'passed': passed,
            'message': message
        })
        if passed:
            self.state['passed'] += 1
        else:
            self.state['failed'] += 1
    
    def test_scraper(self) -> Tuple[int, str, Optional[Tuple]]:
        """Test WebScraperWithWgetFallback class"""
        scraper = WebScraperWithWgetFallback()
        
        success, content, error = scraper.fetch("https://example.com")
        if success and content:
            self._record_result("WebScraper fetch", True, f"Fetched {len(content)} chars")
        else:
            self._record_result("WebScraper fetch", False, str(error))
        
        success, status, error = scraper.Run("status")
        if success:
            self._record_result("WebScraper status", True)
        else:
            self._record_result("WebScraper status", False, str(error))
        
        return (1, "WebScraper tests complete", None)
    
    def test_html_parser(self) -> Tuple[int, str, Optional[Tuple]]:
        """Test HtmlParser class"""
        parser = HtmlParser()
        
        html = "<html><head><title>Test</title></head><body><a href='http://example.com'>Link</a></body></html>"
        
        success, result, error = parser.parse(html)
        if success and 'links' in result:
            self._record_result("HtmlParser parse", True, f"Found {len(result['links'])} links")
        else:
            self._record_result("HtmlParser parse", False, str(error))
        
        success, text, error = parser.extract_text(html)
        if success:
            self._record_result("HtmlParser extract_text", True)
        else:
            self._record_result("HtmlParser extract_text", False, str(error))
        
        return (1, "HtmlParser tests complete", None)
    
    def test_xml_parser(self) -> Tuple[int, str, Optional[Tuple]]:
        """Test XmlParser class"""
        parser = XmlParser()
        
        xml = "<root><item id='1'>Test</item><item id='2'>Test2</item></root>"
        
        success, result, error = parser.parse(xml)
        if success and 'elements' in result:
            self._record_result("XmlParser parse", True, f"Found {len(result['elements'])} elements")
        else:
            self._record_result("XmlParser parse", False, str(error))
        
        success, elements, error = parser.extract_elements(xml, 'item')
        if success:
            self._record_result("XmlParser extract_elements", True, f"Found {len(elements)} items")
        else:
            self._record_result("XmlParser extract_elements", False, str(error))
        
        return (1, "XmlParser tests complete", None)
    
    def test_json_parser(self) -> Tuple[int, str, Optional[Tuple]]:
        """Test JsonParser class"""
        parser = JsonParser()
        
        json_str = '{"name": "test", "value": 123, "nested": {"key": "val"}}'
        
        success, result, error = parser.parse(json_str)
        if success and isinstance(result, dict):
            self._record_result("JsonParser parse", True)
        else:
            self._record_result("JsonParser parse", False, str(error))
        
        success, value, error = parser.extract_value(json_str, 'nested.key')
        if success and value == 'val':
            self._record_result("JsonParser extract_value", True)
        else:
            self._record_result("JsonParser extract_value", False, str(error))
        
        return (1, "JsonParser tests complete", None)
    
    def test_http_client(self) -> Tuple[int, str, Optional[Tuple]]:
        """Test HttpClient class"""
        client = HttpClient()
        
        success, content, error = client.get("https://example.com")
        if success and content:
            self._record_result("HttpClient get", True, f"Fetched {len(content)} chars")
        else:
            self._record_result("HttpClient get", False, str(error))
        
        success, result, error = client.set_header("User-Agent", "TestAgent")
        if success:
            self._record_result("HttpClient set_header", True)
        else:
            self._record_result("HttpClient set_header", False, str(error))
        
        return (1, "HttpClient tests complete", None)
    
    def test_request_builder(self) -> Tuple[int, str, Optional[Tuple]]:
        """Test HttpRequestBuilder class"""
        builder = HttpRequestBuilder()
        
        success, result, error = builder.set_url("https://example.com")
        if success:
            self._record_result("RequestBuilder set_url", True)
        else:
            self._record_result("RequestBuilder set_url", False, str(error))
        
        success, result, error = builder.set_method("POST")
        if success:
            self._record_result("RequestBuilder set_method", True)
        else:
            self._record_result("RequestBuilder set_method", False, str(error))
        
        success, result, error = builder.add_header("Content-Type", "application/json")
        if success:
            self._record_result("RequestBuilder add_header", True)
        else:
            self._record_result("RequestBuilder add_header", False, str(error))
        
        success, req, error = builder.build()
        if success:
            self._record_result("RequestBuilder build", True)
        else:
            self._record_result("RequestBuilder build", False, str(error))
        
        return (1, "RequestBuilder tests complete", None)
    
    def test_link_extractor(self) -> Tuple[int, str, Optional[Tuple]]:
        """Test LinkExtractor class"""
        extractor = LinkExtractor()
        
        html = "<html><body><a href='http://example.com/page1'>Link1</a><a href='/page2'>Link2</a></body></html>"
        
        success, result, error = extractor.extract(html, "https://example.com")
        if success and 'internal' in result:
            self._record_result("LinkExtractor extract", True, f"Found {len(result['internal'])} internal links")
        else:
            self._record_result("LinkExtractor extract", False, str(error))
        
        return (1, "LinkExtractor tests complete", None)
    
    def test_config(self) -> Tuple[int, str, Optional[Tuple]]:
        """Test Config_Web class"""
        config = Config()
        
        success, value, error = config.get("DEFAULT_TIMEOUT")
        if success and value == 30:
            self._record_result("Config get", True)
        else:
            self._record_result("Config get", False, str(error))
        
        success, result, error = config.set("DEFAULT_TIMEOUT", 60)
        if success:
            self._record_result("Config set", True)
        else:
            self._record_result("Config set", False, str(error))
        
        success, value, error = config.get("DEFAULT_TIMEOUT")
        if success and value == 60:
            self._record_result("Config verify set", True)
        else:
            self._record_result("Config verify set", False, str(error))
        
        success, all_config, error = config.get_all()
        if success and isinstance(all_config, dict):
            self._record_result("Config get_all", True, f"Found {len(all_config)} config keys")
        else:
            self._record_result("Config get_all", False, str(error))
        
        return (1, "Config tests complete", None)
    
    def test_orchestrator(self) -> Tuple[int, str, Optional[Tuple]]:
        """Test WebScraping orchestrator class"""
        orchestrator = WebScraping()
        
        success, state, error = orchestrator.Run("read_state")
        if success and 'meta' in state:
            self._record_result("WebScraping read_state", True, "State returned")
        else:
            self._record_result("WebScraping read_state", False, str(error))
        
        success, result, error = orchestrator.Run("parse_html", {'html': '<html><body><a href="http://example.com">Link</a></body></html>'})
        if success and 'links' in result:
            self._record_result("WebScraping parse_html", True, f"Found {len(result['links'])} links")
        else:
            self._record_result("WebScraping parse_html", False, str(error))
        
        success, result, error = orchestrator.Run("parse_json", {'json': '{"key": "value"}'})
        if success and isinstance(result, dict):
            self._record_result("WebScraping parse_json", True)
        else:
            self._record_result("WebScraping parse_json", False, str(error))
        
        success, result, error = orchestrator.Run("config_get", {'key': 'DEFAULT_TIMEOUT'})
        if success:
            self._record_result("WebScraping config_get", True)
        else:
            self._record_result("WebScraping config_get", False, str(error))
        
        success, result, error = orchestrator.Run("unknown_command")
        if not success and error:
            self._record_result("WebScraping unknown_command handled", True)
        else:
            self._record_result("WebScraping unknown_command handled", False, "Should have failed")
        
        return (1, "WebScraping orchestrator tests complete", None)
    
    def test_all(self) -> Tuple[int, str, Optional[Tuple]]:
        """Run all tests"""
        self.test_scraper()
        self.test_html_parser()
        self.test_xml_parser()
        self.test_json_parser()
        self.test_http_client()
        self.test_request_builder()
        self.test_link_extractor()
        self.test_config()
        self.test_orchestrator()
        
        summary = f"Tests passed: {self.state['passed']}, Tests failed: {self.state['failed']}"
        
        for result in self.state['results']:
            status = "PASS" if result['passed'] else "FAIL"
            print(f"{status}: {result['test']} - {result['message']}")
        
        print(summary)
        
        return (1, summary, None)
    
    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        """Dispatch test commands"""
        if params is None:
            params = {}
        
        if command == "test_all":
            return self.test_all()
        
        elif command == "test_scraper":
            return self.test_scraper()
        
        elif command == "test_parser":
            self.test_html_parser()
            self.test_xml_parser()
            self.test_json_parser()
            return (1, "Parser tests complete", None)
        
        elif command == "test_http":
            self.test_http_client()
            self.test_request_builder()
            return (1, "HTTP tests complete", None)
        
        elif command == "test_config":
            return self.test_config()
        
        else:
            return (0, None, (1, f"Unknown command: {command}", 0))


if __name__ == "__main__":
    tester = TestDomWeb()
    success, result, error = tester.Run("test_all")
    if success:
        print(result)
    else:
        print(f"Error: {error}")
