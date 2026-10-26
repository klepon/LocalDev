"""Panel kanan: detail satu project, tombol aksi, dan log."""

import os
import re
import subprocess
from functools import partial

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QTextCursor
from PySide6.QtWidgets import (
    QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from ..detect import WRANGLER, Action, ProjectInfo
from ..runner import NO_WINDOW, Runner

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
SCRIPT_COLUMNS = 4


class DetailView(QWidget):
    reload_requested = Signal(str)

    def __init__(self, info: ProjectInfo, runner: Runner, parent=None):
        super().__init__(parent)
        self.info = info
        self.runner = runner
        self.path = info.path
        self.buttons: dict[str, tuple[QPushButton, str]] = {}
        self.log_views: dict[str, QPlainTextEdit] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.addLayout(self._header())

        if info.error:
            error = QLabel(info.error)
            error.setObjectName("error")
            root.addWidget(error)
            root.addStretch()
            return

        cards = QHBoxLayout()
        if info.wrangler:
            cards.addWidget(self._wrangler_card())
        if info.migrations:
            cards.addWidget(self._target_card("Migrasi database", info.migrations))
        if info.deploys:
            cards.addWidget(self._target_card("Deploy Cloudflare", info.deploys))
        if cards.count():
            root.addLayout(cards)
        if info.scripts:
            root.addWidget(self._scripts_card())
        root.addWidget(self._log_panel(), 1)

        runner.output.connect(self._on_output)
        runner.state.connect(self._on_state)
        runner.finished.connect(self._on_finished)
        runner.url_found.connect(self._on_url)

        for key in runner.keys(self.path):
            self._ensure_tab(key)
        for key in self.buttons:
            self._sync_button(key)
        self._sync_dev()

        whoami = WRANGLER["whoami"]
        if info.wrangler and whoami.key not in runner.keys(self.path):
            self.runner.start(self.path, whoami)

    # --- layout ---

    def _header(self) -> QHBoxLayout:
        box = QHBoxLayout()
        text = QVBoxLayout()
        title = QLabel(self.info.name)
        title.setObjectName("title")
        sub = QLabel(" · ".join(p for p in (f"v{self.info.version}" if self.info.version else "", self.path) if p))
        sub.setObjectName("muted")
        sub.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.addWidget(title)
        text.addWidget(sub)
        box.addLayout(text, 1)

        self.dev_btn = QPushButton()
        self.dev_btn.setObjectName("primary")
        self.dev_btn.clicked.connect(lambda: self.info.dev and self._toggle(self.info.dev))
        self.browser_btn = QPushButton("Buka browser")
        self.browser_btn.clicked.connect(self._open_browser)
        folder_btn = QPushButton("Folder")
        folder_btn.clicked.connect(lambda: os.startfile(self.path))
        code_btn = QPushButton("VS Code")
        code_btn.clicked.connect(self._open_code)
        reload_btn = QPushButton("Muat ulang")
        reload_btn.setToolTip("Baca ulang package.json")
        reload_btn.clicked.connect(lambda: self.reload_requested.emit(self.path))
        for btn in (self.dev_btn, self.browser_btn, folder_btn, code_btn, reload_btn):
            box.addWidget(btn)
        return box

    def _wrangler_card(self) -> QGroupBox:
        group = QGroupBox("Wrangler")
        layout = QVBoxLayout(group)
        self.wrangler_status = QLabel("Memeriksa login…")
        layout.addWidget(self.wrangler_status)
        row = QHBoxLayout()
        for key, label in (("whoami", "Cek"), ("login", "Login"), ("logout", "Logout")):
            row.addWidget(self._action_button(WRANGLER[key], label))
        row.addStretch()
        layout.addLayout(row)
        return group

    def _target_card(self, title: str, actions: list[Action]) -> QGroupBox:
        group = QGroupBox(title)
        row = QHBoxLayout(group)
        for action in actions:
            btn = self._action_button(action, action.label)
            if action.target == "production":
                btn.setObjectName("danger")
            row.addWidget(btn)
        row.addStretch()
        return group

    def _scripts_card(self) -> QGroupBox:
        group = QGroupBox("Script lain")
        grid = QGridLayout(group)
        for i, action in enumerate(self.info.scripts):
            grid.addWidget(self._action_button(action, action.label), i // SCRIPT_COLUMNS, i % SCRIPT_COLUMNS)
        return group

    def _log_panel(self) -> QTabWidget:
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        clear = QPushButton("Bersihkan")
        clear.clicked.connect(self._clear_log)
        self.tabs.setCornerWidget(clear)
        return self.tabs

    def _action_button(self, action: Action, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setToolTip(action.command)
        btn.clicked.connect(partial(self._toggle, action))
        self.buttons[action.key] = (btn, label)
        return btn

    def _ensure_tab(self, key: str) -> tuple[QPlainTextEdit, bool]:
        view = self.log_views.get(key)
        if view:
            return view, False
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setMaximumBlockCount(5000)
        view.setFont(QFont("Consolas", 9))
        view.setPlainText(self.runner.log(self.path, key))
        view.setProperty("key", key)
        self.log_views[key] = view
        self.tabs.addTab(view, "")
        self._sync_tab(key)
        return view, True

    # --- aksi ---

    def _toggle(self, action: Action):
        if self.runner.is_running(self.path, action.key):
            self.runner.stop(self.path, action.key)
            return
        if not self._confirm(action):
            return
        self.runner.start(self.path, action)
        self.tabs.setCurrentWidget(self.log_views[action.key])

    def _confirm(self, action: Action) -> bool:
        if action.target == "production":
            text, ok = QInputDialog.getText(
                self, "Konfirmasi production",
                f"Perintah ini mengubah PRODUCTION:\n{action.command}\n\n"
                f"Ketik nama project ({self.info.name}) untuk lanjut:")
            return ok and text.strip() == self.info.name
        if action.danger:
            answer = QMessageBox.question(self, "Konfirmasi", f"Jalankan perintah ini?\n\n{action.command}")
            return answer == QMessageBox.StandardButton.Yes
        return True

    def _open_browser(self):
        if self.info.dev and (url := self.runner.url(self.path, self.info.dev.key)):
            QDesktopServices.openUrl(QUrl(url))

    def _open_code(self):
        subprocess.Popen(["cmd", "/d", "/c", "code", "."], cwd=self.path, creationflags=NO_WINDOW)

    def _clear_log(self):
        view = self.tabs.currentWidget()
        if view:
            self.runner.clear(self.path, view.property("key"))
            view.clear()

    # --- sinyal runner ---

    def _on_output(self, project: str, key: str, text: str):
        if project != self.path:
            return
        view, created = self._ensure_tab(key)
        if created:
            return
        bar = view.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum() - 4
        cursor = QTextCursor(view.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        if at_bottom:
            bar.setValue(bar.maximum())

    def _on_state(self, project: str, key: str, running: bool):
        if project != self.path:
            return
        if running and key in self.log_views:
            self.log_views[key].setPlainText(self.runner.log(self.path, key))
        if key in self.log_views:
            self._sync_tab(key)
        if key in self.buttons:
            self._sync_button(key)
        if self.info.dev and key == self.info.dev.key:
            self._sync_dev()

    def _on_finished(self, project: str, key: str, code: int):
        if project != self.path:
            return
        if key == WRANGLER["whoami"].key:
            self._show_whoami(code)
        elif key in (WRANGLER["login"].key, WRANGLER["logout"].key):
            self.runner.start(self.path, WRANGLER["whoami"])

    def _on_url(self, project: str, key: str, _url: str):
        if project == self.path and self.info.dev and key == self.info.dev.key:
            self._sync_dev()

    # --- sinkron tampilan ---

    def _show_whoami(self, code: int):
        log = self.runner.log(self.path, WRANGLER["whoami"].key)
        if "not authenticated" in log.lower() or "not logged in" in log.lower():
            self.wrangler_status.setText("Belum login")
        elif m := EMAIL.search(log):
            self.wrangler_status.setText(f"Login sebagai {m.group(0).rstrip('.')}")
        elif code == 0:
            self.wrangler_status.setText("Sudah login")
        else:
            self.wrangler_status.setText("Gagal cek login, lihat log")

    def _sync_button(self, key: str):
        btn, label = self.buttons[key]
        btn.setText(f"■ {label}" if self.runner.is_running(self.path, key) else label)

    def _sync_tab(self, key: str):
        index = self.tabs.indexOf(self.log_views[key])
        label = self.runner.label(self.path, key)
        self.tabs.setTabText(index, f"● {label}" if self.runner.is_running(self.path, key) else label)

    def _sync_dev(self):
        dev = self.info.dev
        if not dev:
            self.dev_btn.setText("Tidak ada script dev")
            self.dev_btn.setEnabled(False)
            self.browser_btn.setEnabled(False)
            return
        running = self.runner.is_running(self.path, dev.key)
        self.dev_btn.setText("■ Stop" if running else "▶ Start")
        url = self.runner.url(self.path, dev.key)
        self.browser_btn.setEnabled(running and bool(url))
        self.browser_btn.setToolTip(url)
