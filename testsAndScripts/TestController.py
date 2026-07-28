"""
===============================================================================
Project      : Terrestrial Intelligent Threat Assessment Network
Module       : RC Controller Pulse Test Utility
Author(s)    : Ricardo Rodrigues and Carolina Antunes
Institution  : Instituto Superior Tecnico
Academic Year: 2025/2026
Version       : 1.0
Last Updated  : 28 July 2026

Description:
    Debug utility for verifying the PWM signals produced by the RC receiver
    channels connected to the Raspberry Pi GPIO pins. The script listens for
    rising and falling edges, measures pulse widths in microseconds, and
    prints the values for live inspection while tuning the rover control
    logic.

===============================================================================

Program Architecture
--------------------

The software is composed of three main stages:

    1. GPIO Alert Setup
        - Claims the RC input pins and prepares them for edge detection.

    2. Pulse Measurement
        - Tracks the width of each PWM pulse using lgpio callbacks.

    3. Live Monitoring
        - Prints the measured values in real time for debugging.

===============================================================================
"""

import lgpio
import time

# ==============================================================================
# --- CONFIGURATION ---
# ==============================================================================
CHIP = 0  # Default GPIO chip
CH1_PIN = 17
CH2_PIN = 27

# ==============================================================================
# --- GPIO INITIALIZATION ---
# ==============================================================================
# Open the GPIO chip and claim the receiver channels for edge detection.
h = lgpio.gpiochip_open(CHIP)

# Claim the lines for alerts so the callbacks can monitor them as inputs.
lgpio.gpio_claim_alert(h, CH1_PIN, lgpio.BOTH_EDGES)
lgpio.gpio_claim_alert(h, CH2_PIN, lgpio.BOTH_EDGES)

# Set the debounce filters to ignore small electrical noise in microseconds.
lgpio.gpio_set_debounce_micros(h, CH1_PIN, 10)
lgpio.gpio_set_debounce_micros(h, CH2_PIN, 10)

# ==============================================================================
# --- STATE VARIABLES ---
# ==============================================================================
# Storage for the most recently measured pulse widths.
pw_ch1 = 1500
pw_ch2 = 1500

# Track the previous edge level and timestamp for each monitored pin.
last_tick = {}
last_level = {}

# ==============================================================================
# --- PWM CALLBACK ---
# ==============================================================================
def rc_callback(chip, pin, level, tick):
    """Measure the pulse width of an RC PWM signal from rising and falling edges."""
    global pw_ch1, pw_ch2, last_tick, last_level

    if pin not in last_tick:
        last_tick[pin] = 0
        last_level[pin] = 0

    if last_level[pin] == 0 and level == 1:
        # Rising edge: record the starting timestamp for the pulse.
        last_tick[pin] = tick

    elif last_level[pin] == 1 and level == 0:
        # Falling Edge: Calculate width in microseconds
        # lgpio ticks are in nanoseconds, so we subtract and divide by 1000
        width = int((tick - last_tick[pin]) / 1000)

        # Filter out extreme outliers; RC PWM is typically in the 1000-2000 us range.
        if 900 <= width <= 2100:
            if pin == CH1_PIN:
                pw_ch1 = width
            elif pin == CH2_PIN:
                pw_ch2 = width

    last_level[pin] = level

# ==============================================================================
# --- CALLBACK REGISTRATION ---
# ==============================================================================
cb1 = lgpio.callback(h, CH1_PIN, lgpio.BOTH_EDGES, rc_callback)
cb2 = lgpio.callback(h, CH2_PIN, lgpio.BOTH_EDGES, rc_callback)

print(f"Testing CH1 (GPIO {CH1_PIN}) and CH2 (GPIO {CH2_PIN}) with lgpio")
print("Move sticks on your FlySky controller...")

try:
    while True:
        print(f"\rCH1: {pw_ch1:>5} µs  |  CH2: {pw_ch2:>5} µs", end="")
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nStopping...")
    # Clean up the callbacks and close the chip.
    cb1.cancel()
    cb2.cancel()
    lgpio.gpiochip_close(h)
