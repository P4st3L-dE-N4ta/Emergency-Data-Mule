#!/usr/bin/env python

"""
===============================================================================
Project      : Terrestrial Intelligent Threat Assessment Network
Module       : MQTT to Firebase Bridge
Author(s)    : Ricardo Rodrigues and Carolina Antunes
Institution  : Instituto Superior Tecnico
Academic Year: 2025/2026
Version       : 1.0
Last Updated  : 28 July 2026

Description:
    Cloud bridge for the emergency data mule. The script subscribes to MQTT
    telemetry published by the Arduino gateway, parses the incoming JSON,
    and forwards the data to Firebase Realtime Database for live monitoring
    and historical event storage. It can also relay Firebase command updates
    back to the edge device over MQTT.

===============================================================================

System Role
-----------

The software is responsible for three main tasks:

    1. MQTT ingestion
        - Receives telemetry published by the cellular gateway on the edge.

    2. Firebase persistence
        - Stores the latest telemetry under the live dashboard path and keeps
          a history of all received events.

    3. Bidirectional command forwarding
        - Watches Firebase commands and republishes selected updates back to
          the edge device over MQTT when requested.

===============================================================================
"""

import time
import json
import paho.mqtt.client as mqtt
import firebase_admin
from firebase_admin import credentials, db
import os
from dotenv import load_dotenv

# ==============================================================================
# --- FIREBASE CONFIGURATION ---
# ==============================================================================
load_dotenv()

# Load the service account key JSON file from the environment configuration.
cred = credentials.Certificate(os.getenv("FIREBASE_KEY_PATH"))

# Initialize the Firebase Admin SDK for Realtime Database access.
firebase_admin.initialize_app(cred, {'databaseURL': os.getenv("FIREBASE_DATABASE_URL")})

# ==============================================================================
# --- MQTT CONFIGURATION AND CALLBACKS ---
# ==============================================================================
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)


def on_connect(client, userdata, flags, rc, properties):
    """Subscribe to the telemetry topics once the MQTT broker connection is established."""
    print(f"🟢 Connected to Mosquitto with result code {rc}")
    client.subscribe("/RMIC_G17/#")


def on_message(client, userdata, message):
    """Handle incoming MQTT telemetry, parse the JSON payload, and forward it to Firebase."""
    if message.topic == "/RMIC_G17/telemetry":
        try:
            # Decode the raw bytes from MQTT into a UTF-8 string.
            payload_str = message.payload.decode('utf-8')

            # Parse the string into a Python dictionary (JSON).
            data = json.loads(payload_str)
            print(f"📥 Received Telemetry: {data}")

            # Update the live dashboard view with the latest telemetry.
            db.reference("RMIC_G17_Live").update(data)

            # Keep a time-stamped history of every received event.
            db.reference("RMIC_G17_History").push(data)

            print("☁️ Successfully pushed to Firebase!")

        except json.JSONDecodeError as e:
            print(f"⚠️ JSON Parse Error: Received malformed data from Arduino: {e}")
            pass
        except Exception as e:
            print(f"❌ Firebase Error: {e}")

# ==============================================================================
# --- FIREBASE-TO-EDGE COMMANDS ---
# ==============================================================================
def fb_stream_handler(event):
    """Listen for command updates in Firebase and relay them back to the edge device over MQTT."""
    print(f"🔔 Firebase Stream Update - Path: {event.path}, Data: {event.data}")

    if event.path == "/enable_alert_sound":
        val = 1 if event.data == True else 0
        print(f"Sending command back to Edge: {val}")
        mqtt_client.publish("/RMIC_G17/enable_alert_sound", val, qos=1)

    elif event.path == "/" and isinstance(event.data, dict):
        if "enable_alert_sound" in event.data:
            val = 1 if event.data["enable_alert_sound"] == True else 0
            print(f"Sending command back to Edge: {val}")
            mqtt_client.publish("/RMIC_G17/enable_alert_sound", val, qos=1)

# ==============================================================================
# --- MAIN LOOP ---
# ==============================================================================
def main():
    """Initialize the MQTT and Firebase listeners and keep the bridge running."""
    # Start listening to Firebase for command updates.
    commands_ref = db.reference("commands")
    my_stream = commands_ref.listen(fb_stream_handler)

    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    # Load the broker connection details from environment configuration.
    broker_ip = os.getenv("MQTT_BROKER_IP")
    mqtt_user = os.getenv("MQTT_USER")
    mqtt_password = os.getenv("MQTT_PASSWORD")

    # Authenticate with the broker.
    mqtt_client.username_pw_set(mqtt_user, mqtt_password)

    print(f"Connecting to Google Cloud Broker at {broker_ip}...")
    mqtt_client.connect(broker_ip, 1883, 60)

    mqtt_client.loop_start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Program interrupted by the user. Shutting down...")
        mqtt_client.loop_stop()
        my_stream.close()


if __name__ == '__main__':
    print('🚀 Starting Edge-to-Cloud Bridge (Mosquitto -> Firebase)')
    main()
