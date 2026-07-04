# [@GHOST]{[@file<backup.py>][@domain<utility>][@role<backup>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<backup>][@return<tuple3>][@orch<Orchestrator>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Backup — zip code, upload to S3, email link via Gmail/Yahoo, git push. Full redundancy.}
# [@WCL]{[@self_contained<true>][@features<zip|s3|email|git>][@redundant<true>][@automated<true>]}

import os
import zipfile
import subprocess
import time
from datetime import datetime

from .credentials import Credentials


class Backup:
    """Backup utility — full redundancy backup of codebase.

    Steps (configurable via Config.BACKUP_STEPS):
    1. ZIP — compress project into timestamped .zip
    2. S3 — upload zip to AWS S3 via boto3
    3. EMAIL — send download link via Gmail or Yahoo Mail
    4. GIT — git commit + push to remote

    Usage:
        from core.utility.backup import Backup
        bk = Backup()
        code, report, err = bk.Run("backup_all", {"project": "/path/to/project"})
        code, report, err = bk.Run("backup_zip", {"project": "/path/to/project"})
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "last_backup": {},
            "history": [],
            "passed": 0,
            "failed": 0,
        }
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state["cred"] = Credentials()

    def Run(self, command, params=None):
        params = params or {}
        if command == "backup_all":
            return self.backup_all(params)
        elif command == "backup_zip":
            return self.backup_zip(params)
        elif command == "backup_s3":
            return self.backup_s3(params)
        elif command == "backup_email":
            return self.backup_email(params)
        elif command == "backup_git":
            return self.backup_git(params)
        elif command == "get_history":
            return self.get_history(params.get("limit", 20))
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self):
        return (1, dict(self.state), None)

    def record(self, step, ok, detail):
        entry = {"step": step, "ok": ok, "detail": detail, "timestamp": time.time()}
        self.state["last_backup"][step] = entry
        if ok:
            self.state["passed"] += 1
        else:
            self.state["failed"] += 1

    def get_project(self, params):
        project = self._p(params, "project")
        if not project:
            from . import Config
            project = Config.PROJECT_ROOT
        return project

    def backup_all(self, params):
        project = self.get_project(params)
        results = {}
        all_ok = True

        zip_ok, zip_path, zip_err = self.do_zip(project, params)
        results["zip"] = {"ok": zip_ok, "path": zip_path, "error": zip_err}
        self.record("zip", zip_ok, zip_path or str(zip_err))
        if not zip_ok:
            all_ok = False

        if zip_ok and zip_path:
            s3_ok, s3_url, s3_err = self.do_s3(zip_path, params)
            results["s3"] = {"ok": s3_ok, "url": s3_url, "error": s3_err}
            self.record("s3", s3_ok, s3_url or str(s3_err))
            if not s3_ok:
                all_ok = False

            email_ok, email_detail, email_err = self.do_email(
                zip_path, s3_url, project, params
            )
            results["email"] = {"ok": email_ok, "detail": email_detail, "error": email_err}
            self.record("email", email_ok, email_detail or str(email_err))
            if not email_ok:
                all_ok = False

        git_ok, git_detail, git_err = self.do_git(project, params)
        results["git"] = {"ok": git_ok, "detail": git_detail, "error": git_err}
        self.record("git", git_ok, git_detail or str(git_err))
        if not git_ok:
            all_ok = False

        self.state["history"].append({
            "timestamp": time.time(),
            "project": project,
            "results": results,
            "all_ok": all_ok,
        })

        summary = self.build_summary(results, all_ok)
        if all_ok:
            return (1, {"results": results, "summary": summary}, None)
        return (0, {"results": results, "summary": summary}, ("BACKUP_PARTIAL", "some steps failed", 0))

    def backup_zip(self, params):
        project = self.get_project(params)
        ok, path, err = self.do_zip(project, params)
        self.record("zip", ok, path or str(err))
        if ok:
            return (1, {"zip_path": path}, None)
        return (0, None, err)

    def backup_s3(self, params):
        zip_path = self._p(params, "zip_path")
        if not zip_path or not os.path.exists(zip_path):
            return (0, None, ("missing_param", "zip_path required", 0))
        ok, url, err = self.do_s3(zip_path, params)
        self.record("s3", ok, url or str(err))
        if ok:
            return (1, {"s3_url": url}, None)
        return (0, None, err)

    def backup_email(self, params):
        zip_path = self._p(params, "zip_path")
        s3_url = self._p(params, "s3_url", "")
        project = self.get_project(params)
        if not zip_path or not os.path.exists(zip_path):
            return (0, None, ("missing_param", "zip_path required", 0))
        ok, detail, err = self.do_email(zip_path, s3_url, project, params)
        self.record("email", ok, detail or str(err))
        if ok:
            return (1, {"email": detail}, None)
        return (0, None, err)

    def backup_git(self, params):
        project = self.get_project(params)
        ok, detail, err = self.do_git(project, params)
        self.record("git", ok, detail or str(err))
        if ok:
            return (1, {"git": detail}, None)
        return (0, None, err)

    def do_zip(self, project, params):
        try:
            if not project or not os.path.isdir(project):
                return (False, None, ("dir_not_found", project or "missing", 0))
            skip_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules",
                         ".tox", ".pytest_cache", ".mypy_cache", "error_log.db",
                         "error_handler.db"}
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_name = os.path.basename(project.rstrip("/"))
            zip_name = "{}_backup_{}.zip".format(project_name, timestamp)
            output_dir = self._p(params, "output_dir", os.path.join(project, ".."))
            zip_path = os.path.join(output_dir, zip_name)

            file_count = 0
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(project):
                    dirs[:] = [d for d in dirs if d not in skip_dirs]
                    for fname in sorted(files):
                        if fname in skip_dirs:
                            continue
                        if fname.endswith((".pyc", ".pyo", ".DS_Store", ".tmp")):
                            continue
                        fpath = os.path.join(root, fname)
                        arcname = os.path.relpath(fpath, project)
                        zf.write(fpath, arcname)
                        file_count += 1

            zip_size = os.path.getsize(zip_path)
            detail = "{} ({} files, {} bytes)".format(zip_path, file_count, zip_size)
            return (True, zip_path, None)
        except Exception as e:
            return (False, None, ("ZIP_ERROR", str(e), 0))

    def do_s3(self, zip_path, params):
        try:
            import boto3
            bucket = self._p(params, "s3_bucket", "")
            if not bucket:
                code, cred, err = self.state["cred"].Run("get", {"provider": "s3"})
                bucket = cred.get("bucket", "") if code else ""
            if not bucket:
                return (False, None, ("missing_param", "s3_bucket required", 0))
            key_prefix = self._p(params, "s3_prefix", "backups/")
            key = key_prefix + os.path.basename(zip_path)

            s3 = boto3.client("s3")
            s3.upload_file(zip_path, bucket, key)
            url = "s3://{}/{}".format(bucket, key)
            return (True, url, None)
        except ImportError:
            return (False, None, ("NO_BOTO3", "boto3 not installed", 0))
        except Exception as e:
            return (False, None, ("S3_ERROR", str(e), 0))

    def do_email(self, zip_path, s3_url, project, params):
        try:
            to_email = self._p(params, "to_email", "")
            if not to_email:
                return (False, None, ("missing_param", "to_email required", 0))
            provider = self._p(params, "email_provider", "gmail")

            project_name = os.path.basename(project.rstrip("/"))
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            zip_size = os.path.getsize(zip_path)
            zip_name = os.path.basename(zip_path)

            subject = "[BACKUP] {} — {}".format(project_name, timestamp)
            body_lines = [
                "Code Backup Report",
                "==================",
                "",
                "Project: {}".format(project_name),
                "Timestamp: {}".format(timestamp),
                "Zip: {} ({} bytes)".format(zip_name, zip_size),
                "",
            ]
            if s3_url:
                body_lines.append("S3 Download: {}".format(s3_url))
            body_lines.append("")
            body_lines.append("This is an automated backup from the Orchestrator utility.")
            body = "\n".join(body_lines)

            if provider == "gmail":
                return self.send_gmail(to_email, subject, body, zip_path)
            elif provider == "yahoo":
                return self.send_yahoo(to_email, subject, body, zip_path)
            else:
                return self.send_smtp(to_email, subject, body, zip_path, params)
        except Exception as e:
            return (False, None, ("EMAIL_ERROR", str(e), 0))

    def send_gmail(self, to_email, subject, body, attachment_path):
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.base import MIMEBase
            from email import encoders

            from_email = os.environ.get("GMAIL_USER", "")
            password = os.environ.get("GMAIL_APP_PASSWORD", "")
            if not from_email or not password:
                code, cred, err = self.state["cred"].Run("get", {"provider": "gmail"})
                from_email = cred.get("user", "") if code else ""
                password = cred.get("password", "") if code else ""
            if not from_email or not password:
                return (False, None, ("GMAIL_CREDENTIALS", "Set gmail credentials via Credentials or env vars", 0))

            msg = MIMEMultipart()
            msg["From"] = from_email
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition",
                                    "attachment; filename={}".format(os.path.basename(attachment_path)))
                    msg.attach(part)

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(from_email, password)
            server.sendmail(from_email, to_email, msg.as_string())
            server.quit()
            return (True, "sent to {} via gmail".format(to_email), None)
        except Exception as e:
            return (False, None, ("GMAIL_ERROR", str(e), 0))

    def send_yahoo(self, to_email, subject, body, attachment_path):
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.base import MIMEBase
            from email import encoders

            from_email = os.environ.get("YAHOO_USER", "")
            password = os.environ.get("YAHOO_APP_PASSWORD", "")
            if not from_email or not password:
                code, cred, err = self.state["cred"].Run("get", {"provider": "yahoo"})
                from_email = cred.get("user", "") if code else ""
                password = cred.get("password", "") if code else ""
            if not from_email or not password:
                return (False, None, ("YAHOO_CREDENTIALS", "Set yahoo credentials via Credentials or env vars", 0))

            msg = MIMEMultipart()
            msg["From"] = from_email
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition",
                                    "attachment; filename={}".format(os.path.basename(attachment_path)))
                    msg.attach(part)

            server = smtplib.SMTP("smtp.mail.yahoo.com", 587)
            server.starttls()
            server.login(from_email, password)
            server.sendmail(from_email, to_email, msg.as_string())
            server.quit()
            return (True, "sent to {} via yahoo".format(to_email), None)
        except Exception as e:
            return (False, None, ("YAHOO_ERROR", str(e), 0))

    def send_smtp(self, to_email, subject, body, attachment_path, params):
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.base import MIMEBase
            from email import encoders

            smtp_host = self._p(params, "smtp_host", "localhost")
            smtp_port = int(self._p(params, "smtp_port", 25))
            from_email = self._p(params, "from_email", "backup@localhost")

            msg = MIMEMultipart()
            msg["From"] = from_email
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition",
                                    "attachment; filename={}".format(os.path.basename(attachment_path)))
                    msg.attach(part)

            server = smtplib.SMTP(smtp_host, smtp_port)
            server.sendmail(from_email, to_email, msg.as_string())
            server.quit()
            return (True, "sent to {} via smtp".format(to_email), None)
        except Exception as e:
            return (False, None, ("SMTP_ERROR", str(e), 0))

    def do_git(self, project, params):
        try:
            if not os.path.isdir(os.path.join(project, ".git")):
                return (False, None, ("NOT_GIT_REPO", "No .git dir in {}".format(project), 0))

            commit_msg = self._p(params, "commit_msg",
                                 "Automated backup {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            remote = self._p(params, "git_remote", "origin")
            branch = self._p(params, "git_branch", "")

            commands = [
                ["git", "add", "-A"],
                ["git", "commit", "-m", commit_msg],
            ]
            if branch:
                commands.append(["git", "push", remote, branch])
            else:
                commands.append(["git", "push", remote])

            outputs = []
            for cmd in commands:
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=project)
                outputs.append({
                    "cmd": " ".join(cmd),
                    "returncode": result.returncode,
                    "stdout": result.stdout.strip()[:200],
                    "stderr": result.stderr.strip()[:200],
                })
                if result.returncode != 0:
                    last_stderr = result.stderr.strip()
                    if "nothing to commit" in last_stderr or "nothing to commit" in result.stdout:
                        outputs[-1]["ok"] = True
                        continue
                    return (False, None, ("GIT_ERROR", last_stderr[:200], 0))

            return (True, "committed + pushed ({})".format(len(outputs)), None)
        except Exception as e:
            return (False, None, ("GIT_ERROR", str(e), 0))

    def build_summary(self, results, all_ok):
        lines = []
        lines.append("=== BACKUP REPORT ===")
        lines.append("Status: {}".format("ALL PASSED" if all_ok else "PARTIAL FAILURE"))
        lines.append("")
        for step, data in results.items():
            tag = "PASS" if data["ok"] else "FAIL"
            detail = data.get("path") or data.get("url") or data.get("detail") or data.get("error", "")
            if isinstance(detail, tuple):
                detail = str(detail)
            lines.append("[{}] {} — {}".format(tag, step, str(detail)[:80]))
        lines.append("")
        lines.append("Steps: {} passed, {} failed".format(
            sum(1 for d in results.values() if d["ok"]),
            sum(1 for d in results.values() if not d["ok"]),
        ))
        return "\n".join(lines)

    def get_history(self, limit=20):
        entries = self.state["history"][-limit:]
        return (1, {"entries": entries, "count": len(entries)}, None)
