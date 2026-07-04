"""VBStyle domain implementation: analytics.

Provides statistical and analytical operations over numeric datasets.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import statistics
import math
from collections import defaultdict


class DomAnalytics:
    """Analytics domain: aggregation, statistics, clustering, forecasting."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "aggregate": self.aggregate,
            "anomaly": self.anomaly,
            "avg": self.avg,
            "classify": self.classify,
            "cluster": self.cluster,
            "correlate": self.correlate,
            "count": self.count,
            "forecast": self.forecast,
            "group": self.group,
            "insight": self.insight,
            "max": self.max,
            "median": self.median,
            "min": self.min,
            "pivot": self.pivot,
            "stddev": self.stddev,
            "sum": self.sum,
            "trend": self.trend,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    @staticmethod
    def _values(params):
        data = params.get("values") or params.get("data") or []
        return [float(v) for v in data] if data else []

    def aggregate(self, params=None):
        params = params or {}
        try:
            values = self._values(params)
            ops = params.get("ops") or ["sum", "avg", "min", "max", "count"]
            result = {"domain": "analytics", "method": "aggregate", "data": {}}
            for op in ops:
                if op == "sum":
                    result["data"]["sum"] = sum(values)
                elif op == "avg":
                    result["data"]["avg"] = statistics.fmean(values) if values else 0.0
                elif op == "min":
                    result["data"]["min"] = min(values) if values else None
                elif op == "max":
                    result["data"]["max"] = max(values) if values else None
                elif op == "count":
                    result["data"]["count"] = len(values)
                elif op == "median":
                    result["data"]["median"] = statistics.median(values) if values else None
                elif op == "stddev":
                    result["data"]["stddev"] = statistics.pstdev(values) if len(values) > 1 else 0.0
            return (1, result, None)
        except Exception as e:
            return (0, None, ("AGGREGATE_ERROR", str(e), 0))

    def anomaly(self, params=None):
        params = params or {}
        try:
            values = self._values(params)
            threshold = float(params.get("threshold", 2.0))
            anomalies = []
            if len(values) > 1:
                mean = statistics.fmean(values)
                sd = statistics.pstdev(values) or 1.0
                for i, v in enumerate(values):
                    z = abs(v - mean) / sd
                    if z > threshold:
                        anomalies.append({"index": i, "value": v, "zscore": z})
            result = {"domain": "analytics", "method": "anomaly", "data": {"anomalies": anomalies, "count": len(anomalies)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ANOMALY_ERROR", str(e), 0))

    def avg(self, params=None):
        params = params or {}
        try:
            values = self._values(params)
            avg = statistics.fmean(values) if values else 0.0
            result = {"domain": "analytics", "method": "avg", "data": {"avg": avg, "count": len(values)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("AVG_ERROR", str(e), 0))

    def classify(self, params=None):
        params = params or {}
        try:
            values = self._values(params)
            bins = int(params.get("bins", 3))
            if not values or bins < 1:
                result = {"domain": "analytics", "method": "classify", "data": {"buckets": [], "labels": []}}
                return (1, result, None)
            lo, hi = min(values), max(values)
            span = (hi - lo) or 1.0
            width = span / bins
            buckets = [0] * bins
            labels = []
            for i in range(bins):
                labels.append(f"bucket_{i}")
            for v in values:
                idx = min(int((v - lo) / width), bins - 1)
                buckets[idx] += 1
            result = {"domain": "analytics", "method": "classify", "data": {"buckets": buckets, "labels": labels, "range": [lo, hi]}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CLASSIFY_ERROR", str(e), 0))

    def cluster(self, params=None):
        params = params or {}
        try:
            values = self._values(params)
            k = int(params.get("k", 2))
            if not values or k < 1:
                result = {"domain": "analytics", "method": "cluster", "data": {"centroids": [], "assignments": []}}
                return (1, result, None)
            k = min(k, len(values))
            step = len(values) // k
            centroids = [values[i * step] for i in range(k)]
            for _ in range(int(params.get("iters", 10))):
                clusters = [[] for _ in range(k)]
                for v in values:
                    nearest = min(range(k), key=lambda i: abs(centroids[i] - v))
                    clusters[nearest].append(v)
                for i, c in enumerate(clusters):
                    if c:
                        centroids[i] = statistics.fmean(c)
            assignments = []
            for v in values:
                nearest = min(range(k), key=lambda i: abs(centroids[i] - v))
                assignments.append(nearest)
            result = {"domain": "analytics", "method": "cluster", "data": {"centroids": centroids, "assignments": assignments, "k": k}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CLUSTER_ERROR", str(e), 0))

    def correlate(self, params=None):
        params = params or {}
        try:
            xs = [float(x) for x in (params.get("x") or [])]
            ys = [float(y) for y in (params.get("y") or [])]
            n = min(len(xs), len(ys))
            if n < 2:
                result = {"domain": "analytics", "method": "correlate", "data": {"correlation": None, "n": n}}
                return (1, result, None)
            mx, my = statistics.fmean(xs[:n]), statistics.fmean(ys[:n])
            sx = statistics.pstdev(xs[:n]) or 1e-9
            sy = statistics.pstdev(ys[:n]) or 1e-9
            cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / n
            corr = cov / (sx * sy)
            result = {"domain": "analytics", "method": "correlate", "data": {"correlation": corr, "n": n}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CORRELATE_ERROR", str(e), 0))

    def count(self, params=None):
        params = params or {}
        try:
            values = self._values(params)
            result = {"domain": "analytics", "method": "count", "data": {"count": len(values)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COUNT_ERROR", str(e), 0))

    def forecast(self, params=None):
        params = params or {}
        try:
            values = self._values(params)
            horizon = int(params.get("horizon", 3))
            if len(values) < 2:
                result = {"domain": "analytics", "method": "forecast", "data": {"forecast": [], "slope": 0.0}}
                return (1, result, None)
            n = len(values)
            xs = list(range(n))
            mx, my = statistics.fmean(xs), statistics.fmean(values)
            denom = sum((x - mx) ** 2 for x in xs) or 1e-9
            slope = sum((xs[i] - mx) * (values[i] - my) for i in range(n)) / denom
            intercept = my - slope * mx
            forecast = [slope * (n + i) + intercept for i in range(horizon)]
            result = {"domain": "analytics", "method": "forecast", "data": {"forecast": forecast, "slope": slope, "intercept": intercept}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FORECAST_ERROR", str(e), 0))

    def group(self, params=None):
        params = params or {}
        try:
            records = params.get("records") or []
            key = params.get("key") or "key"
            groups = defaultdict(list)
            for r in records:
                k = r.get(key) if isinstance(r, dict) else key
                groups[k].append(r)
            result = {"domain": "analytics", "method": "group", "data": {"groups": dict(groups), "count": len(groups)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("GROUP_ERROR", str(e), 0))

    def insight(self, params=None):
        params = params or {}
        try:
            values = self._values(params)
            insights = {}
            if values:
                insights["mean"] = statistics.fmean(values)
                insights["median"] = statistics.median(values)
                insights["min"] = min(values)
                insights["max"] = max(values)
                insights["range"] = max(values) - min(values)
                insights["stddev"] = statistics.pstdev(values) if len(values) > 1 else 0.0
                insights["count"] = len(values)
                insights["sum"] = sum(values)
            result = {"domain": "analytics", "method": "insight", "data": insights}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INSIGHT_ERROR", str(e), 0))

    def max(self, params=None):
        params = params or {}
        try:
            values = self._values(params)
            mx = max(values) if values else None
            result = {"domain": "analytics", "method": "max", "data": {"max": mx, "count": len(values)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MAX_ERROR", str(e), 0))

    def median(self, params=None):
        params = params or {}
        try:
            values = self._values(params)
            med = statistics.median(values) if values else None
            result = {"domain": "analytics", "method": "median", "data": {"median": med, "count": len(values)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MEDIAN_ERROR", str(e), 0))

    def min(self, params=None):
        params = params or {}
        try:
            values = self._values(params)
            mn = min(values) if values else None
            result = {"domain": "analytics", "method": "min", "data": {"min": mn, "count": len(values)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MIN_ERROR", str(e), 0))

    def pivot(self, params=None):
        params = params or {}
        try:
            records = params.get("records") or []
            row_key = params.get("row_key") or "row"
            col_key = params.get("col_key") or "col"
            val_key = params.get("val_key") or "val"
            pivot = defaultdict(dict)
            for r in records:
                rk = r.get(row_key)
                ck = r.get(col_key)
                pivot[rk][ck] = r.get(val_key)
            result = {"domain": "analytics", "method": "pivot", "data": {"pivot": dict(pivot), "rows": len(pivot)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PIVOT_ERROR", str(e), 0))

    def stddev(self, params=None):
        params = params or {}
        try:
            values = self._values(params)
            sd = statistics.pstdev(values) if len(values) > 1 else 0.0
            result = {"domain": "analytics", "method": "stddev", "data": {"stddev": sd, "count": len(values)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STDDEV_ERROR", str(e), 0))

    def sum(self, params=None):
        params = params or {}
        try:
            values = self._values(params)
            total = sum(values)
            result = {"domain": "analytics", "method": "sum", "data": {"sum": total, "count": len(values)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SUM_ERROR", str(e), 0))

    def trend(self, params=None):
        params = params or {}
        try:
            values = self._values(params)
            if len(values) < 2:
                result = {"domain": "analytics", "method": "trend", "data": {"direction": "flat", "slope": 0.0}}
                return (1, result, None)
            n = len(values)
            xs = list(range(n))
            mx, my = statistics.fmean(xs), statistics.fmean(values)
            denom = sum((x - mx) ** 2 for x in xs) or 1e-9
            slope = sum((xs[i] - mx) * (values[i] - my) for i in range(n)) / denom
            direction = "up" if slope > 0 else ("down" if slope < 0 else "flat")
            result = {"domain": "analytics", "method": "trend", "data": {"direction": direction, "slope": slope}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TREND_ERROR", str(e), 0))
