import lgpio
import time

# Configuration
CHIP = 0  # Default GPIO chip
CH1_PIN = 17
CH2_PIN = 27

# Open the GPIO chip
h = lgpio.gpiochip_open(CHIP)

# 1. Claim lines for alerts (this automatically configures them as inputs for edge detection)
lgpio.gpio_claim_alert(h, CH1_PIN, lgpio.BOTH_EDGES)
lgpio.gpio_claim_alert(h, CH2_PIN, lgpio.BOTH_EDGES)

# 2. Set the debounce filters to ignore noise (in microseconds)
lgpio.gpio_set_debounce_micros(h, CH1_PIN, 10)
lgpio.gpio_set_debounce_micros(h, CH2_PIN, 10)

# Storage for pulse widths
pw_ch1 = 1500
pw_ch2 = 1500

# Initialize tracking variables
last_tick = {}
last_level = {}

# Callback function
def rc_callback(chip, pin, level, tick):
    global pw_ch1, pw_ch2, last_tick, last_level
    
    if pin not in last_tick:
        last_tick[pin] = 0
        last_level[pin] = 0

    if last_level[pin] == 0 and level == 1:
        # Rising Edge: Record the starting timestamp
        last_tick[pin] = tick
        
    elif last_level[pin] == 1 and level == 0:
        # Falling Edge: Calculate width in microseconds
        # 3. lgpio ticks are in nanoseconds, so we subtract and divide by 1000
        width = int((tick - last_tick[pin]) / 1000)
        
        # Optional but recommended: Filter out extreme outliers (RC PWM is typically 1000us - 2000us)
        if 900 <= width <= 2100:
            if pin == CH1_PIN:
                pw_ch1 = width
            elif pin == CH2_PIN:
                pw_ch2 = width
    
    last_level[pin] = level

# 4. Register callbacks
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
    # Clean up callbacks and close the chip
    cb1.cancel()
    cb2.cancel()
    lgpio.gpiochip_close(h)
