# Cloud Bridge

The cloud bridge connects the rover telemetry stream to Firebase and provides a cloud-side relay for command messages.

## What it does

- Subscribes to MQTT telemetry published by the cellular gateway.
- Parses the incoming JSON payloads.
- Stores the data in Firebase Realtime Database.
- Optionally relays commands from Firebase back to the edge device over MQTT.

## Main component

- [mqtt_to_firebase.py](mqtt_to_firebase.py) – Python service that manages MQTT and Firebase integration.

## Setup notes

- Install the required libraries from [requirements.txt](requirements.txt).
- Configure Firebase credentials and MQTT connection settings in the environment or deployment config.
- The service expects a Firebase service account key file and broker credentials.
