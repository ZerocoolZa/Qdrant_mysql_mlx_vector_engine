class BrkAI:
    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.rep = self.param.get("rep") or Rep()
        self.cfg = self.param.get("cfg")
        self.conv = self.param.get("conv")
        self.aud = self.param.get("aud")
        self.io = self.param.get("io")
        self.state = {
            "Runs": 0,
            "Workers": 0,
            "Strategies": 0,
            "Best Score": 0,
            "Remaining": 0,
            "Winner": "",
            "Learned": 0,
        }
        self.learn_tag = "#[@BRKLS]"

    def Rdstat(self):
        return (1, dict(self.state), ())

    def Run(self, text):
        original = str(text)
        strategies = self.Strats()
        workers = self.Workers(len(strategies))
        self.state["Workers"] = workers
        self.state["Strategies"] = len(strategies)
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = []
            for strat in strategies:
                futures.append(pool.submit(self.Work, original, strat))
            for fut in as_completed(futures):
                try:
                    ok, value, issues = fut.result()
                    if ok:
                        results.append(value)
                    else:
                        results.append({
                            "name": "Failed",
                            "text": original,
                            "bad": [{"Line": 0, "Kind": "Worker Failed", "Text": repr(issues)}],
                            "score": 0,
                            "learn": [],
                            "stats": {},
                        })
                except Exception as exc:
                    results.append({
                        "name": "Future Failed",
                        "text": original,
                        "bad": [{"Line": 0, "Kind": "Future Failed", "Text": str(exc)}],
                        "score": 0,
                        "learn": [],
                        "stats": {},
                    })
        if not results:
            return self.rep.Fail("No Candidates", "No Worker Returned")
        best = self.Best(results)
        self.Wrlearn(best.get("learn", []))
        self.state["Runs"] += 1
        self.state["Best Score"] = best.get("score", 0)
        self.state["Remaining"] = len(best.get("bad", []))
        self.state["Winner"] = best.get("name", "")
        self.state["Learned"] = len(best.get("learn", []))
        return self.rep.Ok({
            "Text": best.get("text", original),
            "Bad": best.get("bad", []),
            "Winner": best.get("name", ""),
            "Score": best.get("score", 0),
            "Candidates": self.Short(results),
            "Learned": best.get("learn", []),
        })

    def Workers(self, count):
        cpu = os.cpu_count() or 2
        limit = cpu * 2
        if count < limit:
            return count if count > 0 else 1
        return limit

    def Strats(self):
        return [
            {"name": "ConvOnly", "mode": "conv"},
            {"name": "FixTokenFirst", "mode": "tok"},
            {"name": "FixShapeFirst", "mode": "shape"},
            {"name": "FixValidThenShape", "mode": "validshape"},
            {"name": "Aggressive", "mode": "all"},
            {"name": "NoComment", "mode": "nocomment"},
        ]

    def Work(self, original, strat):
        con = sqlite3.connect(":memory:")
        try:
            self.Schema(con)
            self.Put(con, "original", original)
            current = original
            learn = []
            attempt = 0
            while attempt < self.cfg.max_pass:
                attempt += 1
                current = self.Apply(current, strat, attempt)
                ok, bad, issues = self.aud.Run(current)
                if not ok:
                    bad = [{"Line": 0, "Kind": "Audit Failed", "Text": repr(issues)}]
                self.SaveTry(con, strat.get("name", ""), attempt, current, bad)
                if not bad:
                    score = self.Score(original, current, bad, attempt, strat)
                    self.SaveProof(con, strat.get("name", ""), attempt, score, "Pass")
                    return self.rep.Ok({
                        "name": strat.get("name", ""),
                        "text": current,
                        "bad": [],
                        "score": score,
                        "learn": learn,
                        "stats": self.Dbstat(con),
                    })
                repaired, rows = self.Repair(current, bad, strat)
                learn.extend(rows)
                if repaired == current:
                    break
                current = repaired
            ok, bad, issues = self.aud.Run(current)
            if not ok:
                bad = [{"Line": 0, "Kind": "Audit Failed", "Text": repr(issues)}]
            score = self.Score(original, current, bad, attempt, strat)
            self.SaveProof(con, strat.get("name", ""), attempt, score, "Fail" if bad else "Pass")
            return self.rep.Ok({
                "name": strat.get("name", ""),
                "text": current,
                "bad": bad,
                "score": score,
                "learn": learn,
                "stats": self.Dbstat(con),
            })
        finally:
            con.close()

    def Schema(self, con):
        cur = con.cursor()
        cur.execute("CREATE TABLE ram_text (key TEXT PRIMARY KEY, val TEXT)")
        cur.execute("CREATE TABLE ram_try (id INTEGER PRIMARY KEY, strategy TEXT, attempt INTEGER, bad INTEGER, text TEXT)")
        cur.execute("CREATE TABLE ram_proof (id INTEGER PRIMARY KEY, strategy TEXT, attempt INTEGER, score INTEGER, status TEXT)")
        cur.execute("CREATE TABLE ram_learn (id INTEGER PRIMARY KEY, kind TEXT, old TEXT, new TEXT)")
        con.commit()
        return (1, None, ())

    def Put(self, con, key, val):
        cur = con.cursor()
        cur.execute("INSERT OR REPLACE INTO ram_text (key, val) VALUES (?, ?)", (key, val))
        con.commit()
        return (1, None, ())

    def SaveTry(self, con, strategy, attempt, text, bad):
        cur = con.cursor()
        cur.execute(
            "INSERT INTO ram_try (strategy, attempt, bad, text) VALUES (?, ?, ?, ?)",
            (strategy, attempt, len(bad), text),
        )
        con.commit()
        return (1, None, ())

    def SaveProof(self, con, strategy, attempt, score, status):
        cur = con.cursor()
        cur.execute(
            "INSERT INTO ram_proof (strategy, attempt, score, status) VALUES (?, ?, ?, ?)",
            (strategy, attempt, score, status),
        )
        con.commit()
        return (1, None, ())

    def Dbstat(self, con):
        cur = con.cursor()
        out = {}
        for name in ["ram_text", "ram_try", "ram_proof", "ram_learn"]:
            cur.execute("SELECT COUNT(*) FROM " + name)
            out[name] = cur.fetchone()[0]
        return out

    def Apply(self, text, strat, attempt):
        mode = strat.get("mode", "conv")
        if mode == "nocomment":
            old = self.conv.convert_comments
            self.conv.convert_comments = 0
            ok, value, issues = self.conv.Run(text)
            self.conv.convert_comments = old
            candidate = value if ok else text
            candidate = self.FixBadTokenLine(candidate)
            return candidate
        if mode == "tok":
            return self.FixTokens(text)
        if mode == "shape":
            candidate = self.FixShapes(text)
            candidate = self.FixBadTokenLine(candidate)
            return candidate
        if mode == "validshape":
            fixed = self.FixValid(text)
            candidate = self.FixShapes(fixed)
            candidate = self.FixBadTokenLine(candidate)
            return candidate
        if mode == "all":
            fixed = self.FixTokens(text)
            fixed = self.FixValid(fixed)
            fixed = self.FixShapes(fixed)
            ok, value, issues = self.conv.Run(fixed)
            candidate = value if ok else fixed
            candidate = self.FixBadTokenLine(candidate)
            return candidate
        ok, value, issues = self.conv.Run(text)
        candidate = value if ok else text
        candidate = self.FixBadTokenLine(candidate)
        return candidate

    def Repair(self, text, bad_rows, strat):
        lines = str(text).splitlines()
        changed = 0
        learned = []
        seen = set()
        for row in bad_rows:
            line_no = int(row.get("Line", 0))
            if line_no <= 0 or line_no > len(lines):
                continue
            if line_no in seen:
                continue
            seen.add(line_no)
            old = lines[line_no - 1]
            new = self.FixLine(old, row.get("Kind", ""), strat)
            if new != old:
                lines[line_no - 1] = new
                changed += 1
                learned.append(self.Learnrow(row.get("Kind", ""), old, new))
        if not changed:
            return (text, learned)
        final = "
