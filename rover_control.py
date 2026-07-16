#!/usr/bin/env python3

from smbus2 import SMBus
import lgpio
import time

# =========================
# I2C Configuration
# =========================
I2C_ADDR = 0x34
MOTOR_FIXED_SPEED_ADDR = 0x33
MOTOR_TYPE_ADDR = 0x14
MOTOR_ENCODER_POLARITY_ADDR = 0x15

MOTOR_TYPE_JGB37_520_12V_110RPM = 3

# =========================
# GPIO Configuration
# =========================
CHIP = 0
THROTTLE_PIN = 17
STEERING_PIN = 27

h = lgpio.gpiochip_open(CHIP)

# Claim as alerts for edge detection and set debounce
lgpio.gpio_claim_alert(h, THROTTLE_PIN, lgpio.BOTH_EDGES)
lgpio.gpio_claim_alert(h, STEERING_PIN, lgpio.BOTH_EDGES)
lgpio.gpio_set_debounce_micros(h, THROTTLE_PIN, 10)
lgpio.gpio_set_debounce_micros(h, STEERING_PIN, 10)

# =========================
# Global Variables
# =========================
# Defaulting to 1500 since your range is 1000-2000
pulse_widths = {
    THROTTLE_PIN: 1500,
    STEERING_PIN: 1500
}

# =========================
# Utility Functions
# =========================
def map_value(x, in_min, in_max, out_min, out_max):
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

def constrain(x, minimum, maximum):
    return max(minimum, min(maximum, x))

def signed_to_byte(value):
    # Converts signed integer to two's complement byte for I2C
    return value & 0xFF

# =========================
# PWM Input Callback
# =========================
rise_ticks = {}

def pwm_callback(chip, gpio, level, tick):
    if level == 1:
        rise_ticks[gpio] = tick
    elif level == 0:
        if gpio in rise_ticks:
            # lgpio ticks are in nanoseconds, convert to microseconds
            width = int((tick - rise_ticks[gpio]) / 1000)
            # Filter slightly wider than your 1000-2000 range to catch extremes safely
            if 700 <= width <= 2100:
                pulse_widths[gpio] = width

# =========================
# Main Program
# =========================
def main():
    bus = SMBus(1)

    print("Configuring motor controller...")
    try:
        # Initialize the motor driver over I2C
        bus.write_byte_data(I2C_ADDR, MOTOR_TYPE_ADDR, MOTOR_TYPE_JGB37_520_12V_110RPM)
        time.sleep(0.01)
        bus.write_byte_data(I2C_ADDR, MOTOR_ENCODER_POLARITY_ADDR, 0)
    except Exception as e:
        print("I2C configuration failed. Check wiring and I2C address:", e)
        return

    # Register callbacks
    cb1 = lgpio.callback(h, THROTTLE_PIN, lgpio.BOTH_EDGES, pwm_callback)
    cb2 = lgpio.callback(h, STEERING_PIN, lgpio.BOTH_EDGES, pwm_callback)

    print("Running... Move controller sticks.")

    try:
        while True:
            throttle_pwm = pulse_widths[THROTTLE_PIN]
            steering_pwm = pulse_widths[STEERING_PIN]
            
            # Map values based on your new 1000-2000 range
            throttle = map_value(throttle_pwm, 1000, 2000, -50, 50)
            steering = map_value(steering_pwm, 1000, 2000, -30, 30)

            # Deadband to prevent motor buzzing when sticks are near neutral
            if abs(throttle) < 5:
                throttle = 0
            if abs(steering) < 5:
                steering = 0

            # Differential drive mixing
            left_motor = throttle + steering
            right_motor = throttle - steering

            # Constrain to motor limits
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

            # Console output for debugging
            print(f"\rT_PWM:{throttle_pwm:4d} S_PWM:{steering_pwm:4d} | "
                  f"T:{throttle:3d} S:{steering:3d} | "
                  f"L:{left_motor:3d} R:{right_motor:3d}", end="")

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nStopping motors...")
        try:
            # Send zero speed to all motors on exit
            bus.write_i2c_block_data(I2C_ADDR, MOTOR_FIXED_SPEED_ADDR, [0, 0, 0, 0])
        except:
            pass

    finally:
        cb1.cancel()
        cb2.cancel()
        lgpio.gpiochip_close(h)
        bus.close()

if __name__ == "__main__":
    main()