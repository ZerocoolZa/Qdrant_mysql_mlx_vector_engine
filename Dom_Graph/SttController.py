#!/usr/bin/env python3
# [@GHOST]{[@file<SttController.py>][@domain<voice>][@role<stt>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<stt>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{SttController — STT via SFSpeechRecognizer with persistent recognizer, queue-based callbacks, mute flag. Uses AudioEngineManager + SilenceDetector. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{SttController}
# [@METHOD]{Run,listen,stop_listening,is_listening,mute,unmute,warmup,set_language,set_on_device,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<STT via SFSpeechRecognizer with persistent recognizer, queue-based callbacks, mute flag. VBStyle: Run dispatch, Tuple3, self.state. Multiple classes in file (SttWorker QThread + SttController). Uses pyqtSignal.>][@todos<Consider splitting SttWorker into separate file per one-class-one-file rule.>]}
"""
SttController — Speech-to-Text control via SFSpeechRecognizer.

WHAT IT MANAGES:
  - SFSpeechRecognizer persistent instance (no cold start)
  - Recognition request + task lifecycle
  - Queue-based callbacks (fire on QThread, not main)
  - Mute flag for feedback loop prevention (<10ms transition)
  - Authorization caching (no 5s polling every call)
  - On-device recognition with graceful fallback

DEPENDS ON:
  - AudioEngineManager — for AVAudioEngine lifecycle
  - SilenceDetector — for audio-level silence detection

WHY CLASS-BASED:
  - Persistent recognizer — no 200-700ms cold start
  - Mute instead of stop — <10ms TTS/STT transition
  - Dynamic language/on-device changes at runtime
  - Centralized STT state — know if listening, muted, what language

USAGE:
  from SttController import SttController
  from AudioEngineManager import AudioEngineManager
  from SilenceDetector import SilenceDetector

  aem = AudioEngineManager()
  sd = SilenceDetector()
  stt = SttController(param={"audio_engine": aem, "silence_detector": sd})

  ok, data, err = stt.Run("warmup")
  ok, data, err = stt.Run("listen", {"on_partial": handler1, "on_finished": handler2})
  ok, data, err = stt.Run("mute")    # during TTS
  ok, data, err = stt.Run("unmute")  # after TTS
  ok, data, err = stt.Run("stop_listening")
"""

import time
import threading
from PyQt6.QtCore import QThread, pyqtSignal


class SttWorker(QThread):
    """Internal QThread worker — runs STT in background."""
    partial = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, controller, config):
        super().__init__()
        self.controller = controller
        self.config = config
        self.running = True
        self.muted = False
        self.finalResult = None
        self.lastError = None
        self.lastPartial = ""
        self.lastPartialTime = 0
        self.lock = threading.Lock()
        self.request = None
        self.task = None

    def run(self):
        try:
            result = self.listenPyobjc()
            if result is not None:
                self.finished.emit(result)
                return
            if self.lastError:
                self.error.emit(self.lastError)
            else:
                self.error.emit("Speech recognition not available")
        except Exception as e:
            self.error.emit(str(e))

    def listenPyobjc(self):
        try:
            from Speech import SFSpeechAudioBufferRecognitionRequest
            from Foundation import NSRunLoop, NSDate

            with self.lock:
                self.finalResult = None
                self.lastError = None
                self.lastPartial = ""
                self.lastPartialTime = 0
                self.muted = False

            # Ensure recognizer + authorization
            if not self.controller.ensureRecognizer():
                return None

            recognizer = self.controller.state["recognizer"]
            aem = self.controller.state["audio_engine"]
            sd = self.controller.state["silence_detector"]

            # Reset silence detector
            sd.Run("reset")

            # Create recognition request
            request = SFSpeechAudioBufferRecognitionRequest.alloc().init()
            request.setShouldReportPartialResults_(True)
            on_device = self.config.get("stt_on_device", True)
            if on_device:
                try:
                    if recognizer.supportsOnDeviceRecognition():
                        request.setRequiresOnDeviceRecognition_(True)
                    else:
                        on_device = False
                except Exception:
                    pass
            self.request = request

            # Install audio tap via AudioEngineManager
            bufferSize = self.config.get("stt_buffer_size", 4096)
            ok, data, err = aem.Run("install_tap", {
                "buffer_size": bufferSize,
                "callback": lambda buffer, when: self.onAudioBuffer(buffer, request),
            })
            if not ok:
                self.lastError = err[1] if err else "tap install failed"
                return None

            # Start engine
            ok, data, err = aem.Run("start")
            if not ok:
                self.lastError = err[1] if err else "engine start failed"
                aem.Run("remove_tap")
                return None

            # Start recognition task
            self.task = recognizer.recognitionTaskWithRequest_resultHandler_(
                request, self.handler
            )

            # Pump runloop with dual silence detection
            loop = NSRunLoop.currentRunLoop()
            start = time.time()
            maxTimeout = self.config.get("stt_max_timeout", 60)
            minListen = self.config.get("stt_min_listen", 1.0)
            silenceTimeout = self.config.get("stt_silence_timeout", 2.5)
            runloopInterval = self.config.get("stt_runloop_interval", 0.05)

            while self.running and time.time() - start < maxTimeout:
                with self.lock:
                    if self.finalResult:
                        break
                    now = time.time()
                    elapsed = now - start
                    if elapsed > minListen and self.lastPartial:
                        textSilence = now - self.lastPartialTime
                        if textSilence > silenceTimeout:
                            self.finalResult = self.lastPartial
                            break
                # Audio-level silence via SilenceDetector
                if elapsed > minListen:
                    ok, sdata, serr = sd.Run("is_silent")
                    if ok and sdata and sdata.get("silent"):
                        with self.lock:
                            if self.lastPartial:
                                self.finalResult = self.lastPartial
                        break
                loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(runloopInterval))

            # Cleanup — pause engine (keep warm), remove tap, cancel task
            aem.Run("remove_tap")
            aem.Run("pause")
            if self.task:
                self.task.cancel()
            request.endAudio()

            with self.lock:
                return self.finalResult or self.lastPartial or ""
        except ImportError:
            return self.listenFallback()
        except Exception as e:
            self.lastError = str(e)
            return self.listenFallback()

    def onAudioBuffer(self, buffer, request):
        if self.muted:
            return
        try:
            request.appendAudioPCMBuffer_(buffer)
            sd = self.controller.state["silence_detector"]
            sd.Run("measure", {"buffer": buffer})
        except Exception:
            pass

    def handler(self, result, error):
        with self.lock:
            if error:
                self.lastError = str(error)
                return
            if result:
                text = result.bestTranscription().formattedString()
                if text != self.lastPartial:
                    self.lastPartial = text
                    self.lastPartialTime = time.time()
                self.partial.emit(text)
                if result.isFinal():
                    self.finalResult = text

    def listenFallback(self):
        try:
            import subprocess
            subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to keystroke "d" using {command down}'],
                capture_output=True, text=True, timeout=10
            )
            return None
        except Exception:
            return None

    def stop(self):
        self.running = False

    def mute(self):
        with self.lock:
            self.muted = True

    def unmute(self):
        with self.lock:
            self.muted = False
            self.lastPartial = ""
            self.lastPartialTime = time.time()


