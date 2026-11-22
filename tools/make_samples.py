"""Génère des fichiers d'exemple (OpenRocket .ork et RockSim .rkt) pour les tests
et la démonstration. Usage : python tools/make_samples.py [dossier_de_sortie]"""
from __future__ import annotations

import math
import sys
import zipfile
from pathlib import Path


def simulate(avg_thrust: float, burn: float, m0: float, prop: float, cd_area: float,
             dt: float = 0.05):
    """Mini simulation 1D (pour produire des données de vol plausibles)."""
    t, h, v = 0.0, 0.0, 0.0
    rows, events = [], [(0.0, "launch"), (0.0, "ignition"), (0.0, "liftoff")]
    apogee_done = rod_done = False
    while True:
        thrust = avg_thrust * (1.25 if t < burn * 0.2 else 0.94) if t < burn else 0.0
        m = m0 - prop * min(t, burn) / burn
        rho = 1.225 * math.exp(-h / 8500)
        drag = 0.5 * rho * v * abs(v) * (cd_area if not apogee_done else cd_area * 60)
        a = (thrust - drag) / m - 9.81
        if t == 0 and a < 0:
            a = 0.0
        cg = 0.62 - 0.03 * min(t, burn) / burn
        cp = 0.80
        stab = (cp - cg) / 0.054
        rows.append([t, h, v, a, m, cg, cp, stab, thrust, abs(v) / 340.0])
        v += a * dt
        h += v * dt
        t += dt
        if not rod_done and h >= 1.5:
            events.append((t, "launchrod"))
            rod_done = True
        if t >= burn and not any(e[1] == "burnout" for e in events):
            events.append((t, "burnout"))
        if not apogee_done and v < 0 and t > burn:
            events.append((t, "apogee"))
            events.append((t, "recoverydevicedeployment"))
            apogee_done = True
        if h <= 0 and t > 1:
            events.append((t, "groundhit"))
            break
        if t > 400:
            break
    return rows, events


def ork_xml() -> str:
    sims = []
    for idx, (name, cfg, thrust, burn, prop) in enumerate((
            ("Vol nominal H128", "cfg-h128", 128.0, 1.7, 0.094),
            ("Vol réduit G80", "cfg-g80", 80.0, 1.6, 0.062)), 1):
        rows, events = simulate(thrust, burn, 1.25 if idx == 1 else 1.21, prop, 0.0012)
        apogee = max(r[1] for r in rows)
        vmax = max(r[2] for r in rows)
        amax = max(r[3] for r in rows)
        t_ap = next(t for t, e in events if e == "apogee")
        flight_time = rows[-1][0]
        dps = "\n".join(
            "          <datapoint>" + ",".join(f"{x:.5g}" for x in [r[0], r[1], r[2], r[3], r[2],
                                                               r[4], r[5], r[6], r[7], r[8], r[9]])
            + "</datapoint>" for r in rows)
        evs = "\n".join(f'          <event time="{t:.3f}" type="{e}"/>' for t, e in events)
        sims.append(f"""    <simulation status="uptodate">
      <name>{name}</name>
      <simulator>RK4Simulator</simulator>
      <calculator>BarrowmanCalculator</calculator>
      <conditions>
        <configid>{cfg}</configid>
        <launchrodlength>1.5</launchrodlength>
        <launchrodangle>5.0</launchrodangle>
        <launchroddirection>90.0</launchroddirection>
        <windaverage>3.0</windaverage>
        <windturbulence>0.1</windturbulence>
        <launchaltitude>154.0</launchaltitude>
        <launchlatitude>45.2</launchlatitude>
        <launchlongitude>0.15</launchlongitude>
        <geodeticmethod>spherical</geodeticmethod>
        <atmosphere model="extendedisa"><basetemperature>291.15</basetemperature><basepressure>101325</basepressure></atmosphere>
        <timestep>0.05</timestep>
      </conditions>
      <flightdata maxaltitude="{apogee:.3f}" maxvelocity="{vmax:.3f}" maxacceleration="{amax:.3f}" maxmach="{vmax / 340:.4f}" timetoapogee="{t_ap:.3f}" flighttime="{flight_time:.3f}" groundhitvelocity="5.4" launchrodvelocity="17.8" deploymentvelocity="4.2" optimumdelay="{t_ap - burn:.2f}">
        <warning>Recovery device deployment at high speed</warning>
        <databranch name="Sustainer" types="Time,Altitude,Vertical velocity,Vertical acceleration,Total velocity,Mass,CG location,CP location,Stability margin calibers,Thrust,Mach number">
{evs}
{dps}
        </databranch>
      </flightdata>
    </simulation>""")
    sims.append("""    <simulation status="notsimulated">
      <name>Simulation sans résultats</name>
      <conditions><configid>cfg-h128</configid><launchrodlength>1.0</launchrodlength></conditions>
    </simulation>""")
    return f"""<?xml version='1.0' encoding='utf-8'?>
<openrocket version="1.9" creator="OpenRocket 23.09">
  <rocket>
    <name>Phénix II</name>
    <designer>Club démo</designer>
    <motorconfiguration configid="cfg-h128" default="true"><stage number="0" active="true"/></motorconfiguration>
    <motorconfiguration configid="cfg-g80"><name>Config. école</name><stage number="0" active="true"/></motorconfiguration>
    <subcomponents>
      <stage>
        <name>Sustainer</name>
        <subcomponents>
          <nosecone>
            <name>Ogive</name>
            <length>0.22</length>
            <shape>ogive</shape>
            <aftradius>auto</aftradius>
            <subcomponents/>
          </nosecone>
          <bodytube>
            <name>Tube principal</name>
            <length>0.85</length>
            <radius>0.027</radius>
            <subcomponents>
              <parachute>
                <name>Principal</name>
                <diameter>0.9</diameter>
                <deployevent>apogee</deployevent>
                <deployaltitude>200</deployaltitude>
              </parachute>
              <streamer>
                <name>Banderole de secours</name>
                <deployevent>ejection</deployevent>
              </streamer>
              <innertube>
                <name>Tube moteur</name>
                <length>0.2</length>
                <outerradius>0.0145</outerradius>
                <clusterconfiguration>single</clusterconfiguration>
                <motormount>
                  <ignitionevent>automatic</ignitionevent>
                  <motor configid="cfg-h128">
                    <type>reload</type>
                    <manufacturer>AeroTech</manufacturer>
                    <digest>abc</digest>
                    <designation>H128W-14A</designation>
                    <diameter>0.029</diameter>
                    <length>0.194</length>
                    <delay>14.0</delay>
                  </motor>
                  <motor configid="cfg-g80">
                    <type>reload</type>
                    <manufacturer>AeroTech</manufacturer>
                    <designation>G80T-7</designation>
                    <diameter>0.029</diameter>
                    <length>0.124</length>
                    <delay>7.0</delay>
                  </motor>
                </motormount>
              </innertube>
              <trapezoidfinset><name>Ailerons</name><fincount>3</fincount></trapezoidfinset>
            </subcomponents>
          </bodytube>
        </subcomponents>
      </stage>
    </subcomponents>
  </rocket>
  <simulations>
{chr(10).join(sims)}
  </simulations>
</openrocket>
"""


