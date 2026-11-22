"""Schéma des champs de la fiche de vol et modèle de données de la fiche.

La fiche est stockée sous forme de dictionnaire plat « clé → valeur texte » afin que
chaque champ reste modifiable manuellement, puis sauvegardé / rechargé en XML.
Les libellés affichés sont des clés de traduction (« lbl_<clé> »).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .models import TimeSeries

# Types de champs
TEXT, MULTILINE, BOOL, CHOICE, DATE, LOCATION = (
    "text", "multiline", "bool", "choice", "date", "location")

LEVEL_CHOICES = ["", "junior", "l1", "l2", "l3"]
YESNO_CHOICES = ["", "yes", "no"]


@dataclass(frozen=True)
class FieldDef:
    key: str
    kind: str = TEXT
    group: str = ""
    choices: tuple = ()
    auto: bool = False      # valeur recalculée automatiquement (si non modifiée à la main)

    @property
    def label_key(self) -> str:
        return f"lbl_{self.key}"


def _f(key, kind=TEXT, group="", choices=(), auto=False) -> FieldDef:
    return FieldDef(key, kind, group, tuple(choices), auto)


FIELDS: list[FieldDef] = [
    # --- Pilote / vol
    _f("pilot_lastname", group="pilot"),
    _f("pilot_firstname", group="pilot"),
    _f("pilot_license", group="pilot"),
    _f("pilot_level", CHOICE, "pilot", LEVEL_CHOICES),
    _f("flight_date", DATE, "pilot"),
    _f("flight_location", LOCATION, "pilot"),
    _f("first_flight", CHOICE, "pilot", YESNO_CHOICES),
    _f("pilot_notes", MULTILINE, "pilot"),
    # --- Fusée
    _f("rocket_name", group="rocket"),
    _f("flight_level", group="rocket", auto=True),
    _f("rocket_mass_kg", group="rocket"),
    _f("rocket_dry_mass_kg", group="rocket"),
    _f("rocket_length_cm", group="rocket"),
    _f("rocket_diameter_mm", group="rocket"),
    _f("rocket_cg_cm", group="rocket"),
    _f("rocket_cp_cm", group="rocket"),
    _f("stability_cal", group="rocket", auto=True),
    _f("stage_count", group="rocket"),
    _f("sim_software", group="rocket"),
    _f("kit", BOOL, "rocket"),
    _f("kit_modified", BOOL, "rocket"),
    _f("scratch_built", BOOL, "rocket"),
    _f("model_classic", BOOL, "rocket"),
    _f("model_fantasy", BOOL, "rocket"),
    _f("model_scale", BOOL, "rocket"),
    _f("payload", MULTILINE, "rocket"),
    # --- Récupération / rampe
    _f("ejection_charge", BOOL, "recovery"),
    _f("ejection_electronic", BOOL, "recovery"),
    _f("ejection_dual", BOOL, "recovery"),
    _f("recovery_streamer", BOOL, "recovery"),
    _f("recovery_parachute", BOOL, "recovery"),
    _f("recovery_dual_parachute", BOOL, "recovery"),
    _f("recovery_other", group="recovery"),
    _f("recovery_details", MULTILINE, "recovery"),
    _f("launch_rod", BOOL, "recovery"),
    _f("launch_rail", BOOL, "recovery"),
    # --- Propulsion (tableau étages × colonnes construit à part dans l'UI)
    *[_f(f"{row}_{col}", group="motors")
      for row in ("stage1", "stage2", "cluster")
      for col in ("type", "manufacturer", "impulse")],
    _f("total_impulse", group="propulsion", auto=True),
    _f("avg_thrust_n", group="propulsion", auto=True),
    _f("thrust_weight_ratio", group="propulsion", auto=True),
    _f("motor_details", MULTILINE, "propulsion"),
    # --- Simulation
    _f("sim_name", group="simulation"),
    _f("sim_apogee_m", group="simulation"),
    _f("sim_max_velocity", group="simulation"),
    _f("sim_max_accel", group="simulation"),
    _f("sim_max_mach", group="simulation"),
    _f("sim_time_to_apogee", group="simulation"),
    _f("sim_flight_time", group="simulation"),
    _f("sim_burnout_time", group="simulation"),
    _f("sim_burnout_altitude", group="simulation"),
    _f("sim_max_thrust", group="simulation"),
    _f("sim_rail_exit_velocity", group="simulation"),
    _f("sim_deployment_velocity", group="simulation"),
    _f("sim_ground_hit_velocity", group="simulation"),
    _f("sim_optimum_delay", group="simulation"),
    _f("sim_rod_length", group="conditions"),
    _f("sim_rod_angle", group="conditions"),
    _f("sim_wind_speed", group="conditions"),
    _f("sim_launch_altitude", group="conditions"),
    _f("sim_latitude", group="conditions"),
    _f("sim_longitude", group="conditions"),
    _f("sim_temperature", group="conditions"),
    _f("sim_pressure", group="conditions"),
    _f("sim_events", MULTILINE, "simulation"),
    _f("sim_warnings", MULTILINE, "simulation"),
    _f("remarks", MULTILINE, "simulation"),
]

FIELD_BY_KEY: dict[str, FieldDef] = {f.key: f for f in FIELDS}
PILOT_PROFILE_KEYS = ("pilot_lastname", "pilot_firstname", "pilot_license", "pilot_level")


def fields_in_group(group: str) -> list[FieldDef]:
    return [f for f in FIELDS if f.group == group]


@dataclass
class FlightCard:
    values: dict[str, str] = field(default_factory=dict)
    series: TimeSeries = field(default_factory=TimeSeries)
    logo_png: Optional[bytes] = None       # logo embarqué (PNG)
    source_file: str = ""

    def get(self, key: str, default: str = "") -> str:
        return self.values.get(key, default) or default

    def flag(self, key: str) -> bool:
        return self.values.get(key, "") in ("1", "true", "True", "yes")

    def set(self, key: str, value) -> None:
        if isinstance(value, bool):
            value = "1" if value else "0"
        self.values[key] = "" if value is None else str(value)

    def update(self, values: dict) -> None:
        for k, v in values.items():
            self.set(k, v)
