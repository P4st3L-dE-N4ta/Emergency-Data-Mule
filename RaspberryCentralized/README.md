# Raspberry Centralized Architecture

This directory contains the centralized software stack intended for the Raspberry Pi-based rover deployment.

## Purpose

The centralized version brings the main control logic into a single software application rather than distributing responsibilities across separate modular nodes. It is the recommended path for the present Raspberry-compatible build.

## Main component

- [PitchCode.py](PitchCode.py) – the main rover control application that coordinates vision, GPS, motor control, and serial communication.

## What it handles

- Camera acquisition and vision processing.
- GPS ingestion and state tracking.
- RC input and motor control logic.
- Communication with the Arduino gateway over serial.

## Setup notes

- Install dependencies from [requirements.txt](requirements.txt).
- Review the configuration constants near the top of [PitchCode.py](PitchCode.py) before deployment.
- The current implementation expects a Raspberry Pi environment with compatible camera and GPIO support.
