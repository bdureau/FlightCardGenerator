"""Parseur des fichiers OpenRocket (.ork).

Un fichier .ork est normalement une archive ZIP contenant un document XML
(« rocket.ork »). Les anciennes versions produisaient du XML compressé GZIP ou du
XML brut : les trois variantes sont acceptées.

Toutes les grandeurs OpenRocket sont stockées en unités SI (m, kg, s, m/s).
"""
from __future__ import annotations

import gzip
import io
import re
import zipfile
from pathlib import Path
from typing import Optional
from xml.etree.ElementTree import Element

from ..core.models import (FlightEvent, MotorInfo, ParsedDocument, RecoveryDevice,
                           RocketInfo, SimulationInfo, TimeSeries)
from .xmlutil import (ParseError, child, child_num, children, iter_local, local, num,
                      parse_xml_bytes, text)

MAX_XML_BYTES = 300 * 1024 * 1024   # garde-fou contre les archives piégées

AXIAL_COMPONENTS = {"nosecone", "bodytube", "transition"}

# Noms de colonnes possibles des données de vol (OpenRocket peut les enregistrer
# dans la langue de son interface).
COLUMN_SYNONYMS = {
    "time": ["time", "temps", "tiempo", "tempo", "zeit"],
    "altitude": ["altitude", "altitud", "höhe", "altezza"],
    "vvel": ["vertical velocity", "vitesse verticale", "velocidad vertical",
             "velocità verticale", "vertikalgeschwindigkeit"],
    "tvel": ["total velocity", "vitesse totale", "velocidad total", "velocità totale",
             "gesamtgeschwindigkeit"],
    "mass": ["mass", "total mass", "masse", "masse totale", "masa", "masa total", "massa",
             "massa totale", "gesamtmasse"],
    "cg": ["cg location", "position du cg", "emplacement du cg", "position cg",
           "ubicación del cg", "posición del cg", "posizione del cg", "posizione cg",
           "cg-position", "schwerpunkt"],
    "cp": ["cp location", "position du cp", "emplacement du cp", "position cp",
           "ubicación del cp", "posición del cp", "posizione del cp", "posizione cp",
           "cp-position", "druckpunkt"],
    "stability": ["stability margin calibers", "stability margin (calibers)",
                  "marge de stabilité en calibres", "marge de stabilité (calibres)",
                  "margen de estabilidad en calibres", "margine di stabilità in calibri",
                  "stabilitätsreserve in kaliber"],
    "thrust": ["thrust", "poussée", "empuje", "spinta", "schub"],
}


def _read_ork_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                names = zf.namelist()
                member = None
                for candidate in ("rocket.ork",):
                    if candidate in names:
                        member = candidate
                if member is None:
                    xmls = [n for n in names if n.lower().endswith((".ork", ".xml"))
                            and not n.endswith("/")]
                    member = xmls[0] if xmls else None
                if member is None:
                    raise ParseError("err_ork_no_xml")
                info = zf.getinfo(member)
                if info.file_size > MAX_XML_BYTES:
                    raise ParseError("err_file_too_large")
                with zf.open(member) as fh:
                    return fh.read(MAX_XML_BYTES + 1)[:MAX_XML_BYTES]
        except zipfile.BadZipFile as exc:
            raise ParseError("err_bad_archive", str(exc)) from exc
    if raw[:2] == b"\x1f\x8b":
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as gz:
                data = gz.read(MAX_XML_BYTES + 1)
        except OSError as exc:
            raise ParseError("err_bad_archive", str(exc)) from exc
        if len(data) > MAX_XML_BYTES:
            raise ParseError("err_file_too_large")
        return data
    return raw


def _cluster_count(config: str) -> int:
    c = (config or "").strip().lower()
    if not c or c == "single":
        return 1
    if c == "double":
        return 2
    m = re.match(r"(\d+)", c)
    return int(m.group(1)) if m else 1


class _Collector:
    """Parcours récursif de l'arbre de composants."""

    def __init__(self):
        self.mounts: list[tuple[int, int, Element]] = []   # (étage OR, cluster, motormount)
        self.recovery: list[RecoveryDevice] = []

    def walk(self, comp: Element, stage_idx: int):
        tag = local(comp.tag).lower()
        if tag in ("parachute", "streamer"):
            ev = text(comp, "deployevent").lower()
            dev = RecoveryDevice(
                kind=tag,
                name=text(comp, "name"),
                diameter_mm=_mm(child_num(comp, "diameter")),
                deploy_event=ev,
                deploy_altitude=child_num(comp, "deployaltitude"),
            )
            self.recovery.append(dev)
        mm = child(comp, "motormount")
        if mm is not None:
            count = _cluster_count(text(comp, "clusterconfiguration"))
            self.mounts.append((stage_idx, count, mm))
        sub = child(comp, "subcomponents")
        if sub is not None:
            for c in sub:
                self.walk(c, stage_idx)


def _mm(v: Optional[float]) -> Optional[float]:
    return None if v is None else v * 1000.0


