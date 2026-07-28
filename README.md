# Emergency Data Mule

Emergency Data Mule is a terrestrial reconnaissance and emergency-response platform that combines rover control, edge perception, cellular telemetry, and cloud persistence. The repository supports two deployment styles:

- a centralized Raspberry Pi-based architecture for the current build
- a modular Arduino-based architecture for experimentation and alternative deployments

## Project purpose

The system is designed to support mobile emergency response scenarios by combining:

- computer vision for detecting and assessing people or objects
- GPS ingestion for location awareness
- motor and rover control for movement
- cellular connectivity through MQTT
- cloud integration with Firebase for monitoring and command relay

## Architecture overview

### 1. Centralized Raspberry-compatible architecture
This is the recommended path for the present deployment.

- [RaspberryCentralized/](RaspberryCentralized/) contains the main centralized control software for the rover.
- [edgeVisionNode/](edgeVisionNode/) handles image-based perception, GPS ingestion, and telemetry generation.
- [cloudBridge/](cloudBridge/) forwards MQTT telemetry to Firebase.

### 2. Modular Arduino-based architecture
This path reflects the earlier modular node-based approach.

- [cellularGateway/](cellularGateway/) contains firmware sketches that bridge the rover to an MQTT broker over NB-IoT.
- These folders were created for modular Arduino-based experimentation and are not required for the current Raspberry-centered build.

## Repository layout

- [cellularGateway/](cellularGateway/) – Arduino firmware for the modular edge-to-cloud gateway
- [cloudBridge/](cloudBridge/) – MQTT-to-Firebase bridge service
- [edgeVisionNode/](edgeVisionNode/) – YOLO-based vision node and telemetry generation
- [RaspberryCentralized/](RaspberryCentralized/) – centralized rover control and sensing application for Raspberry Pi
- [testsAndScripts/](testsAndScripts/) – debugging, simulation, and hardware test utilities
- [models/](models/) – pretrained model files used by the vision stack
- [bin/](bin/) – local Arduino CLI helper binary

## Recommended workflow

- For the Raspberry-based deployment, start with [RaspberryCentralized/](RaspberryCentralized/) and [edgeVisionNode/](edgeVisionNode/).
- For the Arduino-based modular deployment, use the sketches in [cellularGateway/](cellularGateway/) and the bridge in [cloudBridge/](cloudBridge/).
- Use [testsAndScripts/](testsAndScripts/) for validation, debugging, and hardware checks.

## Notes

- The system uses MQTT for telemetry transport and Firebase for cloud visibility.
- The perception pipeline relies on YOLO pose models and camera input.
- Arduino secrets headers are intentionally kept separate from source code and should be configured per deployment.
