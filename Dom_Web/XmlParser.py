#!/usr/bin/env python3
"""
#[@GHOST]{[@file<XmlParser.py>][@state<active>][@date<2026-07-03>][@ver<2.0>][@auth<Cascade>]}
#[@VBSTYLE]{[@auth<system>][@role<web_component>][@return<Tuple3>][@orch<WebScraping>][@mem<none>][@db<none>]}
#[@FILEID]{[@path<XmlParser.py>][@hash<placeholder>]}
#[@SUMMARY]{XML parser using ElementTree}
#[@CLASS]{XmlParser}
#[@METHOD]{__init__, parse, extract_elements, extract_attributes, Run}
"""

import xml.etree.ElementTree as ET
from typing import Optional, Tuple, List, Dict, Any


class XmlParser:
    """
    XML parser for extracting structured data from XML content.
    Uses Python's ElementTree for parsing.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            'root': None,
            'elements': [],
            'attributes': {}
        }

    def parse(self, xml_content: str) -> Tuple[int, Dict[str, Any], Optional[Tuple]]:
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
        success, result, error = self.parse(xml_content)
        if not success:
            return (0, [], error)
        if tag:
            elements = [e for e in result['elements'] if e['tag'] == tag]
        else:
            elements = result['elements']
        return (1, elements, None)

    def extract_attributes(self, xml_content: str, tag: str) -> Tuple[int, Dict[str, str], Optional[Tuple]]:
        success, elements, error = self.extract_elements(xml_content, tag)
        if not success:
            return (0, {}, error)
        if elements:
            return (1, elements[0]['attributes'], None)
        return (1, {}, None)

    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        if params is None:
            params = {}
        if command == "parse":
            xml_content = params.get('xml')
            if not xml_content:
                return (0, None, (29, "Missing required param: xml", 0))
            return self.parse(xml_content)
        elif command == "extract_elements":
            xml_content = params.get('xml')
            if not xml_content:
                return (0, None, (30, "Missing required param: xml", 0))
            return self.extract_elements(xml_content, params.get('tag'))
        elif command == "extract_attributes":
            xml_content = params.get('xml')
            tag = params.get('tag')
            if not xml_content or not tag:
                return (0, None, (31, "Missing required params: xml, tag", 0))
            return self.extract_attributes(xml_content, tag)
        else:
            return (0, None, (32, f"Unknown command: {command}", 0))
