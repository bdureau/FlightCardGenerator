"""Éditeurs de champs génériques construits à partir du schéma ``core.card.FIELDS``."""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QLabel, QLineEdit,
                             QPlainTextEdit, QWidget)

from ..core.card import BOOL, CHOICE, DATE, LOCATION, MULTILINE, FieldDef
from ..i18n import Translator


class FieldEditor:
    """Associe un FieldDef à un widget Qt (lecture / écriture / retraduction)."""

    def __init__(self, fdef: FieldDef, on_change: Callable[[str], None]):
        self.fdef = fdef
        self.key = fdef.key
        self._on_change = on_change
        self.label: Optional[QLabel] = None if fdef.kind == BOOL else QLabel()
        self.widget = self._create()
        if self.label is not None:
            self.label.setBuddy(self.widget)
        self.widget.setObjectName(f"field_{fdef.key}")

    # ------------------------------------------------------------------ création
    def _create(self) -> QWidget:
        k = self.fdef.kind
        if k == MULTILINE:
            w = QPlainTextEdit()
            w.setTabChangesFocus(True)
            w.setMinimumHeight(64)
            w.setMaximumHeight(110)
            w.textChanged.connect(self._changed)
        elif k == BOOL:
            w = QCheckBox()
            w.toggled.connect(self._changed)
        elif k == CHOICE:
            w = QComboBox()
            for c in self.fdef.choices:
                w.addItem(c or "—", c)
            w.currentIndexChanged.connect(self._changed)
        elif k == DATE:
            w = QDateEdit()
            w.setCalendarPopup(True)
            w.setDate(QDate.currentDate())
            w.dateChanged.connect(self._changed)
        elif k == LOCATION:
            w = QComboBox()
            w.setEditable(True)
            w.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            w.editTextChanged.connect(self._changed)
        else:
            w = QLineEdit()
            w.setClearButtonEnabled(True)
            w.textChanged.connect(self._changed)
        return w

    def _changed(self, *_):
        self._on_change(self.key)

    # ------------------------------------------------------------------ valeur
    def value(self) -> str:
        w, k = self.widget, self.fdef.kind
        if k == MULTILINE:
            return w.toPlainText()
        if k == BOOL:
            return "1" if w.isChecked() else "0"
        if k == CHOICE:
            return w.currentData() or ""
        if k == DATE:
            return w.date().toString("yyyy-MM-dd")
        if k == LOCATION:
            return w.currentText().strip()
        return w.text()

    def set_value(self, value: str) -> None:
        w, k = self.widget, self.fdef.kind
        value = value or ""
        w.blockSignals(True)
        try:
            if k == MULTILINE:
                w.setPlainText(value)
            elif k == BOOL:
                w.setChecked(value in ("1", "true", "True", "yes"))
            elif k == CHOICE:
                idx = w.findData(value)
                if idx < 0 and value:
                    w.addItem(value, value)
                    idx = w.count() - 1
                w.setCurrentIndex(max(0, idx))
            elif k == DATE:
                d = QDate.fromString(value, "yyyy-MM-dd")
                w.setDate(d if d.isValid() else QDate.currentDate())
            elif k == LOCATION:
                w.setEditText(value)
            else:
                w.setText(value)
                w.setCursorPosition(0)
        finally:
            w.blockSignals(False)

    def set_locations(self, places: list[str]) -> None:
        if self.fdef.kind != LOCATION:
            return
        current = self.value()
        w = self.widget
        w.blockSignals(True)
        w.clear()
        w.addItems(places)
        w.setEditText(current)
        w.blockSignals(False)

    # ------------------------------------------------------------------ i18n
    def retranslate(self, tr: Translator) -> None:
        text = tr(self.fdef.label_key)
        if self.fdef.kind == BOOL:
            self.widget.setText(text)
        else:
            self.label.setText(text + " :" if tr.lang == "fr" else text + ":")
        if self.fdef.kind == CHOICE:
            w = self.widget
            for i in range(w.count()):
                data = w.itemData(i)
                if not data:
                    w.setItemText(i, tr("none"))
                elif data in ("yes", "no"):
                    w.setItemText(i, tr(data))
                elif tr(f"level_{data}") != f"level_{data}":
                    w.setItemText(i, tr(f"level_{data}"))
        if self.fdef.kind == DATE:
            fmt = tr.locale.dateFormat(tr.locale.FormatType.ShortFormat)
            if "yyyy" not in fmt:
                fmt = fmt.replace("yy", "yyyy")
            self.widget.setDisplayFormat(fmt)
        if self.fdef.auto:
            self.widget.setToolTip(tr("tip_auto"))
            if self.label is not None:
                self.label.setToolTip(tr("tip_auto"))
        self.widget.setProperty("autoField", self.fdef.auto)
