"""Widgets réutilisables : zone de glisser-déposer, aperçu, sélection de simulation."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPalette
from PyQt6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QFrame,
                             QHeaderView, QLabel, QSizePolicy, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from ..core.models import SimulationInfo
from ..i18n import Translator

ACCEPTED_EXTENSIONS = (".ork", ".rkt", ".xml")


def accepted_local_file(mime) -> Optional[str]:
    if not mime.hasUrls():
        return None
    for url in mime.urls():
        if url.isLocalFile():
            path = url.toLocalFile()
            if Path(path).suffix.lower() in ACCEPTED_EXTENSIONS:
                return path
    return None


class DropZone(QFrame):
    """Cadre cliquable acceptant les fichiers .ork / .rkt / .xml."""
    fileDropped = pyqtSignal(str)
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.addWidget(self._label)
        self._hint = ""
        self._active_text = ""
        self._set_active(False)

    def set_texts(self, hint: str, active: str):
        self._hint, self._active_text = hint, active
        self._label.setText(hint)

    def _set_active(self, active: bool):
        hl = self.palette().color(QPalette.ColorRole.Highlight)
        border = hl.name() if active else "#8a94b8"
        bg = QColor(hl)
        bg.setAlpha(45 if active else 12)
        self.setStyleSheet(
            f"DropZone {{ border: 2px dashed {border}; border-radius: 8px;"
            f" background: rgba({bg.red()},{bg.green()},{bg.blue()},{bg.alpha()}); }}")
        if self._label is not None:
            self._label.setText(self._active_text if active and self._active_text else self._hint)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if accepted_local_file(event.mimeData()):
            event.acceptProposedAction()
            self._set_active(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_active(False)

    def dropEvent(self, event):
        self._set_active(False)
        path = accepted_local_file(event.mimeData())
        if path:
            event.acceptProposedAction()
            self.fileDropped.emit(path)


class PreviewWidget(QWidget):
    """Affiche une QImage mise à l'échelle en conservant les proportions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image: Optional[QImage] = None
        self.setMinimumSize(320, 230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_image(self, image: QImage):
        self._image = image
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), self.palette().color(QPalette.ColorRole.Mid))
        if self._image is None or self._image.isNull():
            return
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        iw, ih = self._image.width(), self._image.height()
        avail = QRectF(self.rect()).adjusted(10, 10, -10, -10)
        s = min(avail.width() / iw, avail.height() / ih)
        w, h = iw * s, ih * s
        target = QRectF(avail.x() + (avail.width() - w) / 2, avail.y() + (avail.height() - h) / 2, w, h)
        p.fillRect(target.translated(4, 4), QColor(0, 0, 0, 60))
        p.drawImage(target, self._image)


class SimulationDialog(QDialog):
    """Liste les simulations d'un fichier et renvoie l'indice choisi."""

    def __init__(self, simulations: list[SimulationInfo], file_name: str, tr: Translator,
                 parent=None, current: int = 0):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg_select_sim_title"))
        self.resize(760, 360)
        lay = QVBoxLayout(self)
        info = QLabel(tr("dlg_select_sim_text", file=file_name))
        info.setWordWrap(True)
        lay.addWidget(info)
        self.table = QTableWidget(len(simulations), 5)
        self.table.setHorizontalHeaderLabels([tr("col_sim_name"), tr("col_motors"), tr("col_apogee"),
                                              tr("col_max_velocity"), tr("col_status")])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 5):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        for row, sim in enumerate(simulations):
            name = sim.name + (f" ({sim.config_name})" if sim.config_name else "")
            status_key = f"sim_status_{sim.status}" if sim.status else ""
            status = tr(status_key) if status_key and tr(status_key) != status_key else sim.status
            cells = [name, sim.motor_summary(),
                     f"{sim.max_altitude:.0f}" if sim.max_altitude is not None else "—",
                     f"{sim.max_velocity:.1f}" if sim.max_velocity is not None else "—",
                     status]
            for col, txt in enumerate(cells):
                item = QTableWidgetItem(txt)
                if col in (2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, item)
        self.table.selectRow(min(max(0, current), len(simulations) - 1))
        self.table.doubleClicked.connect(lambda *_: self.accept())
        lay.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def selected_index(self) -> int:
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else 0