def _motor_from_elem(m: Element, stage_fire: int, count: int) -> MotorInfo:
    delay_txt = text(m, "delay").lower()
    return MotorInfo(
        designation=text(m, "designation"),
        manufacturer=text(m, "manufacturer"),
        stage=stage_fire,
        count=count,
        delay=None if delay_txt in ("", "none", "plugged") else num(delay_txt),
        diameter_mm=_mm(child_num(m, "diameter")),
        length_mm=_mm(child_num(m, "length")),
    )


def _merge_motors(motors: list[MotorInfo]) -> list[MotorInfo]:
    merged: dict[tuple, MotorInfo] = {}
    for m in motors:
        key = (m.stage, m.designation, m.manufacturer, m.delay)
        if key in merged:
            merged[key].count += m.count
        else:
            merged[key] = MotorInfo(**m.__dict__)
    return sorted(merged.values(), key=lambda x: (x.stage, x.designation))


def _norm_event(kind: str) -> str:
    return re.sub(r"[\s_\-]", "", (kind or "").lower())


def _find_column(types: list[str], key: str) -> Optional[int]:
    lowered = [t.strip().lower() for t in types]
    syns = COLUMN_SYNONYMS[key]
    for s in syns:
        if s in lowered:
            return lowered.index(s)
    if key == "stability":
        for i, t in enumerate(lowered):
            if "stabil" in t and ("calib" in t or "kaliber" in t):
                return i
    return None


def _value_at(times: list[float], values: list[Optional[float]], t: float) -> Optional[float]:
    best, best_dt = None, None
    for ti, vi in zip(times, values):
        if vi is None:
            continue
        dt = abs(ti - t)
        if best_dt is None or dt < best_dt:
            best, best_dt = vi, dt
    return best


def _first(values: list[Optional[float]]) -> Optional[float]:
    for v in values:
        if v is not None:
            return v
    return None


def _parse_flightdata(fd: Element, sim: SimulationInfo):
    a = {k.lower(): v for k, v in fd.attrib.items()}
    sim.max_altitude = num(a.get("maxaltitude"))
    sim.max_velocity = num(a.get("maxvelocity"))
    sim.max_acceleration = num(a.get("maxacceleration"))
    sim.max_mach = num(a.get("maxmach"))
    sim.time_to_apogee = num(a.get("timetoapogee"))
    sim.flight_time = num(a.get("flighttime"))
    sim.ground_hit_velocity = num(a.get("groundhitvelocity"))
    sim.rail_exit_velocity = num(a.get("launchrodvelocity"))
    sim.deployment_velocity = num(a.get("deploymentvelocity"))
    sim.optimum_delay = num(a.get("optimumdelay"))

    for w in children(fd, "warning"):
        desc = child(w, "description")
        msg = (desc.text if desc is not None and desc.text else " ".join(w.itertext())).strip()
        if msg and msg not in sim.warnings:
            sim.warnings.append(msg)

    branches = children(fd, "databranch")
    if not branches:
        return
    br = branches[0]
    for ev in children(br, "event"):
        t = num(ev.get("time"))
        if t is not None:
            sim.events.append(FlightEvent(time=t, kind=_norm_event(ev.get("type", ""))))
    sim.events.sort(key=lambda e: e.time)

    types = [t.strip() for t in br.get("types", "").split(",")]
    rows: list[list[Optional[float]]] = []
    for dp in children(br, "datapoint"):
        if dp.text:
            rows.append([num(v) for v in dp.text.split(",")])
    if not rows or not types:
        return

    def col(key: str) -> list[Optional[float]]:
        i = _find_column(types, key)
        if i is None:
            return []
        return [r[i] if i < len(r) else None for r in rows]

    time = col("time")
    if not time or any(t is None for t in time):
        return
    times = [float(t) for t in time]  # type: ignore[arg-type]
    alt, vv, tv = col("altitude"), col("vvel"), col("tvel")
    mass, cg, cp, stab, thrust = col("mass"), col("cg"), col("cp"), col("stability"), col("thrust")

    rod_t = next((e.time for e in sim.events if e.kind == "launchrod"), None)
    burn_t = next((e.time for e in sim.events if e.kind == "burnout"), None)
    sim.burnout_time = burn_t

    if mass:
        sim.launch_mass = _first(mass)
        if burn_t is not None:
            sim.burnout_mass = _value_at(times, mass, burn_t)
    if cg:
        sim.cg = _first(cg)
    if cp:
        sim.cp = _value_at(times, cp, rod_t) if rod_t is not None else None
        sim.cp = sim.cp if sim.cp is not None else _first(cp)
    if stab:
        sim.stability = _value_at(times, stab, rod_t) if rod_t is not None else None
        sim.stability = sim.stability if sim.stability is not None else _first(stab)
    if alt and burn_t is not None:
        sim.burnout_altitude = _value_at(times, alt, burn_t)

    if thrust:
        pts = [(t, f) for t, f in zip(times, thrust) if f is not None]
        if pts:
            sim.max_thrust = max(f for _, f in pts)
        burning = [(t, f) for t, f in pts if f > 0]
        if len(burning) >= 10:   # échantillonnage suffisant pour intégrer
            impulse = 0.0
            for (t0, f0), (t1, f1) in zip(pts, pts[1:]):
                impulse += 0.5 * (f0 + f1) * (t1 - t0)
            duration = burning[-1][0] - burning[0][0]
            sim.total_impulse = impulse
            if duration > 0:
                sim.avg_thrust = impulse / duration

    vel = tv if tv and any(v is not None for v in tv) else vv
    if alt:
        series = TimeSeries(
            time=times,
            altitude=[v if v is not None else 0.0 for v in alt],
            velocity=[v if v is not None else 0.0 for v in vel] if vel else [],
        )
        sim.series = series.downsample(400)


