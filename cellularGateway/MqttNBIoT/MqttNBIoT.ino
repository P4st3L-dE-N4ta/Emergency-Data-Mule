/*
===============================================================================
Project      : Terrestrial Intelligent Threat Assessment Network
Module       : NB-IoT MQTT Gateway
Author(s)    : Ricardo Rodrigues and Carolina Antunes
Institution  : Instituto Superior Tecnico
Academic Year: 2025/2026
Version       : 1.0
Last Updated  : 28 July 2026

Description:
    Edge-to-cloud bridge for the emergency data mule. The Arduino uses the
    MKR NB 1500 modem to attach to the cellular network, establish an MQTT
    session, and publish JSON telemetry received over the USB serial link from
    the Raspberry Pi. This sketch acts as the gateway between the rover and
    the cloud broker.

===============================================================================

System Role
-----------

The firmware is responsible for four main tasks:

    1. Cellular registration on the NB-IoT network.
    2. MQTT connection setup with the broker.
    3. Listening for JSON payloads from the Python control software.
    4. Publishing telemetry to the configured topic and returning status
       feedback over the serial port.

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
    Serial.println("Attempting connection to Mosquitto Broker...");

    if (client.connect(clientID, mqtt_user, mqtt_pass)) {
      Serial.println("🟢 Connected to MQTT Broker!");
      Serial.println("READY");  // Inform the Python control software that the bridge is ready.
    } else {
      Serial.print("🔴 Failed, rc=");
      Serial.print(client.state());
      Serial.println(" - trying again in 3 seconds...");
      delay(3000);
    }
  }
}

// ==============================================================================
// --- ARDUINO SETUP ---
// ==============================================================================
void setup() {
  // Match the Python serial settings to avoid framing issues during telemetry transfer.
  Serial.begin(115200);
  while (!Serial) {
    ; // Wait for the serial port to connect.
  }

  // Give the Arduino a small buffer window to capture the full JSON line.
  Serial.setTimeout(100);

  Serial.println("Starting Edge-to-Cloud MQTT Bridge...");
  
  boolean connected = false;

  // Attach the modem to the cellular network before starting MQTT.
  while (!connected) {
    if ((nbAccess.begin(PINNUMBER) == NB_READY) &&
        (gprs.attachGPRS() == GPRS_READY)) {
      connected = true;
    } else {
      Serial.println("Not connected to Cellular, retrying in 2 seconds...");
      delay(2000);
    }
  }
  Serial.println("📡 Cellular Modem attached to Vodafone Network!");

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

  // Read any JSON telemetry sent from the Python control software over USB serial.
  if (Serial.available() > 0) {
    String payload = Serial.readStringUntil('\n');
    payload.trim();

    // Verify that the received line is JSON before publishing it to the cloud.
    if (payload.length() > 0 && payload.startsWith("{")) {
      Serial.print("Attempting to publish ");
      Serial.print(payload.length());
      Serial.println(" bytes...");

      if (client.publish(topic_telemetry, payload.c_str())) {
        // Send a success status message back to Python for debugging.
        Serial.println("✅ MQTT Publish Success!");
      } else {
        // Send an error message back to Python if the publish fails.
        Serial.print("❌ MQTT Publish Failed. Error State: ");
        Serial.println(client.state());
      }
    }
  }
}
