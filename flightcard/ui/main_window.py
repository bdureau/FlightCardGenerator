"""Fenêtre principale de l'application."""
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import (PYQT_VERSION_STR, QT_VERSION_STR, QBuffer, QByteArray, QIODevice,
                          QSize, Qt, QTimer, QUrl)
from PyQt6.QtGui import QAction, QDesktopServices, QIcon, QImage, QKeySequence, QPixmap
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QGridLayout,
                             QGroupBox, QHBoxLayout, QLabel, QMainWindow,
                             QMessageBox, QPushButton, QScrollArea, QSplitter, QTabBar,
                             QTabWidget, QToolBar, QVBoxLayout, QWidget)

from .. import __app_name__, __version__
from ..core.card import FIELD_BY_KEY, FIELDS, PILOT_PROFILE_KEYS, FlightCard
from ..core.mapping import (AUTO_DEPENDENCIES, auto_targets, card_values_from_simulation,
                            compute_auto_values)
from ..core.models import ParsedDocument, TimeSeries
from ..core.rocketry import thrust_to_weight_verdict, to_float
from ..i18n import LANGUAGE_NAMES, LANGUAGES, LanguageManager, Translator
from ..parsers import ParseError, parse_simulation_file
from ..printing.renderer import CardRenderer, setup_printer_page
from ..storage.card_xml import load_card, save_card
from ..storage.paths import documents_dir, manual_path, resource_dir
from ..storage.settings import SettingsStore
from .field_editors import FieldEditor
from .widgets import DropZone, PreviewWidget, SimulationDialog, accepted_local_file

# Champs conservés lors de l'import d'une nouvelle simulation (saisis par le pilote)
KEEP_ON_IMPORT = set(PILOT_PROFILE_KEYS) | {
    "flight_date", "flight_location", "first_flight", "pilot_notes", "kit", "kit_modified",
    "scratch_built", "model_classic", "model_fantasy", "model_scale", "payload",
    "launch_rod", "launch_rail", "recovery_other", "remarks"}


