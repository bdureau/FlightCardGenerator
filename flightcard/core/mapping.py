"""Conversion ParsedDocument + simulation choisie → valeurs des champs de la fiche,
et calcul des champs automatiques (impulsion totale, rapport poussée/poids, ...)."""
from __future__ import annotations

import re
from typing import Callable, Optional

from .models import MotorInfo, ParsedDocument, SimulationInfo
from .rocketry import (avg_thrust_from_designation, certification_level_for_impulse,
                       thrust_to_weight, to_float)

Translate = Callable[[str], str]

COMMA_LANGS = {"fr", "es", "it", "de"}
_COUNT_PREFIX = re.compile(r"^\s*(\d+)\s*[×xX*]\s*")


def fmt(value: Optional[float], decimals: int = 2, lang: str = "en") -> str:
    if value is None:
        return ""
    s = f"{value:.{decimals}f}"
    return s.replace(".", ",") if lang in COMMA_LANGS else s


def _motor_label(m: MotorInfo, count: Optional[int] = None) -> str:
    n = m.count if count is None else count
    d = m.designation or "?"
    return f"{n} × {d}" if n > 1 else d


def _unit_impulse(m: MotorInfo, sim: SimulationInfo, all_motors: list[MotorInfo]) -> Optional[float]:
    if m.total_impulse:
        return m.total_impulse
    designations = {x.designation for x in all_motors}
    total_count = sum(x.count for x in all_motors)
    if sim.total_impulse and len(designations) == 1 and total_count:
        return sim.total_impulse / total_count
    return None


def motor_rows(sim: SimulationInfo, lang: str) -> dict[str, str]:
    """Répartit les moteurs dans les lignes 1er étage / 2e étage / cluster."""
    v: dict[str, str] = {}
    motors = sorted(sim.motors, key=lambda m: (m.stage, -m.count))
    first = [m for m in motors if m.stage == 0]
    upper = [m for m in motors if m.stage >= 1]

    def put(row: str, label: str, mfg: str, impulse: Optional[float]):
        v[f"{row}_type"] = label
        v[f"{row}_manufacturer"] = mfg
        v[f"{row}_impulse"] = fmt(impulse, 1, lang)

    if first:
        main = first[0]
        imp = _unit_impulse(main, sim, motors)
        put("stage1", _motor_label(main, 1), main.manufacturer, imp)
        extras: list[tuple[MotorInfo, int]] = []
        if main.count > 1:
            extras.append((main, main.count - 1))
        extras += [(m, m.count) for m in first[1:]]
        if extras:
            labels = " + ".join(_motor_label(m, n) for m, n in extras)
            mfgs = " / ".join(sorted({m.manufacturer for m, _ in extras if m.manufacturer}))
            imps = [(_unit_impulse(m, sim, motors), n) for m, n in extras]
            total = sum(i * n for i, n in imps) if all(i for i, _ in imps) else None
            put("cluster", labels, mfgs, total)
    if upper:
        labels = " + ".join(_motor_label(m) for m in upper)
        mfgs = " / ".join(sorted({m.manufacturer for m in upper if m.manufacturer}))
        imps = [(_unit_impulse(m, sim, motors), m.count) for m in upper]
        total = sum(i * n for i, n in imps) if all(i for i, _ in imps) else None
        put("stage2", labels, mfgs, total)
    return v


def _event_lines(sim: SimulationInfo, tr: Translate, lang: str) -> str:
    lines = []
    for e in sim.events:
        key = f"ev_{e.kind}"
        name = tr(key)
        if name == key:
            name = e.kind
        lines.append(f"t = {fmt(e.time, 2, lang)} s — {name}")
    return "\n".join(lines)


