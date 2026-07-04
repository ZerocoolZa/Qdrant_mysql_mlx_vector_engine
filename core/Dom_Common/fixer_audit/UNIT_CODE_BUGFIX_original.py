class UNIT_CODE_BUGFIX:

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.rep = self.param.get("rep") or self._Rep()
        self.state = {"Runs": 0, "Workers": 0, "Strategies": 0, "Best Score": 0, "Winner": "", "Fixed": 0}

    def _ok(self, value):
        return (1, value, ())

    def _fail(self, code, message, detail=None):
        return (0, None, ((str(code), str(message), detail),))

    class _Rep:
        def Ok(self, payload):
            return (1, payload, ())
        def Fail(self, code, message):
            return (0, None, ((str(code), str(message)),))

    def Rdstat(self):
        return self._ok(dict(self.state))

    def Run(self, code):
        original = str(code)
        strategies = self._Strats()
        workers = self._Workers(len(strategies))
        self.state["Workers"] = workers
        self.state["Strategies"] = len(strategies)
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = []
            for strat in strategies:
                futures.append(pool.submit(self._Work, original, strat))
            for fut in as_completed(futures):
                try:
                    ok, value, issues = fut.result()
                    if ok:
                        results.append(value)
                except Exception as exc:
                    results.append({"name": "Failed", "code": original, "score": 0, "fixed": 0})
        if not results:
            return self._fail("NO_CANDIDATES", "No Worker Returned")
        best = self._Best(results)
        self.state["Runs"] += 1
        self.state["Best Score"] = best.get("score", 0)
        self.state["Winner"] = best.get("name", "")
        self.state["Fixed"] = best.get("fixed", 0)
        return self._ok({"Code": best.get("code", original), "Winner": best.get("name", ""), "Score": best.get("score", 0), "Fixed": best.get("fixed", 0)})

    def _Workers(self, count):
        cpu = os.cpu_count() or 2
        limit = cpu * 2
        if count < limit:
            return count if count > 0 else 1
        return limit

    def _Strats(self):
        return [
            {"name": "NullCheck", "mode": "null"},
            {"name": "TypeFix", "mode": "type"},
            {"name": "BoundsCheck", "mode": "bounds"},
            {"name": "ResourceLeak", "mode": "leak"},
            {"name": "Conservative", "mode": "conservative"},
            {"name": "Aggressive", "mode": "aggressive"},
        ]

    def _Work(self, original, strat):
        con = sqlite3.connect(":memory:")
        try:
            self._Schema(con)
            candidate, fixed = self._Apply(original, strat)
            score = self._Score(original, candidate, fixed, strat)
            self._SaveProof(con, strat.get("name", ""), score, fixed)
            return self._ok({"name": strat.get("name", ""), "code": candidate, "score": score, "fixed": fixed})
        finally:
            con.close()

    def _Schema(self, con):
        cur = con.cursor()
        cur.execute("CREATE TABLE ram_code (id INTEGER PRIMARY KEY, text TEXT)")
        cur.execute("CREATE TABLE ram_proof (id INTEGER PRIMARY KEY, strategy TEXT, score INTEGER, fixed INTEGER)")
        con.commit()
        return self._ok(None)

    def _SaveProof(self, con, strategy, score, fixed):
        cur = con.cursor()
        cur.execute("INSERT INTO ram_proof (strategy, score, fixed) VALUES (?, ?, ?)", (strategy, score, fixed))
        con.commit()
        return self._ok(None)

    def _Apply(self, code, strat):
        mode = strat.get("mode", "conservative")
        fixed = 0
        if mode == "null":
            candidate = self._NullCheck(code)
            fixed = candidate.count("if ") - code.count("if ")
        elif mode == "type":
            candidate = self._TypeFix(code)
            fixed = candidate.count("str(") - code.count("str(")
        elif mode == "bounds":
            candidate = self._BoundsCheck(code)
            fixed = candidate.count("len(") - code.count("len(")
        elif mode == "leak":
            candidate = self._ResourceLeak(code)
            fixed = candidate.count("finally") - code.count("finally")
        elif mode == "aggressive":
            candidate = self._AggressiveFix(code)
            fixed = candidate.count("try:") - code.count("try:")
        else:
            candidate = code
        return (candidate, max(0, fixed))

    def _NullCheck(self, code):
        lines = str(code).splitlines()
        return "
".join(lines)

    def _TypeFix(self, code):
        lines = str(code).splitlines()
        return "
".join(lines)

    def _BoundsCheck(self, code):
        lines = str(code).splitlines()
        return "
".join(lines)

    def _ResourceLeak(self, code):
        lines = str(code).splitlines()
        return "
".join(lines)

    def _AggressiveFix(self, code):
        lines = str(code).splitlines()
        return "
".join(lines)

    def _Score(self, original, candidate, fixed, strat):
        score = 100000
        score += fixed * 5000
        if strat.get("mode") == "conservative":
            score += 10000
        return score

    def _Best(self, results):
        ranked = sorted(results, key=lambda row: row.get("score", 0), reverse=True)
        return ranked[0]
