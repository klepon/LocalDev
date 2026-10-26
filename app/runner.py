"""Run project commands through QProcess, keep their logs, and kill them along with child processes."""

import codecs
import re
import subprocess

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from .detect import Action

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
URL = re.compile(r"https?://(?:localhost|127\.0\.0\.1):\d+/?")
MAX_LOG = 400_000
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

Key = tuple[str, str]  # (project path, action key)


class Runner(QObject):
    output = Signal(str, str, str)
    state = Signal(str, str, bool)
    finished = Signal(str, str, int)
    url_found = Signal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._procs: dict[Key, QProcess] = {}
        self._decoders: dict[Key, codecs.IncrementalDecoder] = {}
        self._logs: dict[Key, str] = {}
        self._labels: dict[Key, str] = {}
        self._urls: dict[Key, str] = {}

    # --- query ---

    def is_running(self, project: str, key: str) -> bool:
        return (project, key) in self._procs

    def running(self, project: str) -> list[str]:
        return [k for p, k in self._procs if p == project]

    def any_running(self) -> bool:
        return bool(self._procs)

    def keys(self, project: str) -> list[str]:
        return [k for p, k in self._logs if p == project]

    def log(self, project: str, key: str) -> str:
        return self._logs.get((project, key), "")

    def label(self, project: str, key: str) -> str:
        return self._labels.get((project, key), key)

    def url(self, project: str, key: str) -> str:
        return self._urls.get((project, key), "")

    def clear(self, project: str, key: str):
        if (project, key) in self._logs:
            self._logs[(project, key)] = ""

    # --- control ---

    def start(self, project: str, action: Action):
        k = (project, action.key)
        if k in self._procs:
            return
        proc = QProcess(self)
        proc.setWorkingDirectory(project)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("NO_COLOR", "1")
        env.insert("FORCE_COLOR", "0")
        proc.setProcessEnvironment(env)
        proc.setProgram("cmd.exe")
        proc.setNativeArguments(f'/d /s /c "{action.command}"')

        self._procs[k] = proc
        self._decoders[k] = codecs.getincrementaldecoder("utf-8")("replace")
        self._labels[k] = action.label
        self._logs[k] = ""
        self._urls.pop(k, None)

        proc.readyReadStandardOutput.connect(lambda: self._read(k))
        proc.finished.connect(lambda code, _status: self._done(k, code))
        proc.errorOccurred.connect(lambda err: self._error(k, err))

        self._append(k, f"> {action.command}\n")
        self.state.emit(project, action.key, True)
        proc.start()

    def stop(self, project: str, key: str):
        proc = self._procs.get((project, key))
        if not proc:
            return
        pid = proc.processId()
        if pid:
            # cmd -> npm -> node -> workerd: kill the whole process tree at once.
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, creationflags=NO_WINDOW)
        else:
            proc.kill()

    def stop_project(self, project: str):
        for key in self.running(project):
            self.stop(project, key)

    def stop_all(self):
        procs = list(self._procs.items())
        for (project, key), _ in procs:
            self.stop(project, key)
        for _, proc in procs:
            proc.waitForFinished(3000)

    # --- internal ---

    def _read(self, k: Key):
        proc = self._procs.get(k)
        if proc:
            self._append(k, self._decoders[k].decode(bytes(proc.readAllStandardOutput())))

    def _append(self, k: Key, text: str):
        text = ANSI.sub("", text).replace("\r\n", "\n").replace("\r", "")
        if not text:
            return
        log = self._logs.get(k, "") + text
        self._logs[k] = log[-MAX_LOG:]
        self.output.emit(*k, text)
        if k not in self._urls and (m := URL.search(log[-2000:])):
            self._urls[k] = m.group(0)
            self.url_found.emit(*k, m.group(0))

    def _done(self, k: Key, code: int):
        if k not in self._procs:
            return
        self._read(k)
        self._append(k, self._decoders[k].decode(b"", final=True))
        self._append(k, f"\n[exited with code {code}]\n")
        self._finish(k, code)

    def _error(self, k: Key, err):
        if err == QProcess.ProcessError.FailedToStart and k in self._procs:
            self._append(k, "\n[failed to start command]\n")
            self._finish(k, -1)

    def _finish(self, k: Key, code: int):
        self._procs.pop(k).deleteLater()
        self._decoders.pop(k, None)
        self._urls.pop(k, None)
        self.state.emit(*k, False)
        self.finished.emit(*k, code)
