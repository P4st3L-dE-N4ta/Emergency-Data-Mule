from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class SensorLoggerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Figure out how much data the phone sent
        content_length = int(self.headers['Content-Length'])
        
        # 2. Read the raw data
        post_data = self.rfile.read(content_length)
        
        # 3. Decode and print it nicely
        try:
            data = json.loads(post_data.decode('utf-8'))
            print("\n" + "="*40)
            print("📡 NEW DATA RECEIVED FROM PHONE 📡")
            print("="*40)
            print(json.dumps(data, indent=4)) 
        except json.JSONDecodeError:
            print("Received data, but it wasn't valid JSON.")

        # 4. Tell the phone "Message received successfully!"
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status":"success"}')

    # Hide the standard HTTP server logging to keep your terminal clean
    def log_message(self, format, *args):
        pass

# Start the server on port 8000
PORT = 8000
# Leave this as 0.0.0.0 so Python listens on all network adapters without crashing
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