def card_values_from_simulation(doc: ParsedDocument, sim: Optional[SimulationInfo],
                                tr: Translate, lang: str) -> dict[str, str]:
    """Construit les valeurs pré-remplies (seuls les champs issus de la simulation)."""
    r = doc.rocket
    sim = sim or SimulationInfo(motors=list(r.motors))
    v: dict[str, str] = {}

    v["rocket_name"] = r.name
    v["sim_software"] = doc.software
    v["stage_count"] = str(r.stage_count)
    mass = sim.launch_mass or r.mass
    v["rocket_mass_kg"] = fmt(mass, 3, lang)
    v["rocket_dry_mass_kg"] = fmt(r.dry_mass or sim.burnout_mass, 3, lang)
    v["rocket_length_cm"] = fmt(r.length * 100 if r.length else None, 1, lang)
    v["rocket_diameter_mm"] = fmt(r.diameter * 1000 if r.diameter else None, 1, lang)
    cg = sim.cg or r.cg
    cp = sim.cp or r.cp
    v["rocket_cg_cm"] = fmt(cg * 100 if cg else None, 1, lang)
    v["rocket_cp_cm"] = fmt(cp * 100 if cp else None, 1, lang)
    stab = sim.stability
    if stab is None and cg and cp and r.diameter:
        stab = (cp - cg) / r.diameter
    v["stability_cal"] = fmt(stab, 2, lang)

    # Propulsion
    for row in ("stage1", "stage2", "cluster"):
        for col in ("type", "manufacturer", "impulse"):
            v[f"{row}_{col}"] = ""
    v.update(motor_rows(sim, lang))
    v["total_impulse"] = fmt(sim.total_impulse, 1, lang)
    first_stage = [m for m in sim.motors if m.stage == 0]
    thrust = None
    if first_stage:
        parts = [(m.avg_thrust or avg_thrust_from_designation(m.designation), m.count)
                 for m in first_stage]
        if all(t for t, _ in parts):
            thrust = sum(t * n for t, n in parts)
    thrust = thrust or sim.avg_thrust
    v["avg_thrust_n"] = fmt(thrust, 1, lang)
    v["thrust_weight_ratio"] = fmt(thrust_to_weight(thrust, mass), 2, lang)
    details = []
    for m in sorted(sim.motors, key=lambda m: m.stage):
        bits = [f"{tr('stage_n').format(n=m.stage + 1)}: {_motor_label(m)}"]
        if m.manufacturer:
            bits.append(m.manufacturer)
        if m.diameter_mm:
            bits.append(f"Ø {fmt(m.diameter_mm, 0, lang)} mm")
        if m.length_mm:
            bits.append(f"L {fmt(m.length_mm, 0, lang)} mm")
        if m.delay is not None:
            bits.append(f"{tr('delay')} {fmt(m.delay, 1, lang)} s")
        details.append(" — ".join(bits))
    v["motor_details"] = "\n".join(details)

    # Récupération
    events = {d.deploy_event for d in r.recovery}
    chutes = [d for d in r.recovery if d.kind == "parachute"]
    streamers = [d for d in r.recovery if d.kind == "streamer"]
    has_charge = any("ejection" in e for e in events) or (
        not events and bool(r.recovery))
    has_elec = any(e and "ejection" not in e and e != "never" for e in events)
    v["ejection_charge"] = "1" if has_charge else "0"
    v["ejection_electronic"] = "1" if has_elec else "0"
    v["ejection_dual"] = "1" if len({e for e in events if e and e != "never"}) >= 2 else "0"
    v["recovery_streamer"] = "1" if streamers else "0"
    v["recovery_parachute"] = "1" if chutes else "0"
    v["recovery_dual_parachute"] = "1" if len(chutes) >= 2 else "0"
    rec_lines = []
    for d in r.recovery:
        line = f"{tr('lbl_recovery_streamer' if d.kind == 'streamer' else 'lbl_recovery_parachute')}"
        if d.name:
            line += f" « {d.name} »"
        if d.diameter_mm:
            line += f" Ø {fmt(d.diameter_mm, 0, lang)} mm"
        if d.deploy_event:
            ev_name = tr(f"deploy_{d.deploy_event}")
            if ev_name == f"deploy_{d.deploy_event}":
                ev_name = d.deploy_event
            line += f" — {ev_name}"
            if d.deploy_event == "altitude" and d.deploy_altitude:
                line += f" {fmt(d.deploy_altitude, 0, lang)} m"
        rec_lines.append(line)
    v["recovery_details"] = "\n".join(rec_lines)

    # Résultats de simulation
    label = sim.name
    if sim.config_name:
        label += f" ({sim.config_name})"
    v["sim_name"] = label
    v["sim_apogee_m"] = fmt(sim.max_altitude, 0, lang)
    v["sim_max_velocity"] = fmt(sim.max_velocity, 1, lang)
    v["sim_max_accel"] = fmt(sim.max_acceleration, 1, lang)
    v["sim_max_mach"] = fmt(sim.max_mach, 3, lang)
    v["sim_time_to_apogee"] = fmt(sim.time_to_apogee, 2, lang)
    v["sim_flight_time"] = fmt(sim.flight_time, 1, lang)
    v["sim_burnout_time"] = fmt(sim.burnout_time, 2, lang)
    v["sim_burnout_altitude"] = fmt(sim.burnout_altitude, 0, lang)
    v["sim_max_thrust"] = fmt(sim.max_thrust, 1, lang)
    v["sim_rail_exit_velocity"] = fmt(sim.rail_exit_velocity, 1, lang)
    v["sim_deployment_velocity"] = fmt(sim.deployment_velocity, 1, lang)
    v["sim_ground_hit_velocity"] = fmt(sim.ground_hit_velocity, 1, lang)
    v["sim_optimum_delay"] = fmt(sim.optimum_delay, 1, lang)
    v["sim_rod_length"] = fmt(sim.rod_length, 2, lang)
    v["sim_rod_angle"] = fmt(sim.rod_angle, 1, lang)
    v["sim_wind_speed"] = fmt(sim.wind_speed, 1, lang)
    v["sim_launch_altitude"] = fmt(sim.launch_altitude, 0, lang)
    v["sim_latitude"] = fmt(sim.latitude, 4, lang)
    v["sim_longitude"] = fmt(sim.longitude, 4, lang)
    v["sim_temperature"] = fmt(sim.temperature, 1, lang)
    v["sim_pressure"] = fmt(sim.pressure, 1, lang)
    v["sim_events"] = _event_lines(sim, tr, lang)
    v["sim_warnings"] = "\n".join(sim.warnings)

    v.update(compute_auto_values(v, lang, only_missing=True))
    return v


