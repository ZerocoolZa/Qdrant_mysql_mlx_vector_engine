class DomConvert:
    """Format conversion: CSV, JSON, XML, YAML, TOML, dict, list roundtrips."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "from_csv": self.from_csv,
            "from_json": self.from_json,
            "from_xml": self.from_xml,
            "from_yaml": self.from_yaml,
            "roundtrip": self.roundtrip,
            "to_csv": self.to_csv,
            "to_dict": self.to_dict,
            "to_list": self.to_list,
            "to_toml": self.to_toml,
            "to_xml": self.to_xml,
            "to_yaml": self.to_yaml,
        }
        handler = handlers.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))

    def from_csv(self, params=None):
        params = params or {}
        try:
            import csv, io
            text = params.get("text", "")
            delimiter = params.get("delimiter", ",")
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
            rows = [dict(r) for r in reader]
            result = {"domain": "convert", "method": "from_csv", "data": {"rows": rows, "count": len(rows)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FROM_CSV_ERROR", str(e), 0))

    def from_json(self, params=None):
        params = params or {}
        try:
            import json
            text = params.get("text", "")
            data = json.loads(text)
            result = {"domain": "convert", "method": "from_json", "data": {"data": data}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FROM_JSON_ERROR", str(e), 0))

    def from_xml(self, params=None):
        params = params or {}
        try:
            import xml.etree.ElementTree as ET
            text = params.get("text", "")

            def elem_to_dict(elem):
                d = {}
                for child in elem:
                    cd = elem_to_dict(child)
                    if child.tag in d:
                        if not isinstance(d[child.tag], list):
                            d[child.tag] = [d[child.tag]]
                        d[child.tag].append(cd)
                    else:
                        d[child.tag] = cd
                if elem.attrib:
                    d["@attrib"] = dict(elem.attrib)
                text_val = (elem.text or "").strip()
                if text_val and not d:
                    return text_val
                if text_val:
                    d["#text"] = text_val
                return d

            root = ET.fromstring(text)
            data = {root.tag: elem_to_dict(root)}
            result = {"domain": "convert", "method": "from_xml", "data": {"data": data}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FROM_XML_ERROR", str(e), 0))

    def from_yaml(self, params=None):
        params = params or {}
        try:
            text = params.get("text", "")
            data = {}
            for line in text.splitlines():
                line = line.rstrip()
                if not line or line.lstrip().startswith("#"):
                    continue
                if ":" in line:
                    k, _, v = line.partition(":")
                    v = v.strip()
                    if v == "":
                        data[k.strip()] = {}
                    else:
                        data[k.strip()] = v
            result = {"domain": "convert", "method": "from_yaml", "data": {"data": data}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FROM_YAML_ERROR", str(e), 0))

    def roundtrip(self, params=None):
        params = params or {}
        try:
            import json
            data = params.get("data")
            fmt = params.get("format", "json")
            if fmt == "json":
                encoded = json.dumps(data)
                decoded = json.loads(encoded)
            elif fmt == "csv":
                import csv, io
                if not isinstance(data, list):
                    data = [data]
                out = io.StringIO()
                if data:
                    writer = csv.DictWriter(out, fieldnames=list(data[0].keys()))
                    writer.writeheader()
                    writer.writerows(data)
                encoded = out.getvalue()
                reader = csv.DictReader(io.StringIO(encoded))
                decoded = [dict(r) for r in reader]
            else:
                encoded = str(data)
                decoded = data
            ok = data == decoded
            result = {"domain": "convert", "method": "roundtrip", "data": {"format": fmt, "encoded": encoded, "decoded": decoded, "match": ok}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ROUNDTRIP_ERROR", str(e), 0))

    def to_csv(self, params=None):
        params = params or {}
        try:
            import csv, io
            data = params.get("data", [])
            if not isinstance(data, list):
                data = [data]
            out = io.StringIO()
            if data:
                fieldnames = []
                for row in data:
                    if isinstance(row, dict):
                        for k in row.keys():
                            if k not in fieldnames:
                                fieldnames.append(k)
                writer = csv.DictWriter(out, fieldnames=fieldnames)
                writer.writeheader()
                for row in data:
                    writer.writerow(row)
            result = {"domain": "convert", "method": "to_csv", "data": {"csv": out.getvalue()}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TO_CSV_ERROR", str(e), 0))

    def to_dict(self, params=None):
        params = params or {}
        try:
            data = params.get("data")
            if isinstance(data, dict):
                out = data
            elif isinstance(data, list):
                out = {str(i): v for i, v in enumerate(data)}
            elif isinstance(data, str):
                out = {"value": data}
            else:
                out = {"value": data}
            result = {"domain": "convert", "method": "to_dict", "data": {"dict": out}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TO_DICT_ERROR", str(e), 0))

    def to_list(self, params=None):
        params = params or {}
        try:
            data = params.get("data")
            if isinstance(data, list):
                out = data
            elif isinstance(data, dict):
                out = list(data.items())
            elif isinstance(data, str):
                out = list(data)
            else:
                out = [data]
            result = {"domain": "convert", "method": "to_list", "data": {"list": out}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TO_LIST_ERROR", str(e), 0))

    def to_toml(self, params=None):
        params = params or {}
        try:
            data = params.get("data", {})
            lines = []

            def _emit(prefix, value):
                if isinstance(value, dict):
                    for k, v in value.items():
                        if isinstance(v, dict):
                            section = prefix + "." + k if prefix else k
                            lines.append(f"[{section}]")
                            _emit(section, v)
                        else:
                            lines.append(f"{k} = {_toml_val(v)}")
                else:
                    lines.append(f"{prefix} = {_toml_val(value)}")

            def _toml_val(v):
                if isinstance(v, bool):
                    return "true" if v else "false"
                if isinstance(v, (int, float)):
                    return str(v)
                if isinstance(v, str):
                    return '"' + v.replace('"', '\\"') + '"'
                if isinstance(v, list):
                    return "[" + ", ".join(_toml_val(x) for x in v) + "]"
                return '"' + str(v) + '"'

            _emit("", data)
            result = {"domain": "convert", "method": "to_toml", "data": {"toml": "\n".join(lines)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TO_TOML_ERROR", str(e), 0))

    def to_xml(self, params=None):
        params = params or {}
        try:
            import xml.etree.ElementTree as ET
            data = params.get("data", {})
            root_name = params.get("root", "root")

            def _build(parent, d):
                for k, v in d.items():
                    child = ET.SubElement(parent, k)
                    if isinstance(v, dict):
                        _build(child, v)
                    elif isinstance(v, list):
                        for item in v:
                            item_child = ET.SubElement(child, "item")
                            if isinstance(item, dict):
                                _build(item_child, item)
                            else:
                                item_child.text = str(item)
                    else:
                        child.text = str(v)

            root = ET.Element(root_name)
            if isinstance(data, dict):
                _build(root, data)
            xml_str = ET.tostring(root, encoding="unicode")
            result = {"domain": "convert", "method": "to_xml", "data": {"xml": xml_str}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TO_XML_ERROR", str(e), 0))

    def to_yaml(self, params=None):
        params = params or {}
        try:
            data = params.get("data", {})
            indent = int(params.get("indent", 2))

            def _emit(d, level):
                lines = []
                pad = " " * (level * indent)
                for k, v in d.items():
                    if isinstance(v, dict):
                        lines.append(f"{pad}{k}:")
                        lines.extend(_emit(v, level + 1))
                    elif isinstance(v, list):
                        lines.append(f"{pad}{k}:")
                        for item in v:
                            if isinstance(item, dict):
                                lines.append(f"{pad}- ")
                                lines.extend(_emit(item, level + 1))
                            else:
                                lines.append(f"{pad}- {item}")
                    elif isinstance(v, bool):
                        lines.append(f"{pad}{k}: {'true' if v else 'false'}")
                    elif isinstance(v, (int, float)):
                        lines.append(f"{pad}{k}: {v}")
                    elif v is None:
                        lines.append(f"{pad}{k}: null")
                    else:
                        lines.append(f"{pad}{k}: {v}")
                return lines

            lines = _emit(data, 0) if isinstance(data, dict) else [f"- {data}"]
            result = {"domain": "convert", "method": "to_yaml", "data": {"yaml": "\n".join(lines)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TO_YAML_ERROR", str(e), 0))
