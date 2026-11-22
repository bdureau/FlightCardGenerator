"""Structures de données neutres (indépendantes de Qt) produites par les parseurs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MotorInfo:
    """Un moteur (ou un groupe de moteurs identiques en cluster) monté dans un étage."""
    designation: str = ""
    manufacturer: str = ""
    stage: int = 0               # 0 = premier étage allumé (booster)
    count: int = 1               # nombre de moteurs identiques (cluster)
    delay: Optional[float] = None          # retard d'éjection (s)
    diameter_mm: Optional[float] = None
    length_mm: Optional[float] = None
    total_impulse: Optional[float] = None  # Ns (pour UN moteur)
    avg_thrust: Optional[float] = None     # N  (pour UN moteur)

    @property
    def impulse_class(self) -> str:
        from .rocketry import impulse_class_from_designation
        return impulse_class_from_designation(self.designation)


@dataclass
class RecoveryDevice:
    kind: str = "parachute"      # "parachute" | "streamer"
    name: str = ""
    diameter_mm: Optional[float] = None
    deploy_event: str = ""       # "ejection", "apogee", "altitude", ...
    deploy_altitude: Optional[float] = None


@dataclass
class FlightEvent:
    time: float
    kind: str                    # identifiant normalisé (launch, burnout, apogee, ...)


@dataclass
class TimeSeries:
    """Séries temporelles réduites utilisées pour le graphique de l'annexe."""
    time: list[float] = field(default_factory=list)
    altitude: list[float] = field(default_factory=list)
    velocity: list[float] = field(default_factory=list)

    def is_empty(self) -> bool:
        return len(self.time) < 2

    def downsample(self, max_points: int = 400) -> "TimeSeries":
        n = len(self.time)
        if n <= max_points:
            return self
        step = n / max_points
        idx = sorted({int(i * step) for i in range(max_points)} | {n - 1})

        def pick(values: list[float]) -> list[float]:
            return [values[i] for i in idx] if len(values) == n else []

        return TimeSeries(pick(self.time), pick(self.altitude), pick(self.velocity))


@dataclass
class SimulationInfo:
    name: str = ""
    status: str = ""
    config_id: str = ""
    config_name: str = ""
    motors: list[MotorInfo] = field(default_factory=list)
    # Résultats (SI)
    max_altitude: Optional[float] = None
    max_velocity: Optional[float] = None
    max_acceleration: Optional[float] = None
    max_mach: Optional[float] = None
    time_to_apogee: Optional[float] = None
    flight_time: Optional[float] = None
    ground_hit_velocity: Optional[float] = None
    rail_exit_velocity: Optional[float] = None
    deployment_velocity: Optional[float] = None
    optimum_delay: Optional[float] = None
    burnout_time: Optional[float] = None
    burnout_altitude: Optional[float] = None
    max_thrust: Optional[float] = None
    # Valeurs au décollage tirées des données de vol
    launch_mass: Optional[float] = None       # kg
    burnout_mass: Optional[float] = None      # kg
    cg: Optional[float] = None                # m depuis la pointe
    cp: Optional[float] = None                # m depuis la pointe
    stability: Optional[float] = None         # calibres
    total_impulse: Optional[float] = None     # Ns (intégré sur la courbe de poussée)
    avg_thrust: Optional[float] = None        # N
    # Conditions
    rod_length: Optional[float] = None        # m
    rod_angle: Optional[float] = None         # degrés
    wind_speed: Optional[float] = None        # m/s
    launch_altitude: Optional[float] = None   # m
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    temperature: Optional[float] = None       # °C
    pressure: Optional[float] = None          # hPa
    events: list[FlightEvent] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    series: TimeSeries = field(default_factory=TimeSeries)

    def has_results(self) -> bool:
        return self.max_altitude is not None

    def motor_summary(self) -> str:
        parts = []
        for m in sorted(self.motors, key=lambda m: m.stage):
            label = m.designation or "?"
            parts.append(f"{m.count}×{label}" if m.count > 1 else label)
        return " + ".join(parts)


@dataclass
class RocketInfo:
    name: str = ""
    designer: str = ""
    length: Optional[float] = None            # m
    diameter: Optional[float] = None          # m (diamètre de référence)
    dry_mass: Optional[float] = None          # kg sans moteur
    mass: Optional[float] = None              # kg au décollage (si connue)
    cg: Optional[float] = None                # m depuis la pointe
    cp: Optional[float] = None                # m depuis la pointe
    stage_count: int = 1
    recovery: list[RecoveryDevice] = field(default_factory=list)
    motors: list[MotorInfo] = field(default_factory=list)   # moteurs de la config. par défaut


@dataclass
class ParsedDocument:
    source_path: str = ""
    software: str = ""                        # ex. « OpenRocket 23.09 »
    rocket: RocketInfo = field(default_factory=RocketInfo)
    simulations: list[SimulationInfo] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)   # avertissements du parseur (clés i18n)
