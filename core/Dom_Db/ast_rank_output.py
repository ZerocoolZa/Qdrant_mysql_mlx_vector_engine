#!/usr/bin/env python3
#[@GHOST]{[@file<ast_rank_output.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<ast_rank_output>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}

import json
import html
import os
from datetime import datetime


class AstRankOutput:
    """Output formatter for AstRankEngine results.

    Domain: formatting AstRankEngine metrics into JSON, SARIF, HTML,
    Markdown, and CSV output formats. Wraps engine results and produces
    self-contained report strings. All access via Run() dispatch.
    Authority: owns output formatting for AST rank metrics.
    """

    TOOL_NAME = "ast-rank"
    TOOL_VERSION = "2.0.0"
    SARIF_VERSION = "2.1.0"
    SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
    SARIF_INFO_URI = "https://github.com/local/ast-rank"
    DEFAULT_TITLE = "AST Rank Report"
    DEFAULT_TOP_N = 20
    CSV_HEADER = "rank,file_path,complexity_score,cyclomatic_complexity,node_count,max_depth,function_count,class_count,import_count,bcl_tag_count,parse_time,grade"
    GRADE_COLORS = {
        "A": "#28a745",
        "B": "#007bff",
        "C": "#ffc107",
        "D": "#fd7e14",
        "F": "#dc3545",
    }
    SEVERITY_MAP = {
        "critical": "error",
        "warning": "warning",
        "info": "note",
    }
    METRIC_KEYS = (
        "complexity_score",
        "cyclomatic_complexity",
        "node_count",
        "max_depth",
        "function_count",
        "class_count",
        "import_count",
        "bcl_tag_count",
        "parse_time",
    )
    SUPPORTED_SAVE_FORMATS = ("json", "sarif", "html", "markdown", "csv")

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "tool_name": self.TOOL_NAME,
                "tool_version": self.TOOL_VERSION,
                "default_title": self.DEFAULT_TITLE,
                "default_top_n": self.DEFAULT_TOP_N,
            },
            "results": {},
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def read_state(self):
        return {
            "config": dict(self.state["config"]),
            "results_count": len(self.state["results"]),
        }

    def set_config(self, config):
        if config is None:
            return (0, None, ("CFG_NULL", "config is None", 0))
        for key, value in config.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Run(self, command, params=None):
        dispatch = {
            "json": self.Json,
            "sarif": self.Sarif,
            "html": self.Html,
            "markdown": self.Markdown,
            "csv": self.Csv,
            "save": self.Save,
            "read_state": lambda p: (1, self.read_state(), None),
            "set_config": lambda p: self.set_config(p),
            "close": lambda p: self.Close(),
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_CMD", "unknown command: " + str(command), 0))
        return handler(params)

    def Close(self):
        """Close any open resources. Returns Tuple3."""
        return (1, {"closed": True}, None)

    def IsoNow(self):
        return datetime.now().isoformat()

    def ExtractMetric(self, metric, key, default=0):
        value = metric.get(key, default)
        if value is None:
            return default
        return value

    def ComputeSummary(self, metrics):
        total_files = len(metrics)
        if total_files == 0:
            return {
                "total_files": 0,
                "average_complexity": 0,
                "average_maintainability": 0,
                "violations": 0,
            }
        complexity_sum = 0
        maintainability_sum = 0
        violations = 0
        for metric in metrics:
            complexity_sum += self.ExtractMetric(metric, "complexity_score", 0)
            maintainability_sum += self.ExtractMetric(metric, "maintainability_score", 0)
            cyclo = self.ExtractMetric(metric, "cyclomatic_complexity", 0)
            if cyclo > 10:
                violations += 1
        return {
            "total_files": total_files,
            "average_complexity": round(complexity_sum / total_files, 2),
            "average_maintainability": round(maintainability_sum / total_files, 2),
            "violations": violations,
        }

    def BuildFileEntry(self, metric):
        path = metric.get("file", metric.get("path", ""))
        metrics_obj = {}
        for key in self.METRIC_KEYS:
            metrics_obj[key] = self.ExtractMetric(metric, key, 0)
        grade = metric.get("grade", "")
        return {
            "path": path,
            "metrics": metrics_obj,
            "grade": grade,
        }

    def Json(self, params=None):
        metrics = self._p(params, "metrics", [])
        if metrics is None:
            return (0, None, ("METRICS_NULL", "metrics is None", 0))
        summary = self._p(params, "summary")
        if summary is None:
            summary = self.ComputeSummary(metrics)
        files = []
        for metric in metrics:
            files.append(self.BuildFileEntry(metric))
        payload = {
            "tool": self.TOOL_NAME,
            "version": self.TOOL_VERSION,
            "generated_at": self.IsoNow(),
            "summary": summary,
            "files": files,
        }
        json_string = json.dumps(payload, indent=2)
        return (1, json_string, None)

    def Sarif(self, params=None):
        violations = self._p(params, "violations", [])
        if violations is None:
            return (0, None, ("VIOLATIONS_NULL", "violations is None", 0))
        tool_version = self._p(params, "tool_version", self.TOOL_VERSION)
        results = []
        for violation in violations:
            severity = violation.get("severity", "warning")
            level = self.SEVERITY_MAP.get(severity, "warning")
            message_text = violation.get("message", violation.get("description", ""))
            rule_id = violation.get("rule_id", violation.get("ruleId", "ast-rank-rule"))
            location = violation.get("location", {})
            uri = location.get("uri", location.get("file", ""))
            start_line = location.get("startLine", location.get("line", 1))
            results.append({
                "ruleId": rule_id,
                "level": level,
                "message": {"text": message_text},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": uri},
                            "region": {"startLine": start_line},
                        }
                    }
                ],
            })
        payload = {
            "version": self.SARIF_VERSION,
            "$schema": self.SARIF_SCHEMA,
            "runs": [
                {
                    "tool": {
                        "name": self.TOOL_NAME,
                        "version": tool_version,
                        "informationUri": self.SARIF_INFO_URI,
                    },
                    "results": results,
                }
            ],
        }
        sarif_string = json.dumps(payload, indent=2)
        return (1, sarif_string, None)

    def Html(self, params=None):
        metrics = self._p(params, "metrics", [])
        if metrics is None:
            return (0, None, ("METRICS_NULL", "metrics is None", 0))
        title = self._p(params, "title", self.DEFAULT_TITLE)
        summary = self.ComputeSummary(metrics)
        generated = self.IsoNow()
        rows_html = []
        for index, metric in enumerate(metrics):
            path = metric.get("file", metric.get("path", ""))
            escaped_path = html.escape(path)
            complexity = self.ExtractMetric(metric, "complexity_score", 0)
            cyclo = self.ExtractMetric(metric, "cyclomatic_complexity", 0)
            node_count = self.ExtractMetric(metric, "node_count", 0)
            max_depth = self.ExtractMetric(metric, "max_depth", 0)
            function_count = self.ExtractMetric(metric, "function_count", 0)
            class_count = self.ExtractMetric(metric, "class_count", 0)
            import_count = self.ExtractMetric(metric, "import_count", 0)
            bcl_tag_count = self.ExtractMetric(metric, "bcl_tag_count", 0)
            parse_time = self.ExtractMetric(metric, "parse_time", 0)
            grade = metric.get("grade", "")
            grade_color = self.GRADE_COLORS.get(grade, "#6c757d")
            rows_html.append(
                "<tr>"
                "<td>" + str(index + 1) + "</td>"
                "<td>" + escaped_path + "</td>"
                "<td>" + str(complexity) + "</td>"
                "<td>" + str(cyclo) + "</td>"
                "<td>" + str(node_count) + "</td>"
                "<td>" + str(max_depth) + "</td>"
                "<td>" + str(function_count) + "</td>"
                "<td>" + str(class_count) + "</td>"
                "<td>" + str(import_count) + "</td>"
                "<td>" + str(bcl_tag_count) + "</td>"
                "<td>" + str(parse_time) + "</td>"
                "<td><span style=\"color:" + grade_color + ";font-weight:bold;\">" + html.escape(grade) + "</span></td>"
                "</tr>"
            )
        rows_joined = "\n".join(rows_html)
        html_string = (
            "<!DOCTYPE html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "<title>" + html.escape(title) + "</title>\n"
            "<style>\n"
            "body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #333; }\n"
            "h1 { color: #1a1a1a; }\n"
            ".meta { color: #666; font-size: 14px; margin-bottom: 16px; }\n"
            "table { border-collapse: collapse; width: 100%; margin-top: 12px; }\n"
            "th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }\n"
            "th { background: #f5f5f5; cursor: pointer; user-select: none; }\n"
            "th:hover { background: #e9e9e9; }\n"
            "tr:nth-child(even) { background: #fafafa; }\n"
            ".summary { display: flex; gap: 24px; margin: 16px 0; flex-wrap: wrap; }\n"
            ".summary-card { background: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 12px 20px; min-width: 160px; }\n"
            ".summary-card .label { font-size: 12px; color: #666; text-transform: uppercase; }\n"
            ".summary-card .value { font-size: 24px; font-weight: bold; color: #1a1a1a; }\n"
            "</style>\n"
            "</head>\n"
            "<body>\n"
            "<h1>" + html.escape(title) + "</h1>\n"
            "<div class=\"meta\">Generated: " + html.escape(generated) + "</div>\n"
            "<div class=\"summary\">\n"
            "<div class=\"summary-card\"><div class=\"label\">Total Files</div><div class=\"value\">" + str(summary["total_files"]) + "</div></div>\n"
            "<div class=\"summary-card\"><div class=\"label\">Avg Complexity</div><div class=\"value\">" + str(summary["average_complexity"]) + "</div></div>\n"
            "<div class=\"summary-card\"><div class=\"label\">Avg Maintainability</div><div class=\"value\">" + str(summary["average_maintainability"]) + "</div></div>\n"
            "<div class=\"summary-card\"><div class=\"label\">Violations</div><div class=\"value\">" + str(summary["violations"]) + "</div></div>\n"
            "</div>\n"
            "<table id=\"rankTable\">\n"
            "<thead>\n"
            "<tr>\n"
            "<th data-type=\"number\">Rank</th>\n"
            "<th data-type=\"string\">File</th>\n"
            "<th data-type=\"number\">Complexity</th>\n"
            "<th data-type=\"number\">Cyclomatic</th>\n"
            "<th data-type=\"number\">Nodes</th>\n"
            "<th data-type=\"number\">Max Depth</th>\n"
            "<th data-type=\"number\">Functions</th>\n"
            "<th data-type=\"number\">Classes</th>\n"
            "<th data-type=\"number\">Imports</th>\n"
            "<th data-type=\"number\">BCL Tags</th>\n"
            "<th data-type=\"number\">Parse Time</th>\n"
            "<th data-type=\"string\">Grade</th>\n"
            "</tr>\n"
            "</thead>\n"
            "<tbody>\n"
            + rows_joined + "\n"
            "</tbody>\n"
            "</table>\n"
            "<script>\n"
            "document.querySelectorAll('#rankTable th').forEach(function(th, index) {\n"
            "  th.addEventListener('click', function() {\n"
            "    var table = document.getElementById('rankTable');\n"
            "    var tbody = table.querySelector('tbody');\n"
            "    var rows = Array.from(tbody.querySelectorAll('tr'));\n"
            "    var type = th.getAttribute('data-type');\n"
            "    var ascending = th.classList.contains('sort-asc') ? false : true;\n"
            "    document.querySelectorAll('#rankTable th').forEach(function(h) {\n"
            "      h.classList.remove('sort-asc', 'sort-desc');\n"
            "    });\n"
            "    th.classList.add(ascending ? 'sort-asc' : 'sort-desc');\n"
            "    rows.sort(function(a, b) {\n"
            "      var av = a.children[index].textContent.trim();\n"
            "      var bv = b.children[index].textContent.trim();\n"
            "      if (type === 'number') {\n"
            "        av = parseFloat(av);\n"
            "        bv = parseFloat(bv);\n"
            "      }\n"
            "      if (av < bv) return ascending ? -1 : 1;\n"
            "      if (av > bv) return ascending ? 1 : -1;\n"
            "      return 0;\n"
            "    });\n"
            "    rows.forEach(function(row) { tbody.appendChild(row); });\n"
            "  });\n"
            "});\n"
            "</script>\n"
            "</body>\n"
            "</html>"
        )
        return (1, html_string, None)

    def Markdown(self, params=None):
        metrics = self._p(params, "metrics", [])
        if metrics is None:
            return (0, None, ("METRICS_NULL", "metrics is None", 0))
        top_n = self._p(params, "top_n", self.DEFAULT_TOP_N)
        summary = self.ComputeSummary(metrics)
        generated = self.IsoNow()
        sorted_metrics = sorted(
            metrics,
            key=lambda m: self.ExtractMetric(m, "complexity_score", 0),
            reverse=True,
        )
        top_metrics = sorted_metrics[:top_n]
        lines = []
        lines.append("# AST Rank Report")
        lines.append("")
        lines.append("Generated: " + generated)
        lines.append("")
        lines.append("## Summary")
        lines.append("- Total files: " + str(summary["total_files"]))
        lines.append("- Average complexity: " + str(summary["average_complexity"]))
        lines.append("- Violations: " + str(summary["violations"]))
        lines.append("")
        lines.append("## Top " + str(len(top_metrics)) + " Files by Complexity")
        lines.append("")
        lines.append("| Rank | File | Complexity | Cyclomatic | Grade |")
        lines.append("|------|------|-----------|-----------|-------|")
        for index, metric in enumerate(top_metrics):
            path = metric.get("file", metric.get("path", ""))
            complexity = self.ExtractMetric(metric, "complexity_score", 0)
            cyclo = self.ExtractMetric(metric, "cyclomatic_complexity", 0)
            grade = metric.get("grade", "")
            lines.append(
                "| " + str(index + 1) + " | " + str(path) + " | " + str(complexity) + " | " + str(cyclo) + " | " + str(grade) + " |"
            )
        lines.append("")
        md_string = "\n".join(lines)
        return (1, md_string, None)

    def Csv(self, params=None):
        metrics = self._p(params, "metrics", [])
        if metrics is None:
            return (0, None, ("METRICS_NULL", "metrics is None", 0))
        sorted_metrics = sorted(
            metrics,
            key=lambda m: self.ExtractMetric(m, "complexity_score", 0),
            reverse=True,
        )
        lines = [self.CSV_HEADER]
        for index, metric in enumerate(sorted_metrics):
            path = metric.get("file", metric.get("path", ""))
            complexity = self.ExtractMetric(metric, "complexity_score", 0)
            cyclo = self.ExtractMetric(metric, "cyclomatic_complexity", 0)
            node_count = self.ExtractMetric(metric, "node_count", 0)
            max_depth = self.ExtractMetric(metric, "max_depth", 0)
            function_count = self.ExtractMetric(metric, "function_count", 0)
            class_count = self.ExtractMetric(metric, "class_count", 0)
            import_count = self.ExtractMetric(metric, "import_count", 0)
            bcl_tag_count = self.ExtractMetric(metric, "bcl_tag_count", 0)
            parse_time = self.ExtractMetric(metric, "parse_time", 0)
            grade = metric.get("grade", "")
            row = [
                str(index + 1),
                str(path),
                str(complexity),
                str(cyclo),
                str(node_count),
                str(max_depth),
                str(function_count),
                str(class_count),
                str(import_count),
                str(bcl_tag_count),
                str(parse_time),
                str(grade),
            ]
            lines.append(",".join(row))
        csv_string = "\n".join(lines)
        return (1, csv_string, None)

    def Save(self, params=None):
        fmt = self._p(params, "format")
        path = self._p(params, "path")
        data = self._p(params, "data", {})
        if fmt is None:
            return (0, None, ("FMT_NULL", "format is None", 0))
        if path is None:
            return (0, None, ("PATH_NULL", "path is None", 0))
        if fmt not in self.SUPPORTED_SAVE_FORMATS:
            return (0, None, ("FMT_UNSUPPORTED", "unsupported format: " + str(fmt), 0))
        if fmt == "json":
            ok, content, err = self.Json(data)
        elif fmt == "sarif":
            ok, content, err = self.Sarif(data)
        elif fmt == "html":
            ok, content, err = self.Html(data)
        elif fmt == "markdown":
            ok, content, err = self.Markdown(data)
        elif fmt == "csv":
            ok, content, err = self.Csv(data)
        else:
            return (0, None, ("FMT_UNSUPPORTED", "unsupported format: " + str(fmt), 0))
        if not ok:
            return (0, None, err)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError as exc:
            return (0, None, ("WRITE_FAIL", str(exc), 0))
        size_bytes = os.path.getsize(path)
        result = {
            "saved": True,
            "path": path,
            "format": fmt,
            "size_bytes": size_bytes,
        }
        return (1, result, None)
