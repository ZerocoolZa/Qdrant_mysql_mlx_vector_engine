import os
import signal
import subprocess
import time


class DomProcess:
    """Process lifecycle management: spawn, signal, monitor, wait."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        if command in ("Run",):
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        handler = getattr(self, command, None)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _proc(self, params):
        pid = params.get("pid")
        if pid is None and params.get("handle"):
            handle = params["handle"]
            if isinstance(handle, dict) and "pid" in handle:
                pid = handle["pid"]
        if pid is None and self.state.get("last_pid") is not None:
            pid = self.state.get("last_pid")
        return pid

    def kill(self, params=None):
        params = params or {}
        try:
            pid = self._proc(params)
            if pid is None:
                return (0, None, ("KILL_ERROR", "missing pid", 0))
            os.kill(pid, signal.SIGKILL)
            result = {"domain": "process", "method": "kill", "data": {"pid": pid, "signal": "SIGKILL"}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("KILL_ERROR", str(e), 0))

    def monitor(self, params=None):
        params = params or {}
        try:
            pid = self._proc(params)
            if pid is None:
                return (0, None, ("MONITOR_ERROR", "missing pid", 0))
            interval = params.get("interval", 0.1)
            duration = params.get("duration", 1.0)
            samples = []
            start = time.time()
            while time.time() - start < duration:
                try:
                    os.kill(pid, 0)
                    samples.append({"alive": True, "t": round(time.time() - start, 3)})
                except OSError:
                    samples.append({"alive": False, "t": round(time.time() - start, 3)})
                    break
                time.sleep(interval)
            result = {"domain": "process", "method": "monitor", "data": {"pid": pid, "samples": samples, "alive": samples[-1]["alive"] if samples else False}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("MONITOR_ERROR", str(e), 0))

    def pid(self, params=None):
        params = params or {}
        try:
            handle = params.get("handle")
            if handle is None:
                pid = os.getpid()
                result = {"domain": "process", "method": "pid", "data": {"pid": pid}}
                return (1, result, None)
            if isinstance(handle, dict) and "pid" in handle:
                result = {"domain": "process", "method": "pid", "data": {"pid": handle["pid"]}}
                return (1, result, None)
            if isinstance(handle, subprocess.Popen):
                result = {"domain": "process", "method": "pid", "data": {"pid": handle.pid}}
                self.state["last_pid"] = handle.pid
                return (1, result, None)
            result = {"domain": "process", "method": "pid", "data": {"pid": None}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PID_ERROR", str(e), 0))

    def restart(self, params=None):
        params = params or {}
        try:
            pid = self._proc(params)
            if pid is not None:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
            cmd = params.get("cmd") or params.get("command")
            if not cmd:
                return (0, None, ("RESTART_ERROR", "missing cmd", 0))
            if isinstance(cmd, str):
                cmd = cmd.split()
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            self.state["last_pid"] = proc.pid
            result = {"domain": "process", "method": "restart", "data": {"old_pid": pid, "new_pid": proc.pid}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("RESTART_ERROR", str(e), 0))

    def signal(self, params=None):
        params = params or {}
        try:
            pid = self._proc(params)
            if pid is None:
                return (0, None, ("SIGNAL_ERROR", "missing pid", 0))
            sig = params.get("signal", signal.SIGTERM)
            if isinstance(sig, str):
                sig = getattr(signal, "SIG" + sig.upper(), signal.SIGTERM)
            os.kill(pid, sig)
            result = {"domain": "process", "method": "signal", "data": {"pid": pid, "signal": int(sig)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("SIGNAL_ERROR", str(e), 0))

    def status(self, params=None):
        params = params or {}
        try:
            pid = self._proc(params)
            if pid is None:
                result = {"domain": "process", "method": "status", "data": {"alive": False, "pid": None}}
                return (1, result, None)
            alive = True
            try:
                os.kill(pid, 0)
            except OSError:
                alive = False
            result = {"domain": "process", "method": "status", "data": {"pid": pid, "alive": alive}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("STATUS_ERROR", str(e), 0))

    def stderr(self, params=None):
        params = params or {}
        try:
            handle = params.get("handle")
            if handle is None:
                return (0, None, ("STDERR_ERROR", "missing handle", 0))
            if isinstance(handle, subprocess.Popen):
                data = handle.stderr.read() if handle.stderr else b""
                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="replace")
                result = {"domain": "process", "method": "stderr", "data": {"stderr": data, "size": len(data)}}
                return (1, result, None)
            return (0, None, ("STDERR_ERROR", "handle not Popen", 0))
        except Exception as e:
            return (0, None, ("STDERR_ERROR", str(e), 0))

    def stdin(self, params=None):
        params = params or {}
        try:
            handle = params.get("handle")
            data = params.get("data", "")
            if handle is None:
                return (0, None, ("STDIN_ERROR", "missing handle", 0))
            if isinstance(handle, subprocess.Popen):
                if handle.stdin:
                    if isinstance(data, str):
                        data = data.encode("utf-8")
                    handle.stdin.write(data)
                    handle.stdin.flush()
                result = {"domain": "process", "method": "stdin", "data": {"written": len(data)}}
                return (1, result, None)
            return (0, None, ("STDIN_ERROR", "handle not Popen", 0))
        except Exception as e:
            return (0, None, ("STDIN_ERROR", str(e), 0))

    def stdout(self, params=None):
        params = params or {}
        try:
            handle = params.get("handle")
            if handle is None:
                return (0, None, ("STDOUT_ERROR", "missing handle", 0))
            if isinstance(handle, subprocess.Popen):
                data = handle.stdout.read() if handle.stdout else b""
                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="replace")
                result = {"domain": "process", "method": "stdout", "data": {"stdout": data, "size": len(data)}}
                return (1, result, None)
            return (0, None, ("STDOUT_ERROR", "handle not Popen", 0))
        except Exception as e:
            return (0, None, ("STDOUT_ERROR", str(e), 0))

    def timeout(self, params=None):
        params = params or {}
        try:
            cmd = params.get("cmd") or params.get("command")
            if not cmd:
                return (0, None, ("TIMEOUT_ERROR", "missing cmd", 0))
            secs = params.get("timeout", 5)
            if isinstance(cmd, str):
                cmd = cmd.split()
            try:
                proc = subprocess.run(cmd, capture_output=True, timeout=secs)
                rc = proc.returncode
                out = proc.stdout.decode("utf-8", errors="replace") if proc.stdout else ""
                err = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
                timed_out = False
            except subprocess.TimeoutExpired as te:
                rc = -1
                out = (te.stdout or b"").decode("utf-8", errors="replace") if te.stdout else ""
                err = (te.stderr or b"").decode("utf-8", errors="replace") if te.stderr else ""
                timed_out = True
            result = {"domain": "process", "method": "timeout", "data": {"returncode": rc, "stdout": out, "stderr": err, "timed_out": timed_out}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("TIMEOUT_ERROR", str(e), 0))

    def wait(self, params=None):
        params = params or {}
        try:
            handle = params.get("handle")
            if handle is None:
                return (0, None, ("WAIT_ERROR", "missing handle", 0))
            if isinstance(handle, subprocess.Popen):
                rc = handle.wait(timeout=params.get("timeout"))
                result = {"domain": "process", "method": "wait", "data": {"returncode": rc}}
                return (1, result, None)
            return (0, None, ("WAIT_ERROR", "handle not Popen", 0))
        except Exception as e:
            return (0, None, ("WAIT_ERROR", str(e), 0))
