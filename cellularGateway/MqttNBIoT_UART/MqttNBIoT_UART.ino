/*
===============================================================================
Project      : Terrestrial Intelligent Threat Assessment Network
Module       : NB-IoT MQTT Gateway over Serial1
Author(s)    : Ricardo Rodrigues and Carolina Antunes
Institution  : Instituto Superior Tecnico
Academic Year: 2025/2026
Version       : 1.0
Last Updated  : 28 July 2026

Description:
    Edge-to-cloud bridge for the emergency data mule. This variant uses the
    MKR NB 1500 modem together with the Arduino Serial1 interface to receive
    JSON telemetry from the Raspberry Pi over a serial link, then publish it
    to the MQTT broker through the cellular modem.

===============================================================================

System Role
-----------

The firmware is responsible for four main tasks:

    1. Cellular registration on the NB-IoT network.
    2. MQTT connection setup with the broker.
    3. Listening for JSON payloads arriving through Serial1.
    4. Publishing telemetry to the configured topic and returning status
       feedback over the same serial interface.

===============================================================================
*/

#include <MKRNB.h>
#include <PubSubClient.h>
#include "arduino_secrets.h"

// ==============================================================================
// --- CELLULAR AND MQTT CONFIGURATION ---
// ==============================================================================
const char PINNUMBER[] = SECRET_PINNUMBER;

// Initialize the library instances used for cellular access and MQTT communication.
NBClient nbclient;
GPRS gprs;
NB nbAccess;

// MQTT broker settings
// These are loaded from the secrets header for deployment.
// const char* mqtt_server = "test.mosquitto.org";
// const int port = 1883;
const char* mqtt_server = SECRET_MQTT_SERVER; // Your GCP IP address
const int port = 1883; 
const char* mqtt_user = MOSQUITTO_CREDENTIALS_USERNAME;
const char* mqtt_pass = MOSQUITTO_CREDENTIALS_PASSWORD;

// Device identity and telemetry topic used by the cloud bridge.
const char* clientID = "Vodafone_Edge_G17_17032026";
const char* topic_telemetry = "/RMIC_G17/telemetry";

// Connect the PubSub client to the NB client transport layer.
PubSubClient client(nbclient);

// ==============================================================================
// --- MQTT RECONNECTION HANDLER ---
// ==============================================================================
void reconnect() {
  while (!client.connected()) {
    Serial1.println("Attempting connection to Mosquitto Broker...");

    if (client.connect(clientID, mqtt_user, mqtt_pass)) {
      Serial1.println("🟢 Connected to MQTT Broker!");
      Serial1.println("READY");  // Inform the Python control software that the bridge is ready.
    } else {
      Serial1.print("🔴 Failed, rc=");
      Serial1.print(client.state());
      Serial1.println(" - trying again in 3 seconds...");
      delay(3000);
    }
  }
}

// ==============================================================================
// --- ARDUINO SETUP ---
// ==============================================================================
void setup() {
  // Match the Python serial settings so telemetry is framed correctly over Serial1.
  Serial1.begin(115200);
  while (!Serial1) {
    ; // Wait for the Serial1 port to connect.
  }

  // Give the Arduino a small buffer window to capture the full JSON line.
  Serial1.setTimeout(100);

  Serial1.println("Starting Edge-to-Cloud MQTT Bridge...");
  
  boolean connected = false;

  // Attach the modem to the cellular network before starting MQTT.
  while (!connected) {
    if ((nbAccess.begin(PINNUMBER) == NB_READY) &&
        (gprs.attachGPRS() == GPRS_READY)) {
      connected = true;
    } else {
      Serial1.println("Not connected to Cellular, retrying in 2 seconds...");
      delay(2000);
    }
  }
  Serial1.println("📡 Cellular Modem attached to Vodafone Network!");

  // Expand the MQTT buffer to 512 bytes so large JSON telemetry can be published safely.
  client.setBufferSize(512);
  client.setServer(mqtt_server, port);
}

// ==============================================================================
// --- MAIN LOOP ---
// ==============================================================================
void loop() {
  // Keep the MQTT session alive while the bridge is running.
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Read any JSON telemetry sent from the Python control software over Serial1.
  if (Serial1.available() > 0) {
     
    String payload = Serial1.readStringUntil('\n');
    payload.trim();

    // Verify that the received line is JSON before publishing it to the cloud.
    if (payload.length() > 0 && payload.startsWith("{")) {
      Serial1.print("Attempting to publish ");
      Serial1.print(payload.length());
      Serial1.println(" bytes...");

      if (client.publish(topic_telemetry, payload.c_str())) {
        // Send a success status message back to the control software for debugging.
        Serial1.println("✅ MQTT Publish Success!");
      } else {
        // Send an error message back to the control software if the publish fails.
        Serial1.print("❌ MQTT Publish Failed. Error State: ");
        Serial1.println(client.state());
      }
    }
  }
}
