import serial
import pynmea2
import time

# --- CONFIGURATION ---
# Change this to match your PC's specific port!
# Windows example: 'COM3' | Mac/Linux example: '/dev/tty.usbserial-1410'
PORT = '/dev/ttyACM0' 
BAUD = 9600 # Standard baud rate for most G-Mouse / USB GPS modules

def test_gps():
    print(f"🔌 Attempting to connect to GPS module on {PORT}...")
    
    try:
        with serial.Serial(PORT, BAUD, timeout=1) as ser:
            print("✅ Serial connection established! Reading data stream...\n")
            print("Press Ctrl+C to exit.")
            print("-" * 60)
            
            while True:
                # Read a line from the GPS module
                try:
                    line = ser.readline().decode('ascii', errors='replace').strip()
                except Exception as e:
                    print(f"❌ Error reading serial line: {e}")
                    continue

                if not line:
                    continue

                # Print the raw data so you know the hardware is talking
                print(f"📦 [RAW]: {line}")

                # Check for position lines ($GPGGA or $GPRMC)
                if line.startswith('$GPGGA') or line.startswith('$GPRMC'):
                    try:
                        msg = pynmea2.parse(line)
                        
                        # Verify if the module has found satellites yet
                        if hasattr(msg, 'latitude') and msg.latitude != 0.0:
                            print("\n" + "="*40)
                            print("🛰️  GPS LOCK ACQUIRED!")
                            print(f"   Latitude:  {round(msg.latitude, 6)}")
                            print(f"   Longitude: {round(msg.longitude, 6)}")
                            if hasattr(msg, 'num_sats'):
                                print(f"   Satellites in view: {msg.num_sats}")
                            print("="*40 + "\n")
                        else:
                            print("   ⏳ [Status]: Raw data received, but searching for satellite lock...")
                    
                    except pynmea2.ParseError:
                        # Occasional string corruption is normal when starting up
                        pass

                time.sleep(0.1)

    except serial.SerialException as e:
        print(f"\n❌ Failed to connect to {PORT}.")
        print("   Please check that the module is securely plugged in and you have the correct port name.")
        print(f"   Error details: {e}")
    except KeyboardInterrupt:
        print("\n👋 Test stopped by user. Exiting.")

if __name__ == "__main__":
    test_gps()