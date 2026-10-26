"""Main window: project list on the left, details on the right."""

from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from .. import store
from ..detect import ProjectInfo, detect
from ..runner import Runner
from .detail import DetailView

PATH_ROLE = Qt.ItemDataRole.UserRole
_dots: dict[str, QIcon] = {}


def dot(color: str) -> QIcon:
    if color not in _dots:
        pix = QPixmap(12, 12)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(1, 1, 10, 10)
        p.end()
        _dots[color] = QIcon(pix)
    return _dots[color]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LocalDev")
        self.settings = QSettings("LocalDev", "LocalDev")
        if not self.restoreGeometry(self.settings.value("geometry", QByteArray())):
            self.resize(850, 600)
        self.runner = Runner(self)
        self.infos: dict[str, ProjectInfo] = {}
        self.views: dict[str, DetailView] = {}

        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_select)
        add_btn = QPushButton("+ Add project")
        add_btn.clicked.connect(self._add)
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 4, 12)
        heading = QLabel("Projects")
        heading.setObjectName("heading")
        left_layout.addWidget(heading)
        left_layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.addWidget(add_btn, 1)
        row.addWidget(self.remove_btn)
        left_layout.addLayout(row)

        self.stack = QStackedWidget()
        self.empty = QLabel("Add a project folder to get started.")
        self.empty.setObjectName("muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.empty)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 940])
        self.setCentralWidget(splitter)

        self.runner.state.connect(lambda project, _key, _running: self._paint(project))

        for path in store.load():
            self._add_item(path)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.remove_btn.setEnabled(self.list.currentItem() is not None)

    # --- list ---

    def _paths(self) -> list[str]:
        return [self.list.item(i).data(PATH_ROLE) for i in range(self.list.count())]

    def _item(self, path: str) -> QListWidgetItem | None:
        for i in range(self.list.count()):
            if self.list.item(i).data(PATH_ROLE) == path:
                return self.list.item(i)
        return None

    def _add_item(self, path: str) -> QListWidgetItem:
        info = detect(path)
        self.infos[path] = info
        item = QListWidgetItem(info.name)
        item.setData(PATH_ROLE, path)
        item.setToolTip(path)
        self.list.addItem(item)
        self._paint(path)
        return item

    def _paint(self, path: str):
        item = self._item(path)
        if item:
            item.setIcon(dot("#16a34a" if self.runner.running(path) else "#9ca3af"))

    def _add(self):
        folder = QFileDialog.getExistingDirectory(self, "Select project folder")
        if not folder:
            return
        path = str(Path(folder).resolve())
        if not (Path(path) / "package.json").is_file():
            QMessageBox.warning(self, "LocalDev", "This folder has no package.json.")
            return
        item = self._item(path) or self._add_item(path)
        store.save(self._paths())
        self.list.setCurrentItem(item)

    def _remove(self):
        item = self.list.currentItem()
        if not item:
            return
        path = item.data(PATH_ROLE)
        answer = QMessageBox.question(
            self, "Remove project",
            f"Remove {self.infos[path].name} from the list?\nThe project folder will not be deleted.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.runner.stop_project(path)
        view = self.views.pop(path, None)
        if view:
            self.stack.removeWidget(view)
            view.deleteLater()
        self.infos.pop(path, None)
        self.list.takeItem(self.list.row(item))
        store.save(self._paths())

    # --- detail ---

    def _on_select(self, item: QListWidgetItem | None, _previous):
        self.remove_btn.setEnabled(item is not None)
        if not item:
            self.stack.setCurrentWidget(self.empty)
            return
        path = item.data(PATH_ROLE)
        self.stack.setCurrentWidget(self.views.get(path) or self._make_view(path))

    def _make_view(self, path: str) -> DetailView:
        view = DetailView(self.infos[path], self.runner)
        view.reload_requested.connect(self._reload)
        self.views[path] = view
        self.stack.addWidget(view)
        return view

    def _reload(self, path: str):
        info = detect(path)
        self.infos[path] = info
        self._item(path).setText(info.name)
        old = self.views.pop(path)
        self.stack.setCurrentWidget(self._make_view(path))
        self.stack.removeWidget(old)
        old.deleteLater()

    def closeEvent(self, event):
        if self.runner.any_running():
            answer = QMessageBox.question(
                self, "Quit", "Some processes are still running. Stop them all and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.runner.stop_all()
        self.settings.setValue("geometry", self.saveGeometry())
        event.accept()
