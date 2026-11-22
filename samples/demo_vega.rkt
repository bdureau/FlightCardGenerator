<?xml version="1.0" encoding="UTF-8"?>
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
