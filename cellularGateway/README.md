# Cellular Gateway

This directory contains the modular Arduino firmware used for the edge-to-cloud link in the original modular architecture.

## Contents

- [MqttNBIoT/](MqttNBIoT/) – Arduino sketch for an NB-IoT MQTT gateway using the MKR NB 1500 modem.
- [MqttNBIoT_UART/](MqttNBIoT_UART/) – variant that uses a serial UART-based path for the cellular modem integration.

## Purpose

These sketches receive telemetry from the rover side over USB serial and publish it to an MQTT broker over the cellular network. They were designed as modular node firmware pieces for an Arduino-based deployment.

## Notes

- The sketches rely on the Arduino secrets headers, especially [MqttNBIoT/arduino_secrets.h](MqttNBIoT/arduino_secrets_template.h) and [MqttNBIoT_UART/arduino_secrets.h](MqttNBIoT_UART/arduino_secrets_template.h).
- The current Raspberry-compatible build uses the centralized architecture instead, but these firmware modules remain useful for modular or alternate deployments.
