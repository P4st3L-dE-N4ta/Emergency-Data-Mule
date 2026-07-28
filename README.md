# Emergency Data Mule

Emergency Data Mule is a terrestrial reconnaissance and emergency-response platform that combines edge perception, rover control, cellular telemetry, and cloud persistence. The repository contains both a modular Arduino-based deployment path and a centralized Raspberry Pi-oriented deployment path.

## Architecture overview

The project currently supports two complementary architectures:

1. Centralized Raspberry-compatible architecture (recommended for the current build)
   - [RaspberryCentralized/](RaspberryCentralized/) contains the main centralized control software for the rover.
   - [edgeVisionNode/](edgeVisionNode/) handles camera-based perception, GPS ingestion, and telemetry generation.
   - [cloudBridge/](cloudBridge/) forwards MQTT telemetry into Firebase.

2. Modular Arduino-based architecture (legacy or alternative deployment)
   - [cellularGateway/](cellularGateway/) contains firmware sketches that bridge the rover to an MQTT broker over NB-IoT.
   - These node folders were created for modular Arduino-based experimentation and are not required for the current centralized Raspberry version.

## Repository layout

- [cellularGateway/](cellularGateway/) – Arduino firmware for the modular edge-to-cloud gateway.
- [cloudBridge/](cloudBridge/) – MQTT-to-Firebase bridge service.
- [edgeVisionNode/](edgeVisionNode/) – YOLO-based vision node and telemetry generation.
- [RaspberryCentralized/](RaspberryCentralized/) – centralized Rover control and sensing application for Raspberry Pi.
- [testsAndScripts/](testsAndScripts/) – test utilities, simulation helpers, and debug scripts.
- [models/](models/) – pretrained model files used by the vision stack.
- [bin/](bin/) – local Arduino CLI helper binary.

## Recommended workflow

- For the Raspberry-based deployment, start with [RaspberryCentralized/](RaspberryCentralized/) and [edgeVisionNode/](edgeVisionNode/).
- For the Arduino-based modular deployment, use the sketches in [cellularGateway/](cellularGateway/) and the bridge in [cloudBridge/](cloudBridge/).
- Use [testsAndScripts/](testsAndScripts/) for validation and hardware debugging.

## Notes

- The project uses MQTT for telemetry transport and Firebase for cloud visibility.
- The vision pipeline relies on YOLO pose models and camera input.
- The Arduino secrets headers are intentionally separate from the source code and should be configured per deployment.