class MainWindow(QMainWindow):
    def __init__(self, store: SettingsStore, lang: LanguageManager, print_lang: str):
        super().__init__()
        self.store = store
        self.lang = lang
        self.print_lang = print_lang
        self.doc: Optional[ParsedDocument] = None
        self.sim_index = 0
        self.series = TimeSeries()
        self.source_file = ""
        self.card_logo_png: Optional[bytes] = None     # logo embarqué d'une fiche XML chargée
        self._manual_auto: set[str] = set()     # champs auto modifiés à la main
        self._loading = False
        self._i18n: list[Callable[[Translator], None]] = []
        self.editors: dict[str, FieldEditor] = {}

        self.setAcceptDrops(True)
        icon_path = resource_dir() / "icons" / "app.png"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(250)
        self._preview_timer.timeout.connect(self.refresh_preview)

        for f in FIELDS:
            self.editors[f.key] = FieldEditor(f, self._on_field_changed)

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_central()
        self.statusBar()

        self._load_profile_into_form()
        self.lang.languageChanged.connect(lambda _l: self.retranslate())
        self.retranslate()
        self._restore_window_state()
        self.statusBar().showMessage(self.tr_("status_ready"))
        self.refresh_preview()

    # ================================================================ utilitaires
    def tr_(self, key: str, **kw) -> str:
        return self.lang.tr(key, **kw)

    @property
    def print_tr(self) -> Translator:
        return Translator(self.print_lang)

    def _t(self, fn: Callable[[Translator], None]):
        """Enregistre un élément à retraduire lors d'un changement de langue."""
        self._i18n.append(fn)

    def ed(self, key: str) -> FieldEditor:
        return self.editors[key]

    # ================================================================ actions / menus
    def _action(self, key: str, slot, shortcut=None) -> QAction:
        act = QAction(self)
        act.triggered.connect(slot)
        if shortcut is not None:
            act.setShortcut(QKeySequence(shortcut))
        self._t(lambda tr, a=act, k=key: a.setText(tr(k)))
        return act

    def _build_actions(self):
        S = QKeySequence.StandardKey
        self.act_new = self._action("act_new_card", self.new_card, S.New)
        self.act_open = self._action("act_open", self.open_simulation_dialog, S.Open)
        self.act_reselect = self._action("act_reselect_sim", self.reselect_simulation, "Ctrl+R")
        self.act_reselect.setEnabled(False)
        self.act_save = self._action("act_save_xml", self.save_card_dialog, S.Save)
        self.act_load = self._action("act_load_xml", self.load_card_dialog, "Ctrl+L")
        self.act_pdf = self._action("act_export_pdf", self.export_pdf, "Ctrl+E")
        self.act_preview = self._action("act_preview", self.print_preview, "Ctrl+Shift+P")
        self.act_print = self._action("act_print", self.print_card, S.Print)
        self.act_quit = self._action("act_quit", self.close, S.Quit)
        self.act_quit.setMenuRole(QAction.MenuRole.QuitRole)
        self.act_manual = self._action("act_manual", self.open_manual, S.HelpContents)
        self.act_about = self._action("act_about", self.about)
        self.act_about.setMenuRole(QAction.MenuRole.AboutRole)

    def _build_menus(self):
        mb = self.menuBar()
        m_file = mb.addMenu("")
        for a in (self.act_new, None, self.act_open, self.act_reselect, None, self.act_save,
                  self.act_load, None, self.act_pdf, self.act_preview, self.act_print, None,
                  self.act_quit):
            m_file.addSeparator() if a is None else m_file.addAction(a)
        m_help = mb.addMenu("")
        m_help.addAction(self.act_manual)
        m_help.addSeparator()
        m_help.addAction(self.act_about)
        self._t(lambda tr: m_file.setTitle(tr("menu_file")))
        self._t(lambda tr: m_help.setTitle(tr("menu_help")))

    def _build_toolbar(self):
        tb = QToolBar(self)
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        self.addToolBar(tb)
        for a in (self.act_open, self.act_save, self.act_preview, self.act_print):
            tb.addAction(a)
        tb.addSeparator()

        self.lbl_ui_lang = QLabel()
        self.cmb_ui_lang = QComboBox()
        self.lbl_print_lang = QLabel()
        self.cmb_print_lang = QComboBox()
        for code in LANGUAGES:
            self.cmb_ui_lang.addItem(LANGUAGE_NAMES[code], code)
            self.cmb_print_lang.addItem(LANGUAGE_NAMES[code], code)
        self.cmb_ui_lang.setCurrentIndex(LANGUAGES.index(self.lang.language))
        self.cmb_print_lang.setCurrentIndex(LANGUAGES.index(self.print_lang))
        self.cmb_ui_lang.currentIndexChanged.connect(
            lambda i: self.lang.set_language(self.cmb_ui_lang.itemData(i)))
        self.cmb_print_lang.currentIndexChanged.connect(self._on_print_language)
        self.chk_annex = QCheckBox()
        self.chk_annex.setChecked(bool(self.store.settings.print_annex))
        self.chk_annex.toggled.connect(self._on_annex_toggled)

        for w in (self.lbl_ui_lang, self.cmb_ui_lang):
            tb.addWidget(w)
        spacer = QWidget()
        spacer.setFixedWidth(14)
        tb.addWidget(spacer)
        for w in (self.lbl_print_lang, self.cmb_print_lang):
            tb.addWidget(w)
        spacer2 = QWidget()
        spacer2.setFixedWidth(14)
        tb.addWidget(spacer2)
        tb.addWidget(self.chk_annex)
        self._t(lambda tr: self.lbl_ui_lang.setText(" " + tr("lbl_ui_language") + " "))
        self._t(lambda tr: self.lbl_print_lang.setText(" " + tr("lbl_print_language") + " "))
        self._t(lambda tr: self.chk_annex.setText(tr("chk_print_annex")))

    # ================================================================ zone centrale
    def _form(self, keys, form: Optional[QFormLayout] = None) -> QFormLayout:
        form = form or QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for k in keys:
            e = self.ed(k)
            if e.label is None:
                form.addRow(e.widget)
            else:
                form.addRow(e.label, e.widget)
        return form

    def _group(self, title_key: str, layout) -> QGroupBox:
        g = QGroupBox()
        g.setLayout(layout)
        self._t(lambda tr, gg=g: gg.setTitle(tr(title_key)))
        return g

    def _checks_row(self, keys) -> QHBoxLayout:
        h = QHBoxLayout()
        for k in keys:
            h.addWidget(self.ed(k).widget)
        h.addStretch(1)
        return h

    @staticmethod
    def _scroll(widget: QWidget) -> QScrollArea:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QScrollArea.Shape.NoFrame)
        sa.setWidget(widget)
        return sa

    def _button(self, key: str, slot) -> QPushButton:
        b = QPushButton()
        b.clicked.connect(slot)
        self._t(lambda tr, bb=b: bb.setText(tr(key)))
        return b

    def _build_central(self):
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(6, 6, 6, 6)
        drop_row = QHBoxLayout()
        self.drop_zone = DropZone()
        self.drop_zone.fileDropped.connect(self.open_path)
        self.drop_zone.clicked.connect(self.open_simulation_dialog)
        drop_row.addWidget(self.drop_zone, 1)
        drop_row.addWidget(self._button("btn_open", self.open_simulation_dialog))
        lv.addLayout(drop_row)

        self.tabs = QTabWidget()
        lv.addWidget(self.tabs, 1)
        tabs_def = [("tab_pilot", self._tab_pilot()), ("tab_rocket", self._tab_rocket()),
                    ("tab_recovery", self._tab_recovery()),
                    ("tab_propulsion", self._tab_propulsion()),
                    ("tab_simulation", self._tab_simulation())]
        for i, (key, w) in enumerate(tabs_def):
            self.tabs.addTab(self._scroll(w), "")
            self._t(lambda tr, idx=i, k=key: self.tabs.setTabText(idx, tr(k)))

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(6, 6, 6, 6)
        self.page_bar = QTabBar()
        self.page_bar.addTab("")
        self.page_bar.addTab("")
        self.page_bar.currentChanged.connect(lambda _i: self.refresh_preview())
        self._t(lambda tr: (self.page_bar.setTabText(0, tr("page_1")),
                            self.page_bar.setTabText(1, tr("page_2"))))
        rv.addWidget(self.page_bar)
        self.preview = PreviewWidget()
        rv.addWidget(self.preview, 1)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(left)
        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)
        self.setCentralWidget(self.splitter)

    # --- onglets ------------------------------------------------------------
    def _tab_pilot(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        prof = self._form(PILOT_PROFILE_KEYS)
        prof.addRow(self._button("btn_save_profile", self.save_profile))
        v.addWidget(self._group("grp_profile", prof))

        flight = self._form(["flight_date"])
        loc_row = QHBoxLayout()
        loc_row.addWidget(self.ed("flight_location").widget, 1)
        loc_row.addWidget(self._button("btn_forget_location", self.forget_location))
        flight.addRow(self.ed("flight_location").label, loc_row)
        self._form(["first_flight", "pilot_notes"], flight)
        v.addWidget(self._group("grp_flight", flight))

        logo_lay = QHBoxLayout()
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(180, 110)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setStyleSheet("QLabel { border: 1px solid #aab; background: white; color: #888; }")
        logo_lay.addWidget(self.logo_label)
        btns = QVBoxLayout()
        btns.addWidget(self._button("btn_choose_logo", self.choose_logo))
        btns.addWidget(self._button("btn_clear_logo", self.clear_logo))
        btns.addStretch(1)
        logo_lay.addLayout(btns)
        logo_lay.addStretch(1)
        v.addWidget(self._group("grp_logo", logo_lay))
        v.addStretch(1)
        return w

    def _tab_rocket(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addLayout(self._form(["rocket_name", "flight_level", "rocket_mass_kg",
                                "rocket_dry_mass_kg", "rocket_length_cm", "rocket_diameter_mm",
                                "rocket_cg_cm", "rocket_cp_cm", "stability_cal", "stage_count",
                                "sim_software"]))
        v.addWidget(self._group("grp_construction", self._checks_row(
            ["kit", "kit_modified", "scratch_built"])))
        v.addWidget(self._group("grp_model", self._checks_row(
            ["model_classic", "model_fantasy", "model_scale"])))
        v.addLayout(self._form(["payload"]))
        v.addStretch(1)
        return w

    def _tab_recovery(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(self._group("grp_ejection", self._checks_row(
            ["ejection_charge", "ejection_electronic", "ejection_dual"])))
        rec = QVBoxLayout()
        rec.addLayout(self._checks_row(["recovery_streamer", "recovery_parachute",
                                        "recovery_dual_parachute"]))
        rec.addLayout(self._form(["recovery_other", "recovery_details"]))
        v.addWidget(self._group("grp_recovery", rec))
        v.addWidget(self._group("grp_launcher", self._checks_row(["launch_rod", "launch_rail"])))
        v.addStretch(1)
        return w

    def _tab_propulsion(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        grid = QGridLayout()
        for c, key in enumerate(("col_type", "col_manufacturer", "col_impulse"), 1):
            lbl = QLabel()
            lbl.setStyleSheet("font-weight: bold;")
            self._t(lambda tr, l=lbl, k=key: l.setText(tr(k)))
            grid.addWidget(lbl, 0, c)
        for r, row in enumerate(("stage1", "stage2", "cluster"), 1):
            lbl = QLabel()
            self._t(lambda tr, l=lbl, k=f"row_{row}": l.setText(tr(k)))
            grid.addWidget(lbl, r, 0)
            for c, col in enumerate(("type", "manufacturer", "impulse"), 1):
                grid.addWidget(self.ed(f"{row}_{col}").widget, r, c)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 3)
        grid.setColumnStretch(3, 2)
        v.addWidget(self._group("grp_motors", grid))

        form = self._form(["total_impulse", "avg_thrust_n"])
        tw_row = QHBoxLayout()
        tw_row.addWidget(self.ed("thrust_weight_ratio").widget, 1)
        self.tw_verdict = QLabel()
        tw_row.addWidget(self.tw_verdict, 2)
        form.addRow(self.ed("thrust_weight_ratio").label, tw_row)
        self._form(["motor_details"], form)
        v.addLayout(form)
        h = QHBoxLayout()
        h.addStretch(1)
        h.addWidget(self._button("btn_recalc", lambda: self.recompute_auto(force=True)))
        v.addLayout(h)
        v.addStretch(1)
        return w

    def _tab_simulation(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.addLayout(self._form(["sim_name"]))
        cols = QHBoxLayout()
        res_keys = [f.key for f in FIELDS if f.group == "simulation" and f.kind == "text"
                    and f.key != "sim_name"]
        cols.addWidget(self._group("grp_results", self._form(res_keys)), 1)
        cond_keys = [f.key for f in FIELDS if f.group == "conditions"]
        cond_box = QVBoxLayout()
        cond_box.addWidget(self._group("grp_conditions", self._form(cond_keys)))
        cond_box.addStretch(1)
        cols.addLayout(cond_box, 1)
        v.addLayout(cols)
        v.addLayout(self._form(["sim_events", "sim_warnings", "remarks"]))
        v.addStretch(1)
        return w

    # ================================================================ i18n
    def retranslate(self):
        tr = self.lang.translator
        for fn in self._i18n:
            fn(tr)
        for e in self.editors.values():
            e.retranslate(tr)
        self.drop_zone.set_texts(tr("drop_hint"), tr("drop_active"))
        self._update_logo_label()
        self._update_title()
        self._update_tw_verdict()
        if self.cmb_ui_lang.currentData() != self.lang.language:
            self.cmb_ui_lang.blockSignals(True)
            self.cmb_ui_lang.setCurrentIndex(LANGUAGES.index(self.lang.language))
            self.cmb_ui_lang.blockSignals(False)
        self.store.settings.ui_language = self.lang.language
        self._save_settings_quietly()

    def _on_print_language(self, idx: int):
        self.print_lang = self.cmb_print_lang.itemData(idx)
        self.store.settings.print_language = self.print_lang
        self._save_settings_quietly()
        self.schedule_preview()

    def _on_annex_toggled(self, checked: bool):
        self.store.settings.print_annex = checked
        self.page_bar.setTabEnabled(1, checked)
        if not checked:
            self.page_bar.setCurrentIndex(0)
        self._save_settings_quietly()
        self.schedule_preview()

    def _update_title(self):
        name = self.ed("rocket_name").value().strip()
        title = self.tr_("app_title")
        self.setWindowTitle(f"{name} — {title}" if name else title)

    # ================================================================ champs
    def values(self) -> dict[str, str]:
        return {k: e.value() for k, e in self.editors.items()}

    def set_values(self, values: dict[str, str], keys=None):
        self._loading = True
        try:
            for k in keys or values.keys():
                if k in self.editors:
                    self.editors[k].set_value(values.get(k, ""))
        finally:
            self._loading = False

    def _on_field_changed(self, key: str):
        if self._loading:
            return
        if key == "rocket_name":
            self._update_title()
        if key in AUTO_DEPENDENCIES:
            if self.ed(key).value().strip():
                self._manual_auto.add(key)
            else:
                self._manual_auto.discard(key)
        self.recompute_auto(changed=key)
        self.schedule_preview()

    def recompute_auto(self, force: bool = False, changed: str = ""):
        """Recalcule les champs automatiques dépendant de ``changed`` (ou tous si ``force``).
        Un champ automatique modifié à la main n'est plus écrasé, sauf recalcul forcé."""
        targets = set(AUTO_DEPENDENCIES) if force else auto_targets(changed)
        if force:
            self._manual_auto.clear()
        targets -= self._manual_auto
        if targets:
            vals = self.values()
            keep = set(AUTO_DEPENDENCIES) - targets
            for _ in range(3):        # propagation (impulsion → niveau, poussée → P/P)
                computed = compute_auto_values(vals, self.print_lang, keep=keep)
                for k in targets:
                    if k in computed:
                        vals[k] = computed[k]
            updates = {k: vals[k] for k in targets if vals[k] != self.ed(k).value()}
            if updates:
                self.set_values(updates)
        self._update_tw_verdict()
        self.schedule_preview()

    def _update_tw_verdict(self):
        ratio = to_float(self.ed("thrust_weight_ratio").value())
        verdict = thrust_to_weight_verdict(ratio)
        color = {"ok": "#1e8449", "rso": "#b9770e", "forbidden": "#c0392b"}.get(verdict, "")
        self.tw_verdict.setText(self.tr_(f"tw_{verdict}") if verdict else "")
        self.tw_verdict.setStyleSheet(f"color: {color}; font-weight: bold;" if color else "")

    # ================================================================ aperçu
    def schedule_preview(self):
        self._preview_timer.start()

    def current_logo(self) -> Optional[QImage]:
        if self.card_logo_png:
            img = QImage.fromData(QByteArray(self.card_logo_png))
            if not img.isNull():
                return img
        p = self.store.logo_path
        if p:
            img = QImage(str(p))
            if not img.isNull():
                return img
        return None

    def build_card(self) -> FlightCard:
        card = FlightCard(values=self.values(), series=self.series, source_file=self.source_file)
        logo = self.current_logo()
        if logo is not None:
            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            logo.save(buf, "PNG")
            card.logo_png = bytes(buf.data())
        return card

    def renderer(self) -> CardRenderer:
        card = FlightCard(values=self.values(), series=self.series, source_file=self.source_file)
        return CardRenderer(card, self.print_tr, self.current_logo(), self.chk_annex.isChecked())

    def refresh_preview(self):
        page = self.page_bar.currentIndex() if self.chk_annex.isChecked() else 0
        width = max(1400, min(2600, int(self.preview.width() * self.devicePixelRatioF() * 1.2)))
        self.preview.set_image(self.renderer().render_to_image(max(0, page), width))

    # ================================================================ import
    def _start_dir(self) -> str:
        d = self.store.settings.last_dir
        return d if d and Path(d).is_dir() else str(documents_dir())

    def _remember_dir(self, path: str):
        self.store.settings.last_dir = str(Path(path).resolve().parent)

    def _filters(self, *keys: str) -> str:
        return ";;".join(self.tr_(k) for k in keys + ("filter_all",))

    def open_simulation_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr_("act_open").replace("&", ""),
                                              self._start_dir(), self._filters("filter_sim"))
        if path:
            self.open_path(path)

    def open_path(self, path: str):
        if Path(path).suffix.lower() == ".xml":
            self.load_card_file(path)
            return
        try:
            doc = parse_simulation_file(path)
        except ParseError as exc:
            msg = self.tr_(exc.key)
            if exc.detail:
                msg += f"\n\n{exc.detail}"
            QMessageBox.critical(self, self.tr_("err_title"), msg)
            return
        except Exception as exc:  # fichier inattendu : ne jamais faire planter l'appli
            QMessageBox.critical(self, self.tr_("err_title"), f"{type(exc).__name__}: {exc}")
            return
        self._remember_dir(path)
        self.doc = doc
        self.card_logo_png = None
        idx = 0
        if len(doc.simulations) > 1:
            dlg = SimulationDialog(doc.simulations, Path(path).name, self.lang.translator, self)
            if dlg.exec() != SimulationDialog.DialogCode.Accepted:
                self.doc = doc   # le fichier reste disponible pour un choix ultérieur
                self.act_reselect.setEnabled(True)
                return
            idx = dlg.selected_index()
        self.apply_simulation(idx)

    def reselect_simulation(self):
        if not self.doc or not self.doc.simulations:
            return
        dlg = SimulationDialog(self.doc.simulations, Path(self.doc.source_path).name,
                               self.lang.translator, self, current=self.sim_index)
        if dlg.exec() == SimulationDialog.DialogCode.Accepted:
            self.apply_simulation(dlg.selected_index())

    def apply_simulation(self, idx: int):
        doc = self.doc
        if doc is None:
            return
        sim = doc.simulations[idx] if doc.simulations else None
        self.sim_index = idx
        values = card_values_from_simulation(doc, sim, self.print_tr, self.print_lang)
        keys = [f.key for f in FIELDS if f.key not in KEEP_ON_IMPORT]
        self.set_values(values, keys)
        self._manual_auto.clear()
        self.series = sim.series if sim else TimeSeries()
        self.source_file = doc.source_path
        self.act_reselect.setEnabled(len(doc.simulations) > 1)
        self._update_tw_verdict()
        self._update_title()
        file_name = Path(doc.source_path).name
        if sim is None:
            self.statusBar().showMessage(self.tr_("status_no_sim"), 10000)
        else:
            self.statusBar().showMessage(self.tr_("status_loaded", file=file_name, sim=sim.name), 10000)
        if sim is not None and sim.launch_mass is None and doc.notes:
            QMessageBox.information(self, self.tr_("warn_title"),
                                    "\n\n".join(self.tr_(n) for n in doc.notes))
        self.tabs.setCurrentIndex(1)
        self.refresh_preview()

    # ================================================================ fiche XML
    def save_card_dialog(self):
        name = self.ed("rocket_name").value().strip() or "fiche"
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip() or "fiche"
        path, _ = QFileDialog.getSaveFileName(self, self.tr_("act_save_xml").replace("&", ""),
                                              str(Path(self._start_dir()) / f"{safe}.xml"),
                                              self._filters("filter_xml"))
        if not path:
            return
        if not path.lower().endswith(".xml"):
            path += ".xml"
        try:
            save_card(self.build_card(), path)
        except OSError as exc:
            QMessageBox.critical(self, self.tr_("err_title"), self.tr_("err_write", detail=str(exc)))
            return
        self._remember_dir(path)
        self._remember_current_location()
        self.statusBar().showMessage(self.tr_("status_saved", file=path), 8000)

    def load_card_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr_("act_load_xml").replace("&", ""),
                                              self._start_dir(), self._filters("filter_xml"))
        if path:
            self.load_card_file(path)

    def load_card_file(self, path: str):
        try:
            card = load_card(path)
        except (ParseError, OSError) as exc:
            QMessageBox.critical(self, self.tr_("err_title"), self.tr_("err_card_xml") + f"\n\n{exc}")
            return
        self._remember_dir(path)
        defaults = {k: "" for k in FIELD_BY_KEY}
        defaults.update(card.values)
        self.set_values(defaults, list(FIELD_BY_KEY))
        self._manual_auto.clear()
        self.series = card.series
        self.source_file = card.source_file
        self.card_logo_png = card.logo_png
        self.doc = None
        self.act_reselect.setEnabled(False)
        self._update_logo_label()
        self._update_title()
        self._update_tw_verdict()
        self.statusBar().showMessage(self.tr_("status_card_loaded", file=path), 8000)
        self.refresh_preview()

    def new_card(self):
        if QMessageBox.question(self, self.tr_("confirm_title"), self.tr_("confirm_new")) \
                != QMessageBox.StandardButton.Yes:
            return
        keep = set(PILOT_PROFILE_KEYS) | {"flight_date", "flight_location"}
        self.set_values({k: "" for k in FIELD_BY_KEY if k not in keep})
        self.doc, self.series, self.source_file, self.card_logo_png = None, TimeSeries(), "", None
        self._manual_auto.clear()
        self.act_reselect.setEnabled(False)
        self._update_logo_label()
        self._update_title()
        self._update_tw_verdict()
        self.refresh_preview()

    # ================================================================ impression
    def _make_printer(self) -> QPrinter:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        setup_printer_page(printer)
        printer.setDocName(self.ed("rocket_name").value() or __app_name__)
        return printer

    def print_preview(self):
        self._remember_current_location()
        printer = self._make_printer()
        dlg = QPrintPreviewDialog(printer, self)
        dlg.setWindowTitle(self.tr_("act_preview").replace("&", "").rstrip("…"))
        renderer = self.renderer()
        dlg.paintRequested.connect(renderer.render_to_printer)
        dlg.resize(1100, 800)
        dlg.exec()

    def print_card(self):
        self._remember_current_location()
        printer = self._make_printer()
        dlg = QPrintDialog(printer, self)
        if dlg.exec() == QPrintDialog.DialogCode.Accepted:
            try:
                self.renderer().render_to_printer(printer)
            except RuntimeError as exc:
                QMessageBox.critical(self, self.tr_("err_title"), str(exc))

    def export_pdf(self):
        name = self.ed("rocket_name").value().strip() or "flight_card"
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip()
        path, _ = QFileDialog.getSaveFileName(self, self.tr_("act_export_pdf").replace("&", ""),
                                              str(Path(self._start_dir()) / f"{safe}.pdf"),
                                              self._filters("filter_pdf"))
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            self.renderer().export_pdf(path)
        except (RuntimeError, OSError) as exc:
            QMessageBox.critical(self, self.tr_("err_title"), self.tr_("err_write", detail=str(exc)))
            return
        self._remember_dir(path)
        self._remember_current_location()
        self.statusBar().showMessage(self.tr_("status_pdf", file=path), 8000)

    # ================================================================ profil / logo
    def _load_profile_into_form(self):
        s = self.store.settings
        self.ed("flight_location").set_locations(s.locations)
        self.set_values({
            "pilot_lastname": s.pilot.lastname, "pilot_firstname": s.pilot.firstname,
            "pilot_license": s.pilot.license, "pilot_level": s.pilot.level,
            "flight_location": s.last_location,
        })

    def _store_profile(self):
        s = self.store.settings
        s.pilot.lastname = self.ed("pilot_lastname").value().strip()
        s.pilot.firstname = self.ed("pilot_firstname").value().strip()
        s.pilot.license = self.ed("pilot_license").value().strip()
        s.pilot.level = self.ed("pilot_level").value()

    def save_profile(self):
        self._store_profile()
        self._remember_current_location()
        self.statusBar().showMessage(self.tr_("status_profile_saved"), 5000)

    def _remember_current_location(self):
        place = self.ed("flight_location").value()
        if place:
            self.store.remember_location(place)
            self.ed("flight_location").set_locations(self.store.settings.locations)
        self._save_settings_quietly()

    def forget_location(self):
        place = self.ed("flight_location").value()
        self.store.forget_location(place)
        self.ed("flight_location").set_locations(self.store.settings.locations)
        self.ed("flight_location").set_value("")
        self._save_settings_quietly()
        self.schedule_preview()

    def choose_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr_("btn_choose_logo").rstrip("…"),
                                              self._start_dir(), self._filters("filter_images"))
        if not path:
            return
        if QImage(path).isNull():
            QMessageBox.warning(self, self.tr_("err_title"), self.tr_("err_logo"))
            return
        try:
            self.store.set_logo(Path(path))
        except OSError as exc:
            QMessageBox.critical(self, self.tr_("err_title"), self.tr_("err_write", detail=str(exc)))
            return
        self.card_logo_png = None
        self._save_settings_quietly()
        self._update_logo_label()
        self.refresh_preview()

    def clear_logo(self):
        self.store.set_logo(None)
        self.card_logo_png = None
        self._save_settings_quietly()
        self._update_logo_label()
        self.refresh_preview()

    def _update_logo_label(self):
        img = self.current_logo()
        if img is None:
            self.logo_label.setPixmap(QPixmap())
            self.logo_label.setText(self.tr_("no_logo"))
        else:
            pm = QPixmap.fromImage(img).scaled(self.logo_label.size() - QSize(8, 8),
                                               Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation)
            self.logo_label.setPixmap(pm)

    # ================================================================ aide
    def open_manual(self):
        path = manual_path(self.lang.language)
        if not path.is_file():
            path = manual_path("en")
        if not path.is_file():
            QMessageBox.warning(self, self.tr_("err_title"),
                                self.tr_("err_manual_missing", path=str(manual_path(self.lang.language))))
            return
        if QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            return
        try:  # repli si QDesktopServices échoue
            system = platform.system()
            if system == "Windows":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif system == "Darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except (OSError, AttributeError):
            QMessageBox.warning(self, self.tr_("err_title"), self.tr_("err_manual_open", path=str(path)))

    def about(self):
        QMessageBox.about(self, self.tr_("act_about").replace("&", "").rstrip("…"),
                          self.tr_("about_text", app=__app_name__, version=__version__,
                                   py=platform.python_version(), qt=QT_VERSION_STR,
                                   pyqt=PYQT_VERSION_STR))

    # ================================================================ glisser-déposer global
    def dragEnterEvent(self, event):
        if accepted_local_file(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        path = accepted_local_file(event.mimeData())
        if path:
            event.acceptProposedAction()
            QTimer.singleShot(0, lambda: self.open_path(path))

    # ================================================================ persistance fenêtre
    def _save_settings_quietly(self):
        try:
            self.store.save()
        except OSError as exc:
            self.statusBar().showMessage(str(exc), 8000)

    def _restore_window_state(self):
        s = self.store.settings
        if s.window_geometry:
            self.restoreGeometry(QByteArray.fromBase64(s.window_geometry.encode()))
        else:
            self.resize(1500, 900)
        if s.splitter_state:
            self.splitter.restoreState(QByteArray.fromBase64(s.splitter_state.encode()))
        else:
            self.splitter.setSizes([620, 880])
        self.page_bar.setTabEnabled(1, self.chk_annex.isChecked())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.schedule_preview()

    def closeEvent(self, event):
        self._store_profile()
        place = self.ed("flight_location").value()
        if place:
            self.store.remember_location(place)
        s = self.store.settings
        s.window_geometry = bytes(self.saveGeometry().toBase64()).decode()
        s.splitter_state = bytes(self.splitter.saveState().toBase64()).decode()
        self._save_settings_quietly()
        super().closeEvent(event)