".join(lines)
        if str(text).endswith("
"):
            final += "
"
        return (final, learned)

    def FixLine(self, line, kind, strat):
        text = str(line)
        if kind in {"Angle Field", "Curly Packet", "Unquoted Detail"}:
            return self.conv.Line(text)
        if kind in {"Token Underscore", "Token Too Long", "Lower Token"}:
            return self.FixTokenLine(text)
        if strat.get("mode") == "all":
            text = self.FixTokenLine(text)
            text = self.FixValid(text)
            text = self.FixShapes(text)
            return self.conv.Line(text)
        return self.conv.Line(text)

    def FixTokens(self, text):
        lines = []
        for line in str(text).splitlines():
            lines.append(self.FixTokenLine(line))
        return "
".join(lines) + ("
" if str(text).endswith("
") else "")

    def FixTokenLine(self, line):
        text = str(line)
        text = re.sub(r"\[@([A-Za-z0-9]*_[A-Za-z0-9_]*)\]", self.FixTok, text)
        text = re.sub(r"\[@([A-Za-z0-9]{6,})\]", self.FixTok, text)
        text = re.sub(r"\[@([a-z][A-Za-z0-9]*)\]", self.FixTok, text)
        return text

    def FixBadTokenLine(self, line):
        text = str(line)
        text = re.sub(r"\[@([A-Za-z0-9]*_[A-Za-z0-9_]*)\]", self.FixTok, text)
        text = re.sub(r"\[@([A-Za-z0-9]{6,})\]", self.FixTok, text)
        text = re.sub(r"\[@([a-z][A-Za-z0-9]*)\]", self.FixTok, text)
        return text

    def FixTok(self, match):
        return "[@" + self.conv.Tok(match.group(1)) + "]"

    def FixShapes(self, text):
        ok, value, issues = self.conv.Run(text)
        return value if ok else text

    def FixValid(self, text):
        lines = []
        for line in str(text).splitlines():
            line = re.sub(r"\[@([A-Za-z0-9_\-]+)\]\(([^()]*)\)", self.FixValidOne, line)
            lines.append(line)
        return "
".join(lines) + ("
" if str(text).endswith("
") else "")

    def FixValidOne(self, match):
        token = match.group(1)
        content = match.group(2)
        return self.conv.ValidFix(token, content)

    def Score(self, original, candidate, bad, attempt, strat):
        changed = self.Changed(original, candidate)
        score = 100000
        for row in bad:
            if row.get("Kind") in {"Token Too Long", "Token Underscore", "Lower Token"}:
                score -= 100000
        score -= len(bad) * 1000
        score -= changed * 5
        score -= attempt * 10
        if strat.get("mode") == "nocomment":
            score += 50
        if len(bad) == 0:
            score += 50000
        return score

    def Changed(self, left, right):
        a = str(left).splitlines()
        b = str(right).splitlines()
        total = abs(len(a) - len(b))
        for idx in range(min(len(a), len(b))):
            if a[idx] != b[idx]:
                total += 1
        return total

    def Best(self, results):
        ranked = sorted(results, key=lambda row: (row.get("score", 0), -len(row.get("bad", []))), reverse=True)
        return ranked[0]

    def Short(self, results):
        out = []
        for row in sorted(results, key=lambda item: item.get("score", 0), reverse=True):
            out.append({
                "Name": row.get("name", ""),
                "Score": row.get("score", 0),
                "Bad": len(row.get("bad", [])),
                "Stats": row.get("stats", {}),
            })
        return out

    def Learnrow(self, kind, old, new):
        return {
            "Kind": str(kind),
            "Old": self.Cut(old),
            "New": self.Cut(new),
        }

    def Cut(self, value):
        text = str(value).replace('"', "'").replace("
", " ").strip()
        return text[:220]

    def Wrlearn(self, rows):
        if not rows:
            return self.rep.Ok({"Learned": 0})
        try:
            path = Path(__file__)
            old = path.read_text(encoding="utf-8", errors="replace")
            existing = set()
            for line in old.splitlines():
                if line.startswith(self.learn_tag):
                    existing.add(line.strip())
            add = []
            for row in rows:
                line = (
                    self.learn_tag
                    + "(\"Kind " + self.Cut(row.get("Kind", ""))
                    + "\";\"Old " + self.Cut(row.get("Old", ""))
                    + "\";\"New " + self.Cut(row.get("New", ""))
                    + "\")"
                )
                if line not in existing:
                    add.append(line)
                    existing.add(line)
            if not add:
                return self.rep.Ok({"Learned": 0})
            path.write_text(old.rstrip() + "

" + "
".join(add) + "
", encoding="utf-8")
            return self.rep.Ok({"Learned": len(add)})
        except Exception as exc:
            return self.rep.Fail("Learn Write Failed", str(exc))
