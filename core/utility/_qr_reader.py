#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Core/utility/_qr_reader.py"
# date="2026-06-27" author="Cascade" session_id="utility-qr"
# context="QR code reader utility. Reads image from clipboard, decodes QR, returns text."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="_qr_reader.py" domain="utility" authority="gui"}
# [@SUMMARY]{summary="Reads QR code from clipboard image. Globally reusable. PyQt6 GUI."}
# [@CLASS]{class="QRReader" domain="utility" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="Show" type="command"}
# [@METHOD]{method="DecodeClipboard" type="helper"}
# [@METHOD]{method="DecodeFile" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class QRReader:
    """QR code reader. Reads from clipboard or file path. Globally reusable."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "last_result": "",
            "last_source": "",
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "show":
            return self.Show(params)
        elif command == "decode_file":
            return self.DecodeFile(params)
        elif command == "decode_clipboard":
            return self.DecodeClipboard(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def DecodeFile(self, params):
        filepath = self._p(params, "filepath")
        if filepath is None:
            return (0, None, ("MISSING_PARAM", "filepath required", 0))
        try:
            import cv2
            cv_img = cv2.imread(filepath)
            if cv_img is None:
                return (0, None, ("FILE_ERROR", "Could not read image: " + filepath, 0))
            det = cv2.QRCodeDetector()
            data, points, _ = det.detectAndDecode(cv_img)
            if data:
                self.state["last_result"] = data
                self.state["last_source"] = filepath
                return (1, data, None)
            else:
                return (0, None, ("NO_QR", "No QR code found in file", 0))
        except Exception as exc:
            return (0, None, ("EXCEPTION", str(exc), 0))

    def DecodeClipboard(self, params):
        try:
            import cv2
            import numpy as np
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QGuiApplication

            app = QApplication.instance() or QApplication(sys.argv)
            clip = app.clipboard()
            mime = clip.mimeData()
            if not mime.hasImage():
                return (0, None, ("NO_IMAGE", "No image in clipboard", 0))
            qimg = clip.image()
            if qimg.isNull():
                return (0, None, ("EMPTY_IMAGE", "Empty image in clipboard", 0))
            w, h = qimg.width(), qimg.height()
            ptr = qimg.bits()
            ptr.setsize(h * w * 4)
            arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, w, 4)
            cv_img = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
            det = cv2.QRCodeDetector()
            data, points, _ = det.detectAndDecode(cv_img)
            if data:
                self.state["last_result"] = data
                self.state["last_source"] = "clipboard"
                QGuiApplication.clipboard().setText(data)
                return (1, data, None)
            else:
                return (0, None, ("NO_QR", "No QR code found in clipboard image", 0))
        except Exception as exc:
            return (0, None, ("EXCEPTION", str(exc), 0))

    def Show(self, params):
        from PyQt6.QtWidgets import (
            QApplication, QWidget, QVBoxLayout, QHBoxLayout,
            QPushButton, QTextEdit, QLabel
        )
        from PyQt6.QtGui import QKeySequence, QShortcut, QGuiApplication

        app = QApplication.instance() or QApplication(sys.argv)
        win = QWidget()
        win.setWindowTitle("QR Reader")
        win.resize(500, 400)
        layout = QVBoxLayout()

        btn_row = QHBoxLayout()
        btn = QPushButton("Paste Image from Clipboard")
        file_btn = QPushButton("Open File...")
        btn_row.addWidget(btn)
        btn_row.addWidget(file_btn)
        layout.addLayout(btn_row)

        res = QTextEdit()
        res.setReadOnly(True)
        res.setAcceptRichText(False)
        label = QLabel("Copy QR image, then click Paste or press Ctrl+V")
        copy_btn = QPushButton("Copy Result")
        layout.addWidget(label)
        layout.addWidget(res)
        layout.addWidget(copy_btn)
        win.setLayout(layout)

        def do_paste():
            result = self.DecodeClipboard({})
            if result[0] == 1:
                res.setPlainText(result[1])
            else:
                res.setPlainText("Failed: " + str(result[2]))

        def do_file():
            from PyQt6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(win, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
            if path:
                result = self.DecodeFile({"filepath": path})
                if result[0] == 1:
                    res.setPlainText(result[1])
                else:
                    res.setPlainText("Failed: " + str(result[2]))

        btn.clicked.connect(do_paste)
        file_btn.clicked.connect(do_file)
        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(res.toPlainText()))
        shortcut = QShortcut(QKeySequence("Ctrl+V"), win)
        shortcut.activated.connect(do_paste)

        win.show()
        app.exec()
        return (1, {"last_result": self.state["last_result"], "last_source": self.state["last_source"]}, None)


if __name__ == "__main__":
    reader = QRReader()
    result = reader.Run("show", {})
    if result[0] == 0:
        sys.stderr.write("ERROR: " + str(result[2]) + "\n")
        sys.exit(1)
