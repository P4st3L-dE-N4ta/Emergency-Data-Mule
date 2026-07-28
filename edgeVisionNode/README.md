# Edge Vision Node

This directory contains the perception stack for the emergency data mule. It is responsible for ingesting GPS updates, running computer vision inference, and generating structured telemetry for downstream relay.

## Main entry point

- [main_yolo.py](main_yolo.py) – primary YOLO-based vision application for the current edge deployment.

## What the node does

- Accepts GPS updates over HTTP from a phone or external logger.
- Loads a YOLO pose model from the repository’s [models/](../models/) directory.
- Captures frames from a local camera.
- Classifies posture and priority based on detected persons.
- Sends telemetry payloads to the Arduino gateway over serial for MQTT transmission.

## Supporting scripts

- [TestsAndScripts/](TestsAndScripts/) – experimental and debugging scripts for camera testing, posture tracking, and model validation.

## Dependencies

Install the dependencies listed in [requirements.txt](requirements.txt).