def parse_openrocket(path: str | Path) -> ParsedDocument:
    path = Path(path)
    root = parse_xml_bytes(_read_ork_bytes(path))
    if local(root.tag).lower() != "openrocket":
        raise ParseError("err_not_openrocket")

    doc = ParsedDocument(source_path=str(path))
    creator = root.get("creator", "").strip()
    doc.software = creator or f"OpenRocket (format {root.get('version', '?')})"

    rocket_el = child(root, "rocket")
    if rocket_el is None:
        raise ParseError("err_not_openrocket")
    rocket = RocketInfo(name=text(rocket_el, "name"), designer=text(rocket_el, "designer"))

    stages = children(child(rocket_el, "subcomponents"), "stage")
    rocket.stage_count = max(1, len(stages))
    n = rocket.stage_count

    length = 0.0
    radii: list[float] = []
    collector = _Collector()
    for si, st in enumerate(stages):
        sub = child(st, "subcomponents")
        if sub is None:
            continue
        for comp in sub:
            tag = local(comp.tag).lower()
            if tag in AXIAL_COMPONENTS:
                length += child_num(comp, "length") or 0.0
                for rname in ("radius", "outerradius", "aftradius", "foreradius"):
                    r = child_num(comp, rname)
                    if r:
                        radii.append(r)
            collector.walk(comp, n - 1 - si)   # 0 = étage qui s'allume en premier
    rocket.length = length or None
    rocket.diameter = 2 * max(radii) if radii else None
    rocket.recovery = collector.recovery

    # Configurations moteur
    default_cfg = ""
    config_names: dict[str, str] = {}
    for mc in children(rocket_el, "motorconfiguration"):
        cid = mc.get("configid", "")
        config_names[cid] = text(mc, "name")
        if mc.get("default", "").lower() == "true":
            default_cfg = cid

    def motors_for(config_id: str) -> list[MotorInfo]:
        result = []
        for stage_fire, count, mm in collector.mounts:
            motors = children(mm, "motor")
            chosen = [m for m in motors if m.get("configid", "") == config_id]
            if not chosen and not config_id and motors:
                chosen = motors[:1]
            for m in chosen:
                result.append(_motor_from_elem(m, stage_fire, count))
        return _merge_motors(result)

    if not default_cfg and config_names:
        default_cfg = next(iter(config_names))
    rocket.motors = motors_for(default_cfg)

    # Simulations
    for i, sim_el in enumerate(children(child(root, "simulations"), "simulation"), 1):
        sim = SimulationInfo(name=text(sim_el, "name") or f"Simulation {i}",
                             status=sim_el.get("status", ""))
        cond = child(sim_el, "conditions")
        if cond is not None:
            sim.config_id = text(cond, "configid")
            sim.rod_length = child_num(cond, "launchrodlength")
            sim.rod_angle = child_num(cond, "launchrodangle")
            sim.launch_altitude = child_num(cond, "launchaltitude")
            sim.latitude = child_num(cond, "launchlatitude")
            sim.longitude = child_num(cond, "launchlongitude")
            wind = next(iter_local(cond, "windaverage"), None)
            if wind is None:
                w = child(cond, "wind")
                wind = child(w, "speed", "average", "windaverage") if w is not None else None
            sim.wind_speed = num(wind.text) if wind is not None else None
            atm = child(cond, "atmosphere")
            if atm is not None:
                t_k = child_num(atm, "basetemperature")
                p_pa = child_num(atm, "basepressure")
                sim.temperature = t_k - 273.15 if t_k is not None else None
                sim.pressure = p_pa / 100.0 if p_pa is not None else None
        cfg = sim.config_id or default_cfg
        sim.config_name = config_names.get(cfg, "")
        sim.motors = motors_for(cfg)
        fd = child(sim_el, "flightdata")
        if fd is not None:
            _parse_flightdata(fd, sim)
        doc.simulations.append(sim)

    if doc.simulations and not any(s.launch_mass for s in doc.simulations):
        doc.notes.append("note_ork_no_data")
    doc.rocket = rocket
    return doc
