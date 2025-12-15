#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import RPi.GPIO as GPIO

BUZZER_PIN = 25   # 蜂鳴器：BCM 25（實體 Pin 22）
BUTTON_PIN = 17   # 按鈕：BCM 17（實體 Pin 11）

def beep2():
    for _ in range(2):
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(0.15)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        time.sleep(0.15)

def main():
    GPIO.setmode(GPIO.BCM)

    # 蜂鳴器腳位：輸出，預設 LOW
    GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)

    # 按鈕腳位：輸入 + 內建上拉電阻
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    print("按鈕 + 蜂鳴器測試程式啟動")
    print("請確定：")
    print("  - 蜂鳴器長腳 → BCM25 (Pin 22)，短腳 → GND")
    print("  - 按鈕一腳 → BCM17 (Pin 11)，另一腳 → GND")
    print("按下按鈕時，終端機會顯示 'Button pressed!' 並嗶嗶兩聲")
    print("Ctrl+C 結束\n")

    try:
        while True:
            # 讀按鈕狀態：PUD_UP → 放開為 HIGH，按下為 LOW
            state = GPIO.input(BUTTON_PIN)

            if state == GPIO.LOW:
                print("Button pressed!")
                beep2()
                # 簡單防抖，避免一次按太久狂觸發
                time.sleep(0.3)
            else:
                # 不按時不要一直刷畫面，稍微睡一下
                time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n結束測試，關閉蜂鳴器並清除 GPIO 設定")
    finally:
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        GPIO.cleanup()

if __name__ == "__main__":
    main()
