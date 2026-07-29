/*
===============================================================================
Project      : Emergency Data Mule
Module       : RC-to-I2C Motor Controller Bridge
Author(s)    : Ricardo Rodrigues and Carolina Antunes
Institution  : Instituto Superior Tecnico
Academic Year: 2025/2026
Version       : 1.0
Last Updated  : 29 July 2026

Description:
    Arduino sketch that translates RC receiver PWM signals into commands for a
    manufacturer-supplied motor controller over I2C. The code reads throttle
    and steering inputs, mixes them into left/right motor commands, and sends
    the resulting values to the controller using the vendor-specific register
    protocol.

===============================================================================

System Role
-----------

This sketch forms the low-level actuation interface of the rover. It converts
operator input into motion commands so the vehicle can translate and turn in
response to the remote-control inputs.

===============================================================================
*/

#include <Wire.h>

// I2C address and register map for the motor controller board.
#define I2C_ADDR 0x34
#define MOTOR_FIXED_SPEED_ADDR 0x33
#define MOTOR_TYPE_ADDR 0x14
#define MOTOR_ENCODER_POLARITY_ADDR 0x15

#define MOTOR_TYPE_JGB37_520_12V_110RPM 3

// RC receiver input pins. These carry PWM signals from the throttle and steering channels.
#define THROTTLE_PIN 2
#define STEERING_PIN 3
// Optional auxiliary pins are left unused in this simplified bridge sketch.
// #define AUX1_PIN 4
// #define AUX2_PIN 5

// Buffer used to send the final left/right motor values to the controller.
int8_t motors[4] = {0, 0, 0, 0};

// Controller configuration values requested by the motor driver hardware.
uint8_t MotorType = MOTOR_TYPE_JGB37_520_12V_110RPM;
uint8_t MotorEncoderPolarity = 0;

// Send a byte array to the motor controller using the manufacturer register protocol.
bool WireWriteDataArray(uint8_t reg, uint8_t *val, unsigned int len)
{
    Wire.beginTransmission(I2C_ADDR);
    Wire.write(reg);

    for(int i=0;i<len;i++)
    {
        Wire.write(val[i]);
    }

    if(Wire.endTransmission()!=0)
        return false;

    return true;
}

void setup()
{
    // Initialize the I2C bus and serial console used for debugging.
    Wire.begin();
    Serial.begin(9600);

    // Configure the RC input pins.
    pinMode(THROTTLE_PIN, INPUT);
    pinMode(STEERING_PIN, INPUT);

    // Optional auxiliary pins are not used for the current control loop.
    // pinMode(AUX1_PIN, INPUT);
    // pinMode(AUX2_PIN, INPUT);

    delay(200);

    // Configure the motor controller with the hardware-specific settings.
    WireWriteDataArray(MOTOR_TYPE_ADDR, &MotorType, 1);
    delay(5);
    WireWriteDataArray(MOTOR_ENCODER_POLARITY_ADDR, &MotorEncoderPolarity, 1);
}

void loop()
{
    // Read the latest RC PWM values from the receiver.
    int throttlePWM = pulseIn(THROTTLE_PIN, HIGH, 25000);
    int steeringPWM = pulseIn(STEERING_PIN, HIGH, 25000);

    // Fallback values keep the rover stable if the receiver drops out briefly.
    if (throttlePWM == 0) throttlePWM = 1500;
    if (steeringPWM == 0) steeringPWM = 1500;

    // Convert the receiver PWM range into a compact motor command range.
    int throttle = map(throttlePWM, 1000, 2000, -50, 50);
    int steering = map(steeringPWM, 1000, 2000, -30, 30);

    // Deadband to avoid jitter when the sticks are centered.
    if (abs(throttle) < 5) throttle = 0;
    if (abs(steering) < 5) steering = 0;

    // Mix throttle and steering into differential drive commands for the left and right motors.
    int leftMotor = throttle + steering;
    int rightMotor = throttle - steering;

    leftMotor = constrain(leftMotor, -50, 50);
    rightMotor = constrain(rightMotor, -50, 50);

    // Write the mixed motor values into the controller's command buffer.
    motors[0] = leftMotor;
    motors[1] = rightMotor;
    motors[2] = leftMotor;
    motors[3] = rightMotor;

    // Send the final command packet to the motor controller over I2C.
    WireWriteDataArray(MOTOR_FIXED_SPEED_ADDR, (uint8_t*)motors, 4);

    // Print debug information to the serial console for tuning and troubleshooting.
    Serial.print("Throttle: ");
    Serial.print(throttle);
    Serial.print(" Steering: ");
    Serial.print(steering);
    Serial.print(" Left: ");
    Serial.print(leftMotor);
    Serial.print(" Right: ");
    Serial.println(rightMotor);

    delay(20);
}