# ----------------------------------------------------------------- champs auto

# Champ automatique → champs dont il dépend
AUTO_DEPENDENCIES: dict[str, set[str]] = {
    "total_impulse": {"stage1_impulse", "stage2_impulse", "cluster_impulse"},
    "flight_level": {"total_impulse", "stage1_impulse", "stage2_impulse", "cluster_impulse"},
    "avg_thrust_n": {"stage1_type", "cluster_type"},
    "thrust_weight_ratio": {"avg_thrust_n", "rocket_mass_kg", "stage1_type", "cluster_type"},
    "stability_cal": {"rocket_cg_cm", "rocket_cp_cm", "rocket_diameter_mm"},
}


def auto_targets(changed: str) -> set[str]:
    """Champs automatiques impactés (transitivement) par la modification de ``changed``."""
    targets: set[str] = set()
    frontier = {changed}
    while frontier:
        new = {k for k, deps in AUTO_DEPENDENCIES.items() if deps & frontier} - targets
        targets |= new
        frontier = new
    return targets


def _thrust_of_cell(text: str) -> Optional[float]:
    """« 2 × H128W + F40 » → 2*128 + 40."""
    if not text.strip():
        return 0.0
    total = 0.0
    for part in text.split("+"):
        part = part.strip()
        if not part:
            continue
        count = 1
        m = _COUNT_PREFIX.match(part)
        if m:
            count = int(m.group(1))
            part = part[m.end():]
        t = avg_thrust_from_designation(part)
        if t is None:
            return None
        total += t * count
    return total


def compute_auto_values(v: dict[str, str], lang: str, only_missing: bool = False,
                        keep: frozenset | set = frozenset()) -> dict[str, str]:
    """Calcule les champs dérivés à partir des autres valeurs (saisies utilisateur incluses).

    ``keep`` : champs automatiques à ne pas recalculer (leur valeur actuelle est utilisée).
    ``only_missing`` : ne calcule que les champs vides."""
    out: dict[str, str] = {}

    def want(key: str) -> bool:
        if key in keep:
            return False
        return not only_missing or not v.get(key, "").strip()

    imps = [to_float(v.get(f"{r}_impulse")) for r in ("stage1", "stage2", "cluster")]
    known = [i for i in imps if i is not None]
    total = sum(known) if known and "total_impulse" not in keep else to_float(v.get("total_impulse"))
    if known and want("total_impulse"):
        out["total_impulse"] = fmt(total, 1, lang)

    level = certification_level_for_impulse(total)
    if want("flight_level"):
        out["flight_level"] = {"lp": "≤ G", "l1": "L1", "l2": "L2", "l3": "L3"}.get(level, "")

    thrust = None
    t1 = _thrust_of_cell(v.get("stage1_type", ""))
    tc = _thrust_of_cell(v.get("cluster_type", ""))
    if t1 is not None and tc is not None and (t1 or tc):
        thrust = t1 + tc
    if thrust is not None and want("avg_thrust_n"):
        out["avg_thrust_n"] = fmt(thrust, 1, lang)
    thrust = to_float(out.get("avg_thrust_n", v.get("avg_thrust_n")))
    mass = to_float(v.get("rocket_mass_kg"))
    ratio = thrust_to_weight(thrust, mass)
    if ratio is not None and want("thrust_weight_ratio"):
        out["thrust_weight_ratio"] = fmt(ratio, 2, lang)

    cg, cp, dia = (to_float(v.get(k)) for k in ("rocket_cg_cm", "rocket_cp_cm", "rocket_diameter_mm"))
    if cg is not None and cp is not None and dia and want("stability_cal"):
        out["stability_cal"] = fmt((cp - cg) / (dia / 10.0), 2, lang)
    return out