class SttController:
    """
    STT controller — SFSpeechRecognizer with persistent recognizer.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    Uses AudioEngineManager + SilenceDetector.
    """

    sharedRecognizer = None
    authChecked = False
    authStatus = -1
    resourceLock = threading.Lock()

    def __init__(self, mem=None, db=None, param=None):
        self.lock = threading.Lock()
        self.state = {
            "config": {
                "stt_language": param.get("stt_language", "en-US") if param else "en-US",
                "stt_on_device": param.get("stt_on_device", True) if param else True,
                "stt_buffer_size": param.get("stt_buffer_size", 4096) if param else 4096,
                "stt_silence_timeout": param.get("stt_silence_timeout", 2.5) if param else 2.5,
                "stt_min_listen": param.get("stt_min_listen", 1.0) if param else 1.0,
                "stt_max_timeout": param.get("stt_max_timeout", 60) if param else 60,
                "stt_runloop_interval": param.get("stt_runloop_interval", 0.05) if param else 0.05,
                "stt_silence_threshold": param.get("stt_silence_threshold", 0.01) if param else 0.01,
            },
            "audio_engine": param.get("audio_engine") if param else None,
            "silence_detector": param.get("silence_detector") if param else None,
            "recognizer": None,
            "worker": None,
            "listening": False,
            "muted": False,
            "warmed_up": False,
            "callbacks": None,
            "stats": {"listen_count": 0, "mute_count": 0, "unmute_count": 0, "errors": 0},
        }

    def Run(self, command, params=None):
        dispatch = {
            "listen": self.cmd_listen,
            "stop_listening": self.cmd_stop_listening,
            "is_listening": self.cmd_is_listening,
            "mute": self.cmd_mute,
            "unmute": self.cmd_unmute,
            "warmup": self.cmd_warmup,
            "set_language": self.cmd_set_language,
            "set_on_device": self.cmd_set_on_device,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown: %s" % command, 0))
        return handler(params or {})

    def read_state(self, params=None):
        with self.lock:
            return (1, dict(self.state), None)

    def set_config(self, params):
        with self.lock:
            for key, val in params.items():
                if key in self.state["config"]:
                    self.state["config"][key] = val
            return (1, dict(self.state["config"]), None)

    def p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    # ════════════════════════════════════════════
    # INTERNAL — ensure recognizer + authorization
    # ════════════════════════════════════════════

    def ensureRecognizer(self):
        try:
            from Speech import SFSpeechRecognizer
            from Foundation import NSLocale, NSRunLoop, NSDate
        except ImportError:
            self.state["stats"]["errors"] += 1
            return False

        with SttController.resourceLock:
            # Authorization — only poll if not determined
            if not SttController.authChecked:
                loop = NSRunLoop.currentRunLoop()
                authStatus = int(SFSpeechRecognizer.authorizationStatus())
                if authStatus == 0:
                    SFSpeechRecognizer.requestAuthorization_(None)
                    for _ in range(50):
                        loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
                        authStatus = int(SFSpeechRecognizer.authorizationStatus())
                        if authStatus != 0:
                            break
                SttController.authStatus = authStatus
                SttController.authChecked = True

            if SttController.authStatus != 3:
                self.state["stats"]["errors"] += 1
                return False

            # Persistent recognizer
            if SttController.sharedRecognizer is None:
                lang = self.state["config"]["stt_language"]
                if lang and lang != "en-US":
                    locale = NSLocale.localeWithLocaleIdentifier_(lang)
                    SttController.sharedRecognizer = SFSpeechRecognizer.alloc().initWithLocale_(locale)
                else:
                    SttController.sharedRecognizer = SFSpeechRecognizer.alloc().init()

                if SttController.sharedRecognizer is None:
                    self.state["stats"]["errors"] += 1
                    return False

                # Set queue to current thread — callbacks fire on QThread
                try:
                    from Foundation import NSOperationQueue
                    queue = NSOperationQueue.alloc().init()
                    queue.setMaxConcurrentOperationCount_(1)
                    SttController.sharedRecognizer.setQueue_(queue)
                except Exception:
                    pass

            recognizer = SttController.sharedRecognizer
            if not recognizer.isAvailable():
                self.state["stats"]["errors"] += 1
                return False

            self.state["recognizer"] = recognizer
            return True

    # ════════════════════════════════════════════
    # COMMANDS
    # ════════════════════════════════════════════

    def cmd_warmup(self, params):
        if self.state["warmed_up"]:
            return (1, {"warmed_up": True, "note": "already warmed"}, None)
        # Warm up recognizer + audio engine in background
        def warmupBg():
            self.ensureRecognizer()
            if self.state["audio_engine"]:
                self.state["audio_engine"].Run("start")
        t = threading.Thread(target=warmupBg, daemon=True)
        t.start()
        with self.lock:
            self.state["warmed_up"] = True
        return (1, {"warmed_up": True}, None)

    def cmd_listen(self, params):
        onPartial = self.p(params, "on_partial")
        onFinished = self.p(params, "on_finished")
        onError = self.p(params, "on_error")
        with self.lock:
            self.state["callbacks"] = {
                "on_partial": onPartial,
                "on_finished": onFinished,
                "on_error": onError,
            }

        # If worker already running, just unmute
        if self.state["worker"] and self.state["worker"].isRunning():
            return self.cmd_unmute({})

        # Create worker
        worker = SttWorker(self, dict(self.state["config"]))
        if onPartial:
            worker.partial.connect(onPartial)
        if onFinished:
            worker.finished.connect(onFinished)
        if onError:
            worker.error.connect(onError)
        with self.lock:
            self.state["worker"] = worker
            self.state["listening"] = True
            self.state["stats"]["listen_count"] += 1
        worker.start()
        return (1, {"listening": True}, None)

    def cmd_stop_listening(self, params):
        with self.lock:
            self.state["listening"] = False
            self.state["muted"] = False
            self.state["callbacks"] = None
            worker = self.state["worker"]
        if worker:
            worker.stop()
        return (1, {"listening": False}, None)

    def cmd_is_listening(self, params):
        with self.lock:
            worker = self.state["worker"]
            listening = worker is not None and worker.isRunning() and not self.state["muted"]
            self.state["listening"] = listening
            return (1, {"listening": listening, "muted": self.state["muted"]}, None)

    def cmd_mute(self, params):
        with self.lock:
            worker = self.state["worker"]
            self.state["muted"] = True
            self.state["stats"]["mute_count"] += 1
        if worker and worker.isRunning():
            worker.mute()
        return (1, {"muted": True}, None)

    def cmd_unmute(self, params):
        with self.lock:
            worker = self.state["worker"]
            self.state["muted"] = False
            self.state["stats"]["unmute_count"] += 1
        if worker and worker.isRunning():
            worker.unmute()
            return (1, {"muted": False, "resumed": True}, None)
        # Worker not running — restart if callbacks exist
        callbacks = self.state["callbacks"]
        if callbacks:
            return self.cmd_listen(callbacks)
        return (1, {"muted": False, "resumed": False}, None)

    def cmd_set_language(self, params):
        lang = self.p(params, "language")
        if not lang:
            return (0, None, ("ERR_PARAMS", "language required", 0))
        with self.lock:
            self.state["config"]["stt_language"] = lang
        # Reset shared recognizer so new language takes effect
        with SttController.resourceLock:
            SttController.sharedRecognizer = None
            SttController.authChecked = False
        return (1, {"language": lang}, None)

    def cmd_set_on_device(self, params):
        onDevice = self.p(params, "on_device")
        if onDevice is None:
            return (0, None, ("ERR_PARAMS", "on_device required", 0))
        with self.lock:
            self.state["config"]["stt_on_device"] = onDevice
        return (1, {"on_device": onDevice}, None)
