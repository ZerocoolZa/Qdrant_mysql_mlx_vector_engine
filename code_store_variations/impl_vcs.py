"""VBStyle domain implementation: vcs.

Version control: commits, branches, merges, diffs, tags, blame.
All methods return Tuple3 (ok, data, error). Python stdlib only.
"""

import time
import uuid
import hashlib
import re
from collections import deque


class DomVcs:
    """VCS domain: commit, branch, merge, diff, rebase, tag, blame, log, checkout, stash, status, revert."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "repo": {
                "head": "main",
                "branches": {"main": []},
                "tags": {},
                "stash": deque(),
                "index": {},
                "working": {},
                "commits": {},
            },
        }
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "commit": self.commit,
            "branch": self.branch,
            "merge": self.merge,
            "diff": self.diff,
            "rebase": self.rebase,
            "tag": self.tag,
            "blame": self.blame,
            "log": self.log,
            "checkout": self.checkout,
            "stash": self.stash,
            "status": self.status,
            "revert": self.revert,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _new_commit(self, message, files, parent=None):
        sha = hashlib.sha1(f"{message}{time.time()}{uuid.uuid4()}".encode()).hexdigest()[:40]
        commit = {
            "sha": sha,
            "message": message,
            "files": dict(files),
            "parent": parent,
            "timestamp": time.time(),
        }
        self.state["repo"]["commits"][sha] = commit
        return commit

    def commit(self, params=None):
        params = params or {}
        try:
            message = params.get("message", "")
            files = params.get("files") or self.state["repo"]["index"]
            if not files:
                return (0, None, ("NOTHING_TO_COMMIT", "No staged files", 0))
            head = self.state["repo"]["head"]
            parent = self.state["repo"]["branches"][head][-1] if self.state["repo"]["branches"][head] else None
            commit = self._new_commit(message, files, parent)
            self.state["repo"]["branches"][head].append(commit["sha"])
            self.state["repo"]["index"] = {}
            result = {
                "domain": "vcs",
                "method": "commit",
                "data": {"sha": commit["sha"], "message": message, "parent": parent},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMMIT_ERROR", str(e), 0))

    def branch(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            action = params.get("action", "create")
            if action == "create":
                if not name:
                    return (0, None, ("BRANCH_NAME_REQUIRED", "name required", 0))
                if name in self.state["repo"]["branches"]:
                    return (0, None, ("BRANCH_EXISTS", f"Branch {name} exists", 0))
                head = self.state["repo"]["head"]
                self.state["repo"]["branches"][name] = list(self.state["repo"]["branches"][head])
                result = {"domain": "vcs", "method": "branch", "data": {"action": "create", "branch": name}}
                return (1, result, None)
            if action == "list":
                result = {"domain": "vcs", "method": "branch", "data": {"branches": list(self.state["repo"]["branches"].keys())}}
                return (1, result, None)
            if action == "delete":
                if name in self.state["repo"]["branches"] and name != self.state["repo"]["head"]:
                    del self.state["repo"]["branches"][name]
                result = {"domain": "vcs", "method": "branch", "data": {"action": "delete", "branch": name}}
                return (1, result, None)
            return (0, None, ("UNKNOWN_ACTION", f"Unknown action: {action}", 0))
        except Exception as e:
            return (0, None, ("BRANCH_ERROR", str(e), 0))

    def merge(self, params=None):
        params = params or {}
        try:
            source = params.get("source")
            if not source or source not in self.state["repo"]["branches"]:
                return (0, None, ("INVALID_BRANCH", f"Branch {source} not found", 0))
            head = self.state["repo"]["head"]
            target_commits = self.state["repo"]["branches"][head]
            source_commits = self.state["repo"]["branches"][source]
            merged = list(target_commits)
            for sha in source_commits:
                if sha not in merged:
                    merged.append(sha)
            self.state["repo"]["branches"][head] = merged
            result = {
                "domain": "vcs",
                "method": "merge",
                "data": {"source": source, "target": head, "merged_count": len(merged)},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MERGE_ERROR", str(e), 0))

    def diff(self, params=None):
        params = params or {}
        try:
            a = params.get("a", {})
            b = params.get("b", {})
            changes = {}
            all_keys = set(a.keys()) | set(b.keys())
            for key in all_keys:
                if a.get(key) != b.get(key):
                    changes[key] = {"old": a.get(key), "new": b.get(key)}
            result = {
                "domain": "vcs",
                "method": "diff",
                "data": {"changes": changes, "count": len(changes)},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DIFF_ERROR", str(e), 0))

    def rebase(self, params=None):
        params = params or {}
        try:
            source = params.get("source")
            target = params.get("target", self.state["repo"]["head"])
            if not source or source not in self.state["repo"]["branches"]:
                return (0, None, ("INVALID_BRANCH", f"Branch {source} not found", 0))
            target_commits = self.state["repo"]["branches"][target]
            source_commits = self.state["repo"]["branches"][source]
            rebased = list(target_commits)
            for sha in source_commits:
                if sha not in rebased:
                    rebased.append(sha)
            self.state["repo"]["branches"][source] = rebased
            result = {
                "domain": "vcs",
                "method": "rebase",
                "data": {"source": source, "target": target, "count": len(rebased)},
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REBASE_ERROR", str(e), 0))

    def tag(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("TAG_NAME_REQUIRED", "name required", 0))
            sha = params.get("sha")
            if not sha:
                head = self.state["repo"]["head"]
                commits = self.state["repo"]["branches"][head]
                sha = commits[-1] if commits else None
            self.state["repo"]["tags"][name] = {"sha": sha, "message": params.get("message", ""), "timestamp": time.time()}
            result = {"domain": "vcs", "method": "tag", "data": {"name": name, "sha": sha}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TAG_ERROR", str(e), 0))

    def blame(self, params=None):
        params = params or {}
        try:
            file = params.get("file")
            lines = params.get("lines") or []
            if not file:
                return (0, None, ("FILE_REQUIRED", "file required", 0))
            blame = []
            for i, line in enumerate(lines):
                head = self.state["repo"]["head"]
                commits = self.state["repo"]["branches"][head]
                sha = commits[-1] if commits else "unknown"
                blame.append({"line": i + 1, "content": line, "sha": sha})
            result = {"domain": "vcs", "method": "blame", "data": {"file": file, "blame": blame}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("BLAME_ERROR", str(e), 0))

    def log(self, params=None):
        params = params or {}
        try:
            limit = int(params.get("limit", 10))
            head = self.state["repo"]["head"]
            commits = self.state["repo"]["branches"][head]
            entries = []
            for sha in reversed(commits[-limit:]):
                commit = self.state["repo"]["commits"].get(sha, {})
                entries.append({
                    "sha": sha,
                    "message": commit.get("message", ""),
                    "timestamp": commit.get("timestamp"),
                })
            result = {"domain": "vcs", "method": "log", "data": {"entries": entries, "count": len(entries)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LOG_ERROR", str(e), 0))

    def checkout(self, params=None):
        params = params or {}
        try:
            name = params.get("name")
            if not name:
                return (0, None, ("BRANCH_REQUIRED", "name required", 0))
            if name not in self.state["repo"]["branches"]:
                return (0, None, ("BRANCH_NOT_FOUND", f"Branch {name} not found", 0))
            self.state["repo"]["head"] = name
            result = {"domain": "vcs", "method": "checkout", "data": {"head": name}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CHECKOUT_ERROR", str(e), 0))

    def stash(self, params=None):
        params = params or {}
        try:
            action = params.get("action", "push")
            if action == "push":
                entry = {"files": dict(self.state["repo"]["index"]), "timestamp": time.time()}
                self.state["repo"]["stash"].append(entry)
                self.state["repo"]["index"] = {}
                result = {"domain": "vcs", "method": "stash", "data": {"action": "push", "stashed": len(self.state["repo"]["stash"])}}
                return (1, result, None)
            if action == "pop":
                if not self.state["repo"]["stash"]:
                    return (0, None, ("STASH_EMPTY", "No stash entries", 0))
                entry = self.state["repo"]["stash"].pop()
                self.state["repo"]["index"] = entry.get("files", {})
                result = {"domain": "vcs", "method": "stash", "data": {"action": "pop", "remaining": len(self.state["repo"]["stash"])}}
                return (1, result, None)
            if action == "list":
                result = {"domain": "vcs", "method": "stash", "data": {"action": "list", "entries": len(self.state["repo"]["stash"])}}
                return (1, result, None)
            return (0, None, ("UNKNOWN_ACTION", f"Unknown action: {action}", 0))
        except Exception as e:
            return (0, None, ("STASH_ERROR", str(e), 0))

    def status(self, params=None):
        params = params or {}
        try:
            head = self.state["repo"]["head"]
            staged = list(self.state["repo"]["index"].keys())
            result = {
                "domain": "vcs",
                "method": "status",
                "data": {
                    "head": head,
                    "staged": staged,
                    "staged_count": len(staged),
                    "stash_count": len(self.state["repo"]["stash"]),
                    "branches": list(self.state["repo"]["branches"].keys()),
                },
            }
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STATUS_ERROR", str(e), 0))

    def revert(self, params=None):
        params = params or {}
        try:
            sha = params.get("sha")
            if not sha or sha not in self.state["repo"]["commits"]:
                return (0, None, ("COMMIT_NOT_FOUND", f"Commit {sha} not found", 0))
            head = self.state["repo"]["head"]
            commits = self.state["repo"]["branches"][head]
            if sha in commits:
                commits.remove(sha)
            revert_sha = hashlib.sha1(f"revert{sha}{time.time()}".encode()).hexdigest()[:40]
            self.state["repo"]["commits"][revert_sha] = {
                "sha": revert_sha,
                "message": f"Revert {sha}",
                "parent": sha,
                "timestamp": time.time(),
                "files": {},
            }
            commits.append(revert_sha)
            result = {"domain": "vcs", "method": "revert", "data": {"reverted": sha, "revert_sha": revert_sha}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REVERT_ERROR", str(e), 0))
