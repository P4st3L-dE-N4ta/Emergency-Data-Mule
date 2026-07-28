"""
===============================================================================
Project      : Terrestrial Intelligent Threat Assessment Network
Module       : GPS Receiver Test Utility
Author(s)    : Ricardo Rodrigues and Carolina Antunes
Institution  : Instituto Superior Tecnico
Academic Year: 2025/2026
Version       : 1.0
Last Updated  : 28 July 2026

Description:
    Debug utility for verifying the serial data stream from the GPS receiver.
    The script opens a serial connection to the GPS module, reads NMEA
    sentences, parses position information, and prints the latest latitude,
    longitude, and satellite status for live validation.

===============================================================================

Program Architecture
--------------------

The software is composed of two main stages:

    1. Serial Reading
        - Reads incoming NMEA sentences from the connected GPS module.

    2. Position Parsing
        - Parses and prints location information when a valid fix is available.

===============================================================================
"""

import serial
import pynmea2
import time

# ==============================================================================
# --- CONFIGURATION ---
# ==============================================================================
# Change this to match your PC's specific port.
# Windows example: 'COM3' | Mac/Linux example: '/dev/tty.usbserial-1410'
PORT = '/dev/ttyACM0'
BAUD = 9600  # Standard baud rate for most G-Mouse / USB GPS modules

# ==============================================================================
# --- GPS TEST ROUTINE ---
# ==============================================================================
def test_gps():
    """Connect to the GPS receiver and print incoming NMEA data and parsed coordinates."""
    print(f"🔌 Attempting to connect to GPS module on {PORT}...")
    
    try:
        with serial.Serial(PORT, BAUD, timeout=1) as ser:
            print("✅ Serial connection established! Reading data stream...\n")
            print("Press Ctrl+C to exit.")
            print("-" * 60)
            
            while True:
                # Read a line from the GPS module.
                try:
                    line = ser.readline().decode('ascii', errors='replace').strip()
                except Exception as e:
                    print(f"❌ Error reading serial line: {e}")
                    continue

                if not line:
                    continue

                # Print the raw data so the hardware activity is visible.
                print(f"📦 [RAW]: {line}")

                # Check for position lines ($GPGGA or $GPRMC).
                if line.startswith('$GPGGA') or line.startswith('$GPRMC'):
                    try:
                        msg = pynmea2.parse(line)
                        
                        # Verify whether the module has found satellites yet.
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
                        # Occasional string corruption is normal when the module starts up.
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