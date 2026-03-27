#!/usr/bin/env python

import time
import json
import paho.mqtt.client as mqtt
# import pyrebase # Note: Use pip install pyrebase4 if you are on newer Python 3.x versions
import firebase_admin
from firebase_admin import credentials, db
import os
from dotenv import load_dotenv


# ==========================================
# 1. FIREBASE CONFIGURATION
# ==========================================
load_dotenv()

# Load the Service Account Key JSON file
cred = credentials.Certificate(os.getenv("FIREBASE_KEY_PATH"))

# Initialize the app with Admin privileges
firebase_admin.initialize_app(cred, {'databaseURL':os.getenv("FIREBASE_DATABASE_URL")})

#firebase_config = {
#    "apiKey": os.getenv("FIREBASE_API_KEY"),
#    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
#    "databaseURL": os.getenv("FIREBASE_DATABASE_URL"),
#    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET")
#}

#firebase = pyrebase.initialize_app(firebase_config)
#db = firebase.database()

# ==========================================
# 2. MQTT SETUP & CALLBACKS
# ==========================================
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_connect(client, userdata, flags, rc, properties):
    print(f"🟢 Connected to Mosquitto with result code {rc}")
    # Subscribe to your specific telemetry topic
    client.subscribe("/RMIC_G17/#")  

def on_message(client, userdata, message):
    # We only care about the telemetry topic for now
    if message.topic == "/RMIC_G17/telemetry":
        try:
            # 1. Decode the raw bytes from MQTT into a string
            payload_str = message.payload.decode('utf-8')
            
            # 2. Parse the string into a Python dictionary (JSON)
            data = json.loads(payload_str)
            print(f"📥 Received Telemetry: {data}")
            
            # 3. Update Firebase
            # .update() overwrites the existing data, creating a "Live Dashboard" state
            # db.child("RMIC_G17_Live").update(data)
            db.reference("RMIC_G17_Live").update(data)
            

            # OPTIONAL: If you want to keep a history of all events instead of just the latest, 
            # uncomment the line below. .push() creates a unique timestamped list.
            # db.child("RMIC_G17_History").push(data)
            db.reference("RMIC_G17_History").push(data)

            print("☁️ Successfully pushed to Firebase!")

        except json.JSONDecodeError as e:
            print(f"⚠️ JSON Parse Error: Received malformed data from Arduino: {e}")
            pass
        except Exception as e:
            print(f"❌ Firebase Error: {e}")

# ==========================================
# 3. OPTIONAL: CLOUD-TO-EDGE COMMANDS
# ==========================================
# If you want to send commands from Firebase BACK to the Arduino
#def fb_stream_handler(message):
#    print(f"🔔 Firebase Stream Update: {message}")
#    
#    # Example: If you toggle a switch in Firebase to turn on a siren
#    if message.get("path") == "/enable_alert_sound":
#        val = 1 if message["data"] == True else 0
#        print(f"Sending command back to Edge: {val}")
#        mqtt_client.publish("/RMIC_G17/enable_alert_sound", val, qos=1)

# In firebase-admin, the listener receives an "Event" object
def fb_stream_handler(event):
    # event.path is the relative path (e.g., "/enable_alert_sound" or "/")
    # event.data is the new value
    print(f"🔔 Firebase Stream Update - Path: {event.path}, Data: {event.data}")
    
    # Check if the specific command was updated directly
    if event.path == "/enable_alert_sound":
        val = 1 if event.data == True else 0

        print(f"Sending command back to Edge: {val}")
        mqtt_client.publish("/RMIC_G17/enable_alert_sound", val, qos=1)
        
        # Check if the entire 'commands' object was updated at once (usually happens on startup)
    elif event.path == "/" and isinstance(event.data, dict):
        if "enable_alert_sound" in event.data:
            val = 1 if event.data["enable_alert_sound"] == True else 0
            print(f"Sending command back to Edge: {val}")
            mqtt_client.publish("/RMIC_G17/enable_alert_sound", val, qos=1)

# ==========================================
# 4. MAIN LOOP
# ==========================================
def main():
    # Start listening to Firebase for any commands to send down to the Edge
#    my_stream = db.child("commands").stream(fb_stream_handler, stream_id="edge_commands")

    # Start listening to Firebase. In firebase-admin, we use .listen()
    commands_ref = db.reference("commands")
    my_stream = commands_ref.listen(fb_stream_handler)
    
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    print("Connecting to test.mosquitto.org...")
    mqtt_client.connect('test.mosquitto.org', 1883, 60) 
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
