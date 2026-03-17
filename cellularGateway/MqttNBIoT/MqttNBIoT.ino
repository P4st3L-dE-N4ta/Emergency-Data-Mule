#include <MKRNB.h>
#include <PubSubClient.h>
#include "arduino_secrets.h"

const char PINNUMBER[] = SECRET_PINNUMBER;

// Initialize the library instances
NBClient nbclient;
GPRS gprs;
NB nbAccess;

// MQTT Info
const char* mqtt_server = "test.mosquitto.org";
const int port = 1883;

// Give your device a unique ID and set the single JSON topic
const char* clientID = "Vodafone_Edge_G17_17032026"; 
const char* topic_telemetry = "/RMIC_G17/telemetry";

// Connect the PubSub client
PubSubClient client(nbclient);

// Connection and reconnection function
void reconnect() {
  while (!client.connected()) {
    Serial.println("Attempting connection to Mosquitto Broker...");
    
    if (client.connect(clientID)) {
      Serial.println("🟢 Connected to MQTT Broker!");
      Serial.println("READY"); // Tell Python we are ready!
    } else {
      Serial.print("🔴 Failed, rc=");
      Serial.print(client.state());
      Serial.println(" - trying again in 3 seconds...");
      delay(3000);
    }
  }
}

void setup() {
  // CRITICAL: Set to 115200 to perfectly match your Python script!
  Serial.begin(115200);
  while (!Serial) {
    ; // wait for serial port to connect
  }
  // Give the Arduino a tiny buffer to catch the whole string
  Serial.setTimeout(100); 
  
  Serial.println("Starting Edge-to-Cloud MQTT Bridge...");
  
  boolean connected = false;

  // Attach to the cellular network
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

  // --- ADD THIS LINE TO FIX THE CRASH ---
  // Expand the MQTT buffer to 512 bytes to comfortably fit your JSON
  client.setBufferSize(512); 
  
  client.setServer(mqtt_server, port); 
}

void loop() {
  // 1. Keep the highly efficient MQTT pipe open
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // 2. Check if Python sent us the YOLO JSON string over the USB cable
  if (Serial.available() > 0) {
     
    String payload = Serial.readStringUntil('\n');
    payload.trim(); 

    // 3. Verify it is our JSON payload
    if (payload.length() > 0 && payload.startsWith("{")) {
      
      // 4. FIRE IT TO THE CLOUD VIA MQTT!
      Serial.print("Attempting to publish ");
      Serial.print(payload.length());
      Serial.println(" bytes...");
	
      //if (client.publish(topic_telemetry, "{\"test\":\"ok\"}")) {
      if (client.publish(topic_telemetry, payload.c_str())) {
        // Send a success message BACK to Python so you can see it in Ubuntu
        Serial.println("✅ MQTT Publish Success!");
      } else {
        // Send an error message BACK to Python if it fails
        Serial.print("❌ MQTT Publish Failed. Error State: ");
        Serial.println(client.state());
      }
    }
  }
}
