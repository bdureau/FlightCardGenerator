"""Tests unitaires : python -m unittest discover -s tests"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import make_samples  # noqa: E402
from flightcard.core.card import FIELDS, FlightCard  # noqa: E402
from flightcard.core.mapping import (auto_targets, card_values_from_simulation,  # noqa: E402
                                     compute_auto_values)
from flightcard.core.rocketry import (avg_thrust_from_designation,  # noqa: E402
                                      certification_level_for_impulse,
                                      impulse_class_from_designation, thrust_to_weight_verdict,
                                      to_float)
from flightcard.i18n import Translator  # noqa: E402
from flightcard.i18n.catalog import CATALOG, LANGUAGES  # noqa: E402
from flightcard.parsers import ParseError, parse_simulation_file  # noqa: E402
from flightcard.storage.card_xml import load_card, save_card  # noqa: E402
from flightcard.storage.settings import SettingsStore  # noqa: E402

TMP = Path(tempfile.mkdtemp())
make_samples.main(TMP)
ORK = TMP / "demo_phenix.ork"
RKT = TMP / "demo_vega.rkt"


class RocketryTests(unittest.TestCase):
    def test_designation(self):
        self.assertEqual(impulse_class_from_designation("H128W-14A"), "H")
        self.assertEqual(avg_thrust_from_designation("H128W-14A"), 128.0)
        self.assertEqual(avg_thrust_from_designation("C6-5"), 6.0)
        self.assertEqual(impulse_class_from_designation("1/2A3-4T"), "1/2A")

    def test_levels_and_ratio(self):
        self.assertEqual(certification_level_for_impulse(100), "lp")
        self.assertEqual(certification_level_for_impulse(300), "l1")
        self.assertEqual(certification_level_for_impulse(2000), "l2")
        self.assertEqual(certification_level_for_impulse(9000), "l3")
        self.assertEqual(thrust_to_weight_verdict(6), "ok")
        self.assertEqual(thrust_to_weight_verdict(4), "rso")
        self.assertEqual(thrust_to_weight_verdict(2), "forbidden")
        self.assertEqual(to_float("1,25 kg"), 1.25)


class ParserTests(unittest.TestCase):
    def test_openrocket(self):
        doc = parse_simulation_file(ORK)
        self.assertEqual(doc.rocket.name, "Phénix II")
        self.assertEqual(len(doc.simulations), 3)
        self.assertAlmostEqual(doc.rocket.length, 1.07, places=3)
        self.assertAlmostEqual(doc.rocket.diameter, 0.054, places=4)
        s0, s1 = doc.simulations[:2]
        self.assertEqual(s0.motors[0].designation, "H128W-14A")
        self.assertEqual(s1.motors[0].designation, "G80T-7")
        self.assertEqual(s1.config_name, "Config. école")
        self.assertAlmostEqual(s0.launch_mass, 1.25, places=3)
        self.assertIsNotNone(s0.stability)
        self.assertGreater(s0.total_impulse, 150)
        self.assertFalse(s0.series.is_empty())
        self.assertFalse(doc.simulations[2].has_results())

    def test_plain_and_gzip_ork(self):
        import gzip
        xml = zipfile.ZipFile(ORK).read("rocket.ork")
        plain = TMP / "plain.ork"
        plain.write_bytes(xml)
        gz = TMP / "gz.ork"
        gz.write_bytes(gzip.compress(xml))
        for p in (plain, gz):
            self.assertEqual(parse_simulation_file(p).rocket.name, "Phénix II")

    def test_rocksim(self):
        doc = parse_simulation_file(RKT)
        self.assertEqual(doc.rocket.name, "Vega Mini")
        self.assertEqual(len(doc.simulations), 2)
        self.assertAlmostEqual(doc.simulations[0].max_altitude, 285.4, places=1)
        self.assertEqual(doc.simulations[0].motors[0].designation, "F39-6T")
        self.assertAlmostEqual(doc.rocket.cg, 0.412, places=3)

    def test_errors(self):
        bad = TMP / "bad.ork"
        bad.write_text("<notopenrocket/>")
        with self.assertRaises(ParseError):
            parse_simulation_file(bad)
        broken = TMP / "broken.rkt"
        broken.write_text("<RockSimDocument>")
        with self.assertRaises(ParseError):
            parse_simulation_file(broken)


class MappingTests(unittest.TestCase):
    def test_values(self):
        doc = parse_simulation_file(ORK)
        v = card_values_from_simulation(doc, doc.simulations[0], Translator("fr"), "fr")
        self.assertEqual(v["stage1_type"], "H128W-14A")
        self.assertEqual(v["rocket_mass_kg"], "1,250")
        self.assertEqual(v["flight_level"], "L1")
        self.assertEqual(v["avg_thrust_n"], "128,0")
        self.assertEqual(v["thrust_weight_ratio"], "10,44")
        self.assertEqual(v["recovery_parachute"], "1")

    def test_cluster_and_auto(self):
        v = {"stage1_type": "H128W", "cluster_type": "2 × H128W", "rocket_mass_kg": "2",
             "stage1_impulse": "200", "cluster_impulse": "400",
             "rocket_cg_cm": "60", "rocket_cp_cm": "75", "rocket_diameter_mm": "50"}
        out = compute_auto_values(v, "en")
        self.assertEqual(out["avg_thrust_n"], "384.0")
        self.assertEqual(out["total_impulse"], "600.0")
        self.assertEqual(out["flight_level"], "L1")
        self.assertEqual(out["stability_cal"], "3.00")
        self.assertEqual(auto_targets("rocket_mass_kg"), {"thrust_weight_ratio"})
        self.assertIn("flight_level", auto_targets("stage1_impulse"))


class I18nTests(unittest.TestCase):
    def test_catalog_complete(self):
        for key, entry in CATALOG.items():
            self.assertEqual(len(entry), len(LANGUAGES), key)
            for text in entry:
                self.assertTrue(text, key)

    def test_field_labels(self):
        for f in FIELDS:
            if f.group != "motors":
                self.assertIn(f.label_key, CATALOG, f.key)

    def test_keys_used_in_code_exist(self):
        pattern = re.compile(r"""(?:tr_?|tr\.tr)\(\s*["']([a-z0-9_]+)["']""")
        missing = set()
        for py in (ROOT / "flightcard").rglob("*.py"):
            for key in pattern.findall(py.read_text(encoding="utf-8")):
                if key not in CATALOG:
                    missing.add(f"{py.name}:{key}")
        self.assertFalse(missing, missing)

    def test_placeholders_consistent(self):
        for key, entry in CATALOG.items():
            ph = [sorted(re.findall(r"\{(\w+)\}", t)) for t in entry]
            self.assertTrue(all(p == ph[0] for p in ph), key)


class StorageTests(unittest.TestCase):
    def test_card_roundtrip(self):
        doc = parse_simulation_file(ORK)
        sim = doc.simulations[0]
        card = FlightCard(values=card_values_from_simulation(doc, sim, Translator("en"), "en"),
                          series=sim.series, logo_png=b"\x89PNG fake", source_file=str(ORK))
        card.values["remarks"] = "Ligne 1\nLigne 2 <&> é"
        path = TMP / "card.xml"
        save_card(card, path)
        back = load_card(path)
        self.assertEqual(back.values["remarks"], card.values["remarks"])
        self.assertEqual(back.values["rocket_name"], "Phénix II")
        self.assertEqual(back.logo_png, card.logo_png)
        self.assertEqual(len(back.series.time), len(sim.series.time))

    def test_settings(self):
        d = TMP / "settings"
        st = SettingsStore(d)
        st.settings.pilot.lastname = "Dupont"
        st.remember_location("La Courtine")
        st.remember_location("Biscarrosse")
        st.remember_location("la courtine")
        st.save()
        st2 = SettingsStore(d)
        self.assertEqual(st2.settings.pilot.lastname, "Dupont")
        self.assertEqual(st2.settings.locations, ["la courtine", "Biscarrosse"])


class RenderTests(unittest.TestCase):
    def test_render_all_languages(self):
        from PyQt6.QtWidgets import QApplication
        from flightcard.printing.renderer import CardRenderer
        app = QApplication.instance() or QApplication([])
        doc = parse_simulation_file(ORK)
        for lang in LANGUAGES:
            tr = Translator(lang)
            card = FlightCard(values=card_values_from_simulation(doc, doc.simulations[0], tr, lang),
                              series=doc.simulations[0].series)
            r = CardRenderer(card, tr)
            for page in range(r.page_count()):
                img = r.render_to_image(page, 800)
                self.assertFalse(img.isNull())
        out = TMP / "card.pdf"
        CardRenderer(card, Translator("it")).export_pdf(out)
        self.assertGreater(out.stat().st_size, 5000)
        del app


if __name__ == "__main__":
    unittest.main()
