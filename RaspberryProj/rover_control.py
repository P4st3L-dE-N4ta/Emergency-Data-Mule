#!/usr/bin/env python3

"""
===============================================================================
Project      : Terrestrial Intelligent Threat Assessment Network
Module       : Rover Motor Control Interface
Author(s)    : Ricardo Rodrigues and Carolina Antunes
Institution  : Instituto Superior Tecnico
Academic Year: 2025/2026
Version       : 1.0
Last Updated  : 28 July 2026

Description:
    Lightweight motor-control interface for the autonomous reconnaissance
    rover. The script reads RC receiver PWM signals from the Raspberry Pi
    GPIO pins, mixes throttle and steering inputs into differential drive
    commands, and transmits the resulting motor speeds to the I2C motor
    driver. It is used as a standalone test/debug utility for the chassis
    and as a building block for the main data mule control flow.

===============================================================================

Program Architecture
--------------------

The software is composed of three main stages:

    1. RC Input Acquisition
        - Reads PWM values from the throttle and steering channels.

    2. Differential Drive Mixing
        - Combines throttle and steering into left/right motor commands.

    3. I2C Actuation
        - Sends the resulting byte values to the motor controller driver.

===============================================================================
"""

from smbus2 import SMBus
import lgpio
import time

# ==============================================================================
# --- I2C CONFIGURATION ---
# ==============================================================================
I2C_ADDR = 0x34
MOTOR_FIXED_SPEED_ADDR = 0x33
MOTOR_TYPE_ADDR = 0x14
MOTOR_ENCODER_POLARITY_ADDR = 0x15

# Motor driver type for the JGB37-520 12V 110RPM unit.
MOTOR_TYPE_JGB37_520_12V_110RPM = 3

# ==============================================================================
# --- GPIO CONFIGURATION ---
# ==============================================================================
CHIP = 0
THROTTLE_PIN = 17
STEERING_PIN = 27

# Open the GPIO chip once and keep it available for the callback handlers.
h = lgpio.gpiochip_open(CHIP)

# Claim the RC input pins as edge-detect alerts and reduce signal noise.
lgpio.gpio_claim_alert(h, THROTTLE_PIN, lgpio.BOTH_EDGES)
lgpio.gpio_claim_alert(h, STEERING_PIN, lgpio.BOTH_EDGES)
lgpio.gpio_set_debounce_micros(h, THROTTLE_PIN, 10)
lgpio.gpio_set_debounce_micros(h, STEERING_PIN, 10)

# ==============================================================================
# --- GLOBAL STATE VARIABLES ---
# ==============================================================================
# Defaulting to 1500 us, which corresponds to the neutral position for many RC receivers.
pulse_widths = {
    THROTTLE_PIN: 1500,
    STEERING_PIN: 1500
}

# ==============================================================================
# --- UTILITY FUNCTIONS ---
# ==============================================================================
def map_value(x, in_min, in_max, out_min, out_max):
    """Map a value from one range into another while preserving integer output."""
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)


def constrain(x, minimum, maximum):
    """Clamp a value inside the allowed bounds."""
    return max(minimum, min(maximum, x))


def signed_to_byte(value):
    # Converts signed integer to two's complement byte for I2C
    return value & 0xFF

# ==============================================================================
# --- PWM INPUT CALLBACK ---
# ==============================================================================
rise_ticks = {}


def pwm_callback(chip, gpio, level, tick):
    """Capture RC pulse widths from rising and falling GPIO edges."""
    if level == 1:
        # Store the timestamp of the rising edge for later pulse-width calculation.
        rise_ticks[gpio] = tick
    elif level == 0:
        if gpio in rise_ticks:
            # lgpio ticks are in nanoseconds, so convert them to microseconds.
            width = int((tick - rise_ticks[gpio]) / 1000)
            # Filter slightly wider than your 1000-2000 range to catch extremes safely
            if 700 <= width <= 2100:
                pulse_widths[gpio] = width

# ==============================================================================
# --- MAIN PROGRAM ---
# ==============================================================================
def main():
    """Initialize the motor controller and continuously stream drive commands."""
    bus = SMBus(1)

    print("Configuring motor controller...")
    try:
        # Initialize the motor driver over I2C before any motion commands are sent.
        bus.write_byte_data(I2C_ADDR, MOTOR_TYPE_ADDR, MOTOR_TYPE_JGB37_520_12V_110RPM)
        time.sleep(0.01)
        bus.write_byte_data(I2C_ADDR, MOTOR_ENCODER_POLARITY_ADDR, 0)
    except Exception as e:
        print("I2C configuration failed. Check wiring and I2C address:", e)
        return

    # Register the GPIO callbacks so the background edge detection can update the pulse widths.
    cb1 = lgpio.callback(h, THROTTLE_PIN, lgpio.BOTH_EDGES, pwm_callback)
    cb2 = lgpio.callback(h, STEERING_PIN, lgpio.BOTH_EDGES, pwm_callback)

    print("Running... Move controller sticks.")

    try:
        while True:
            throttle_pwm = pulse_widths[THROTTLE_PIN]
            steering_pwm = pulse_widths[STEERING_PIN]

            # Map the RC pulse widths into actuator values suitable for the chassis.
            throttle = map_value(throttle_pwm, 1000, 2000, -50, 50)
            steering = map_value(steering_pwm, 1000, 2000, -30, 30)

            # Apply a small deadband so the motors remain quiet around the neutral position.
            if abs(throttle) < 5:
                throttle = 0
            if abs(steering) < 5:
                steering = 0

            # Differential-drive mixing: steering modifies the left/right motor balance.
            left_motor = throttle + steering
            right_motor = throttle - steering

            # Clamp the final command to the motor driver's safe operating range.
            left_motor = constrain(left_motor, -50, 50)
            right_motor = constrain(right_motor, -50, 50)

            # Format for I2C (Assuming driver expects: Left1, Right1, Left2, Right2)
            motors = [
                signed_to_byte(left_motor),
                signed_to_byte(right_motor),
                signed_to_byte(left_motor),
                signed_to_byte(right_motor)
            ]
            
            # Send speeds to motor driver via I2C
            try:
                bus.write_i2c_block_data(I2C_ADDR, MOTOR_FIXED_SPEED_ADDR, motors)
            except Exception as e:
                print("I2C Write Error:", e)

            # Console output for debugging and manual tuning.
            print(f"\rT_PWM:{throttle_pwm:4d} S_PWM:{steering_pwm:4d} | "
                  f"T:{throttle:3d} S:{steering:3d} | "
                  f"L:{left_motor:3d} R:{right_motor:3d}", end="")

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nStopping motors...")
        try:
            # Send a zero-speed command on shutdown as a safety fallback.
            bus.write_i2c_block_data(I2C_ADDR, MOTOR_FIXED_SPEED_ADDR, [0, 0, 0, 0])
        except Exception:
            pass

    finally:
        # Release the GPIO callbacks and close the bus cleanly.
        cb1.cancel()
        cb2.cancel()
        lgpio.gpiochip_close(h)
        bus.close()


if __name__ == "__main__":
    main()