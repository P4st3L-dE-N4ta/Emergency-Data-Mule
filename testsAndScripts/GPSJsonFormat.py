"""
===============================================================================
Project      : Terrestrial Intelligent Threat Assessment Network
Module       : Phone GPS JSON Receiver
Author(s)    : Ricardo Rodrigues and Carolina Antunes
Institution  : Instituto Superior Tecnico
Academic Year: 2025/2026
Version       : 1.0
Last Updated  : 28 July 2026

Description:
    Lightweight HTTP listener used to receive JSON payloads from a mobile
    device or sensor logger. The script accepts POST requests, decodes the
    incoming JSON, prints the received data for inspection, and responds with
    a success status to the sender.

===============================================================================

System Role
-----------

The script acts as a local ingestion endpoint for testing and prototyping.
It allows a phone or external device to push GPS or telemetry data to a
nearby computer without needing a full cloud backend.

===============================================================================
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class SensorLoggerHandler(BaseHTTPRequestHandler):
    """Handle incoming POST requests containing JSON payloads from a mobile sensor app."""
    def do_POST(self):
        # Determine how much data the sender transmitted in the request body.
        content_length = int(self.headers['Content-Length'])

        # Read the raw request payload from the incoming connection.
        post_data = self.rfile.read(content_length)

        # Decode the payload and print it in a readable format.
        try:
            data = json.loads(post_data.decode('utf-8'))
            print("\n" + "="*40)
            print("📡 NEW DATA RECEIVED FROM PHONE 📡")
            print("="*40)
            print(json.dumps(data, indent=4)) 
        except json.JSONDecodeError:
            print("Received data, but it wasn't valid JSON.")

        # Respond to the sender with a simple success message.
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"success"}')

    # Suppress the default HTTP logging so the terminal output remains concise.
    def log_message(self, format, *args):
        pass

# ==============================================================================
# --- SERVER CONFIGURATION ---
# ==============================================================================
PORT = 8000
# Bind to all network interfaces so the endpoint is reachable from nearby devices.
IP = '0.0.0.0'
server = HTTPServer((IP, PORT), SensorLoggerHandler)

print(f"🖥️  Python Server is listening on port {PORT}...")
print("-> Make sure your PC and Phone are on the same Wi-Fi.")
print("-> Find your PC's actual local IP address (e.g., 192.168.1.X).")
print(f"-> In Sensor Logger, set the Push URL to: http://<YOUR_PC_IP>:{PORT}")

try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nShutting down server.")
    server.server_close()