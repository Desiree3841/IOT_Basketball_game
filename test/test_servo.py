# servo_to_90.py
# -*- coding: utf-8 -*-

import RPi.GPIO as GPIO
import time

SERVO_PIN = 23      # 你的 SG90 橘線接在 GPIO 23
FREQ_HZ   = 50      # SG90 一般用 50Hz PWM

def angle_to_duty(angle: float) -> float:
    """
    SG90 常見對應：
    0 度  ~ 2.5% duty
    180 度 ~ 12.5% duty
    中間線性內插
    """
    angle = max(0.0, min(180.0, float(angle)))
    return 2.5 + (angle / 180.0) * 10.0

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(SERVO_PIN, GPIO.OUT)

    pwm = GPIO.PWM(SERVO_PIN, FREQ_HZ)
    pwm.start(0)

    try:
        target_angle = 90.0
        duty = angle_to_duty(target_angle)
        print(f"Move servo on GPIO {SERVO_PIN} to {target_angle}° (duty={duty:.2f}%)")

        # 先給一小段 PWM，讓它轉到 90 度
        pwm.ChangeDutyCycle(duty)
        time.sleep(0.6)   # 讓它有時間轉過去

        # 如果你希望「保持」在 90 度不動，可以註解掉下面這行
        # 但長時間上 PWM 伺服會比較熱：
        pwm.ChangeDutyCycle(0)

        input("已轉到約 90 度，確認完按 Enter 結束程式...")

    finally:
        pwm.stop()
        GPIO.cleanup()
        print("GPIO cleanup 完成，程式結束。")

if __name__ == "__main__":
    main()
