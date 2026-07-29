# TITAN

TITAN is a terrestrial reconnaissance and emergency-response platform that combines rover control, edge perception, cellular telemetry, and cloud persistence. The repository supports two deployment styles:

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

## Recommended workflow

- For the Raspberry-based deployment, start with [RaspberryCentralized/](RaspberryCentralized/) and [edgeVisionNode/](edgeVisionNode/).
- For the Arduino-based modular deployment, use the sketches in [cellularGateway/](cellularGateway/) and the bridge in [cloudBridge/](cloudBridge/).
- Use [testsAndScripts/](testsAndScripts/) for validation, debugging, and hardware checks.

## Notes

- The system uses MQTT for telemetry transport and Firebase for cloud visibility.
- The perception pipeline relies on YOLO pose models and camera input.
- Arduino secrets headers are intentionally kept separate from source code and should be configured per deployment.

## Hardware notes

Please keep the following hardware caveats in mind for reliable operation of the system:

- The Gmouse device should be connected and left outdoors for approximately 10 minutes to 15 minutes for calibration before use.
- The camera wire extensions were soldered with swapped colors, so polarity should be verified carefully before connecting the device.
- The camera can become quite hot, so any new support structure should allow for adequate heat dissipation.
- The pins of the motor control board were re-soldered and the original identification markings are no longer visible; refer to the hardware connection documentation in the [motor driver product page](https://www.hiwonder.com/products/4-channel-encoder-motor-driver?_pos=1&_sid=17cccb2b4&_ss=r/).
- If the remote control commands appear reversed (for example, throttle or steering in the wrong direction), this can usually be corrected by changing the sign of the differential-drive mixing terms.
- When using the Arduino MKR NB 1500, the initial antenna search can draw significant current, so it is advisable to power the board from an external supply.
- Do not use the 5 V pin of the motor driver for direct connection to a processing board. Please consult the manufacturer documentation in the [driver documentation folder](https://drive.google.com/drive/folders/1ZIbMQo2R2YOgqYN3d9nTgIqJnxlGbR8m/).
- When using Arduino boards, pull-up resistors may be required on the I2C lines to prevent floating behavior. When using a Raspberry Pi, a voltage divider may be necessary because its GPIO pins cannot safely receive 5 V logic levels.
- Wiring and circuit references are available in the project PDFs: [Materials and circuit diagram - Arduino.pdf](Materials%20and%20circuit%20diagram%20-%20Arduino.pdf) and [ElectricDiagram_Raspberry.pdf](ElectricDiagram_Raspberry.pdf).

## Useful links

Chassis 
- https://www.hiwonder.com/products/suspended-shock-absorbing-tracked-chassis?variant=40378709835863 

Motor control board
- https://www.hiwonder.com/products/4-channel-encoder-motor-driver?_pos=1&_sid=17cccb2b4&_ss=r
- https://drive.google.com/drive/folders/1ZIbMQo2R2YOgqYN3d9nTgIqJnxlGbR8m

Receiver synchronization FS-iA6
- youtube.com/watch?si=seeDfcXPnpqhOFPc&v=msGpx8vEHsQ&feature=youtu.be 

