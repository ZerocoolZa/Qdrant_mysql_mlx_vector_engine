import math


class DomCompass:
    """Compass domain: navigation, orientation, and spatial mapping operations."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db
        if param:
            if isinstance(param, dict):
                self.state["config"].update(param.get("config", {}))
                self.state["catalog"] = list(param.get("catalog", []))
            elif isinstance(param, list):
                self.state["catalog"] = list(param)

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "benchmark": self.benchmark,
            "calibrate": self.calibrate,
            "distance": self.distance,
            "explore": self.explore,
            "heading": self.heading,
            "landmark": self.landmark,
            "map": self.map,
            "navigate": self.navigate,
            "orient": self.orient,
            "report": self.report,
            "route": self.route,
            "survey": self.survey,
            "waypoint": self.waypoint,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def benchmark(self, params=None):
        params = params or {}
        try:
            point = params.get("point", {})
            catalog = self.state.get("catalog", [])
            if not catalog:
                result = {"domain": "compass", "method": "benchmark", "data": {"benchmark": None, "index": -1}}
                return (1, result, None)
            px = float(point.get("x", 0))
            py = float(point.get("y", 0))
            best_i = -1
            best_d = None
            for i, item in enumerate(catalog):
                ix = float(item.get("x", 0)) if isinstance(item, dict) else 0.0
                iy = float(item.get("y", 0)) if isinstance(item, dict) else 0.0
                d = math.sqrt((px - ix) ** 2 + (py - iy) ** 2)
                if best_d is None or d < best_d:
                    best_d = d
                    best_i = i
            result = {"domain": "compass", "method": "benchmark", "data": {"benchmark": catalog[best_i] if best_i >= 0 else None, "index": best_i, "distance": best_d}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BENCHMARK_ERROR", str(e), 0))

    def calibrate(self, params=None):
        params = params or {}
        try:
            offset = float(params.get("offset", 0.0))
            self.state["config"]["calibration_offset"] = offset
            result = {"domain": "compass", "method": "calibrate", "data": {"offset": offset, "calibrated": True}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CALIBRATE_ERROR", str(e), 0))

    def distance(self, params=None):
        params = params or {}
        try:
            a = params.get("a", {})
            b = params.get("b", {})
            ax = float(a.get("x", 0))
            ay = float(a.get("y", 0))
            bx = float(b.get("x", 0))
            by = float(b.get("y", 0))
            d = math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)
            result = {"domain": "compass", "method": "distance", "data": {"distance": d}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DISTANCE_ERROR", str(e), 0))

    def explore(self, params=None):
        params = params or {}
        try:
            origin = params.get("origin", {"x": 0, "y": 0})
            radius = float(params.get("radius", 10.0))
            catalog = self.state.get("catalog", [])
            ox = float(origin.get("x", 0))
            oy = float(origin.get("y", 0))
            found = []
            for item in catalog:
                ix = float(item.get("x", 0)) if isinstance(item, dict) else 0.0
                iy = float(item.get("y", 0)) if isinstance(item, dict) else 0.0
                d = math.sqrt((ox - ix) ** 2 + (oy - iy) ** 2)
                if d <= radius:
                    found.append({"item": item, "distance": d})
            found.sort(key=lambda x: x["distance"])
            result = {"domain": "compass", "method": "explore", "data": {"found": found, "count": len(found)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXPLORE_ERROR", str(e), 0))

    def heading(self, params=None):
        params = params or {}
        try:
            a = params.get("a", {})
            b = params.get("b", {})
            ax = float(a.get("x", 0))
            ay = float(a.get("y", 0))
            bx = float(b.get("x", 0))
            by = float(b.get("y", 0))
            angle = math.degrees(math.atan2(by - ay, bx - ax))
            if angle < 0:
                angle += 360.0
            result = {"domain": "compass", "method": "heading", "data": {"heading": angle, "radians": math.radians(angle)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("HEADING_ERROR", str(e), 0))

    def landmark(self, params=None):
        params = params or {}
        try:
            name = str(params.get("name", ""))
            point = params.get("point", {"x": 0, "y": 0})
            landmark = {"name": name, "x": float(point.get("x", 0)), "y": float(point.get("y", 0))}
            self.state["catalog"].append(landmark)
            result = {"domain": "compass", "method": "landmark", "data": {"landmark": landmark, "total": len(self.state["catalog"])}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LANDMARK_ERROR", str(e), 0))

    def map(self, params=None):
        params = params or {}
        try:
            catalog = self.state.get("catalog", [])
            bounds = params.get("bounds", {})
            min_x = float(bounds.get("min_x", -float("inf")))
            max_x = float(bounds.get("max_x", float("inf")))
            min_y = float(bounds.get("min_y", -float("inf")))
            max_y = float(bounds.get("max_y", float("inf")))
            mapped = []
            for item in catalog:
                ix = float(item.get("x", 0)) if isinstance(item, dict) else 0.0
                iy = float(item.get("y", 0)) if isinstance(item, dict) else 0.0
                if min_x <= ix <= max_x and min_y <= iy <= max_y:
                    mapped.append(item)
            result = {"domain": "compass", "method": "map", "data": {"map": mapped, "count": len(mapped)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MAP_ERROR", str(e), 0))

    def navigate(self, params=None):
        params = params or {}
        try:
            start = params.get("start", {"x": 0, "y": 0})
            end = params.get("end", {"x": 0, "y": 0})
            sx = float(start.get("x", 0))
            sy = float(start.get("y", 0))
            ex = float(end.get("x", 0))
            ey = float(end.get("y", 0))
            steps = []
            n = int(params.get("steps", 5))
            if n <= 0:
                n = 5
            for i in range(1, n + 1):
                t = i / n
                steps.append({"x": sx + (ex - sx) * t, "y": sy + (ey - sy) * t, "step": i})
            result = {"domain": "compass", "method": "navigate", "data": {"steps": steps, "count": len(steps)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("NAVIGATE_ERROR", str(e), 0))

    def orient(self, params=None):
        params = params or {}
        try:
            point = params.get("point", {"x": 0, "y": 0})
            ref = params.get("reference", {"x": 0, "y": 0})
            px = float(point.get("x", 0))
            py = float(point.get("y", 0))
            rx = float(ref.get("x", 0))
            ry = float(ref.get("y", 0))
            dx = px - rx
            dy = py - ry
            angle = math.degrees(math.atan2(dy, dx))
            if angle < 0:
                angle += 360.0
            dist = math.sqrt(dx * dx + dy * dy)
            result = {"domain": "compass", "method": "orient", "data": {"angle": angle, "distance": dist}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ORIENT_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            catalog = self.state.get("catalog", [])
            config = self.state.get("config", {})
            result = {"domain": "compass", "method": "report", "data": {"landmarks": len(catalog), "config": config, "catalog": list(catalog)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))

    def route(self, params=None):
        params = params or {}
        try:
            waypoints = params.get("waypoints", [])
            if len(waypoints) < 2:
                result = {"domain": "compass", "method": "route", "data": {"segments": [], "total_distance": 0.0}}
                return (1, result, None)
            segments = []
            total = 0.0
            for i in range(len(waypoints) - 1):
                a = waypoints[i]
                b = waypoints[i + 1]
                ax = float(a.get("x", 0))
                ay = float(a.get("y", 0))
                bx = float(b.get("x", 0))
                by = float(b.get("y", 0))
                d = math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)
                total += d
                segments.append({"from": a, "to": b, "distance": d})
            result = {"domain": "compass", "method": "route", "data": {"segments": segments, "total_distance": total}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ROUTE_ERROR", str(e), 0))

    def survey(self, params=None):
        params = params or {}
        try:
            catalog = self.state.get("catalog", [])
            if not catalog:
                result = {"domain": "compass", "method": "survey", "data": {"area": 0.0, "count": 0, "centroid": None}}
                return (1, result, None)
            xs = [float(item.get("x", 0)) if isinstance(item, dict) else 0.0 for item in catalog]
            ys = [float(item.get("y", 0)) if isinstance(item, dict) else 0.0 for item in catalog]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            area = (max_x - min_x) * (max_y - min_y)
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)
            result = {"domain": "compass", "method": "survey", "data": {"area": area, "count": len(catalog), "centroid": {"x": cx, "y": cy}, "bounds": {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y}}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SURVEY_ERROR", str(e), 0))

    def waypoint(self, params=None):
        params = params or {}
        try:
            point = params.get("point", {"x": 0, "y": 0})
            name = str(params.get("name", f"wp_{len(self.state['catalog'])}"))
            wp = {"name": name, "x": float(point.get("x", 0)), "y": float(point.get("y", 0))}
            self.state["catalog"].append(wp)
            result = {"domain": "compass", "method": "waypoint", "data": {"waypoint": wp, "total": len(self.state["catalog"])}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("WAYPOINT_ERROR", str(e), 0))