RKT = """<?xml version="1.0" encoding="UTF-8"?>
<RockSimDocument>
  <FileVersion>4</FileVersion>
  <DesignInformation>
    <RocketDesign>
      <Name>Vega Mini</Name>
      <StageCount>1</StageCount>
      <CG>412.0</CG>
      <CP>520.5</CP>
      <Stage3Parts>
        <NoseCone><Name>Nose</Name><Len>120.0</Len><BaseDia>41.6</BaseDia><CalcMass>32.0</CalcMass></NoseCone>
        <BodyTube><Name>Body</Name><Len>500.0</Len><OD>41.6</OD><CalcMass>95.0</CalcMass>
          <AttachedParts>
            <Parachute><Name>Chute 45cm</Name><Dia>450.0</Dia><CalcMass>18.0</CalcMass></Parachute>
            <BodyTube><Name>Motor tube</Name><Len>120</Len><OD>24.8</OD><IsMotorMount>1</IsMotorMount><CalcMass>10.0</CalcMass></BodyTube>
            <FinSet><Name>Fins</Name><CalcMass>30.0</CalcMass></FinSet>
          </AttachedParts>
        </BodyTube>
      </Stage3Parts>
    </RocketDesign>
  </DesignInformation>
  <SimulationResultsList>
    <SimulationResults>
      <SimulationName>F39 calme</SimulationName>
      <MaxAltitude>285400.0</MaxAltitude>
      <MaxVelocity>61200.0</MaxVelocity>
      <MaxAcceleration>140000.0</MaxAcceleration>
      <TimeToApogee>8.3</TimeToApogee>
      <OptimalDelay>6.4</OptimalDelay>
      <LaunchGuideVelocity>14300.0</LaunchGuideVelocity>
      <SimulationEngineList>
        <Engine><EngineCode>F39-6T</EngineCode><Manufacturer>AeroTech</Manufacturer><TotalImpulse>49.7</TotalImpulse></Engine>
      </SimulationEngineList>
    </SimulationResults>
    <SimulationResults>
      <SimulationName>E30 vent fort</SimulationName>
      <MaxAltitude>190000.0</MaxAltitude>
      <MaxVelocity>48000.0</MaxVelocity>
      <TimeToApogee>7.1</TimeToApogee>
      <SimulationEngineList>
        <Engine><EngineCode>E30-4T</EngineCode><Manufacturer>AeroTech</Manufacturer><TotalImpulse>39.9</TotalImpulse></Engine>
      </SimulationEngineList>
    </SimulationResults>
  </SimulationResultsList>
</RockSimDocument>
"""


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out / "demo_phenix.ork", "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("rocket.ork", ork_xml())
    (out / "demo_vega.rkt").write_text(RKT, encoding="utf-8")
    print(f"Exemples écrits dans {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "samples")
