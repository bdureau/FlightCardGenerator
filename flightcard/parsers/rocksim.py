"""Parseur des fichiers RockSim (.rkt).

Le format RockSim est un XML (racine <RockSimDocument>) non documenté publiquement.
RockSim enregistre ses grandeurs en unités internes métriques : longueurs en mm,
masses en g, vitesses en mm/s, accélérations en mm/s². Le parseur est volontairement
tolérant (noms d'éléments alternatifs, éléments absents) ; toute valeur reste
modifiable dans l'interface.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from xml.etree.ElementTree import Element

from ..core.models import (FlightEvent, MotorInfo, ParsedDocument, RecoveryDevice,
                           RocketInfo, SimulationInfo)
from ..core.rocketry import avg_thrust_from_designation
from .xmlutil import (ParseError, child, child_num, iter_local, local,
                      parse_xml_bytes, text)

MM = 0.001
G = 0.001

AXIAL = {"nosecone", "bodytube", "transition"}
MOTOR_CODE_TAGS = ("EngineCode", "MotorCode", "Designation", "EngineName", "MotorName", "Code")
MOTOR_MFG_TAGS = ("Manufacturer", "Mfg", "MfgName", "EngineMfg", "MotorManufacturer")


def _first_num(elem: Optional[Element], *names: str) -> Optional[float]:
    for n in names:
        v = child_num(elem, n)
        if v is not None:
            return v
    return None


def _first_nonzero(elem: Optional[Element], *names: str) -> Optional[float]:
    for n in names:
        v = child_num(elem, n)
        if v:
            return v
    return None


def _scale(v: Optional[float], factor: float) -> Optional[float]:
    return None if v is None else v * factor


def _part_mass_g(part: Element) -> float:
    use_known = text(part, "UseKnownMass", "MassOverride").strip() in ("1", "true", "True")
    known = child_num(part, "KnownMass")
    calc = child_num(part, "CalcMass")
    if use_known and known:
        mass = known
    else:
        mass = calc if calc is not None else (known or 0.0)
    attached = child(part, "AttachedParts")
    if attached is not None:
        for p in attached:
            mass += _part_mass_g(p)
    return mass


def _walk_recovery(part: Element, out: list[RecoveryDevice]):
    tag = local(part.tag).lower()
    if tag in ("parachute", "streamer"):
        out.append(RecoveryDevice(
            kind=tag,
            name=text(part, "Name"),
            diameter_mm=child_num(part, "Dia"),
            deploy_event="ejection",
        ))
    attached = child(part, "AttachedParts")
    if attached is not None:
        for p in attached:
            _walk_recovery(p, out)


def _motors_in(elem: Element, stage_fire_default: int = 0) -> list[MotorInfo]:
    motors: list[MotorInfo] = []
    for e in elem.iter():
        code = ""
        for t in MOTOR_CODE_TAGS:
            c = child(e, t)
            if c is not None and c.text and c.text.strip():
                code = c.text.strip()
                break
        if not code:
            continue
        mfg = text(e, *MOTOR_MFG_TAGS)
        if not mfg and local(e.tag).lower() not in (
                "engine", "motor", "simulationengine", "engineselection", "engineitem"):
            continue
        stage = child_num(e, "Stage", "StageNumber")
        imp = _first_num(e, "TotalImpulse", "TotImpulse", "Impulse")
        avg = _first_num(e, "AvgThrust", "AverageThrust")
        motors.append(MotorInfo(
            designation=code,
            manufacturer=mfg,
            stage=int(stage) - 1 if stage and stage >= 1 else stage_fire_default,
            count=int(child_num(e, "Count", "Qty", "Quantity") or 1),
            delay=_first_num(e, "Delay", "EjectionDelay"),
            diameter_mm=_first_num(e, "Dia", "Diameter"),
            length_mm=_first_num(e, "Len", "Length"),
            total_impulse=imp,
            avg_thrust=avg if avg is not None else avg_thrust_from_designation(code),
        ))
    return motors


def parse_rocksim(path: str | Path) -> ParsedDocument:
    path = Path(path)
    root = parse_xml_bytes(path.read_bytes())
    if local(root.tag).lower() != "rocksimdocument":
        raise ParseError("err_not_rocksim")

    doc = ParsedDocument(source_path=str(path))
    version = text(root, "FileVersion")
    doc.software = "RockSim" + (f" (format {version})" if version else "")

    design = next(iter_local(root, "RocketDesign"), None)
    if design is None:
        raise ParseError("err_not_rocksim")

    rocket = RocketInfo(name=text(design, "Name"), designer=text(design, "Designer"))

    stage_elems: list[tuple[int, Element]] = []
    for n in (1, 2, 3):
        st = child(design, f"Stage{n}Parts")
        if st is not None and len(st):
            stage_elems.append((n, st))
    stage_elems.sort()                       # Stage1 (booster) s'allume en premier
    rocket.stage_count = max(1, len(stage_elems))

    length = 0.0
    diameters: list[float] = []
    dry_g = 0.0
    for _, st in stage_elems:
        for part in st:
            tag = local(part.tag).lower()
            if tag in AXIAL:
                length += child_num(part, "Len") or 0.0
                for d in ("OD", "BaseDia", "FrontDia", "RearDia"):
                    v = child_num(part, d)
                    if v:
                        diameters.append(v)
            dry_g += _part_mass_g(part)
            _walk_recovery(part, rocket.recovery)
    rocket.length = length * MM if length else None
    rocket.diameter = max(diameters) * MM if diameters else None
    rocket.dry_mass = dry_g * G if dry_g else None

    rocket.cg = _scale(_first_nonzero(design, "CG", "CalcCG", "Stage3CG"), MM)
    rocket.cp = _scale(_first_nonzero(design, "CP", "CalcCP", "ProCP"), MM)
    known_mass = _first_nonzero(design, "KnownMass", "Stage3Mass", "CalcMass")
    if known_mass:
        rocket.dry_mass = known_mass * G

    rocket.motors = _motors_in(design)

    for i, res in enumerate(iter_local(root, "SimulationResults"), 1):
        sim = SimulationInfo()
        sim.name = text(res, "SimulationName", "Name", "Description", "Title") or f"Simulation {i}"
        sim.max_altitude = _scale(_first_num(res, "MaxAltitude", "Apogee"), MM)
        sim.max_velocity = _scale(_first_num(res, "MaxVelocity"), MM)
        sim.max_acceleration = _scale(_first_num(res, "MaxAcceleration"), MM)
        sim.max_mach = _first_num(res, "MaxMach", "MaxMachNumber")
        sim.time_to_apogee = _first_num(res, "TimeToApogee", "ApogeeTime")
        sim.optimum_delay = _first_num(res, "OptimalDelay", "OptimumDelay", "OptimalEjectionDelay")
        sim.flight_time = _first_num(res, "FlightTime", "TotalFlightTime")
        sim.ground_hit_velocity = _scale(_first_num(res, "GroundHitVelocity", "FinalVelocity",
                                                    "DescentVelocity"), MM)
        sim.rail_exit_velocity = _scale(_first_num(res, "LaunchGuideVelocity",
                                                   "VelocityOffGuide", "LaunchRodVelocity"), MM)
        sim.deployment_velocity = _scale(_first_num(res, "EjectionVelocity",
                                                    "DeploymentVelocity"), MM)
        sim.burnout_altitude = _scale(_first_num(res, "BurnoutAltitude"), MM)
        sim.burnout_time = _first_num(res, "BurnoutTime")
        sim.max_thrust = _first_num(res, "MaxThrust")
        sim.wind_speed = _scale(_first_num(res, "WindSpeed"), MM)
        sim.rod_length = _scale(_first_num(res, "LaunchGuideLength"), MM)
        sim.rod_angle = _first_num(res, "LaunchGuideAngle", "LaunchAngle")
        sim.launch_altitude = _scale(_first_num(res, "LaunchAltitude", "Elevation"), MM)
        sim.temperature = _first_num(res, "Temperature", "LaunchTemperature")
        sim.launch_mass = _scale(_first_nonzero(res, "LaunchMass", "LiftoffMass", "TotalMass"), G)
        sim.cg = _scale(_first_nonzero(res, "CG", "LaunchCG"), MM)
        sim.cp = _scale(_first_nonzero(res, "CP", "LaunchCP"), MM)
        sim.stability = _first_num(res, "StabilityMargin", "Stability")
        sim.motors = _motors_in(res) or list(rocket.motors)
        for ev in iter_local(res, "SimulationEvent", "Event"):
            t = _first_num(ev, "Time", "EventTime")
            kind = text(ev, "Type", "EventType", "Name").lower().replace(" ", "")
            if t is not None and kind:
                sim.events.append(FlightEvent(time=t, kind=kind))
        sim.events.sort(key=lambda e: e.time)
        doc.simulations.append(sim)

    if not rocket.motors and doc.simulations:
        rocket.motors = list(doc.simulations[0].motors)
    doc.rocket = rocket
    return doc

