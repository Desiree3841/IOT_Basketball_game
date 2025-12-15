#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from gpiozero import Buzzer, Button

BUZZER_PIN = 25
BUTTON_PIN = 17

def beep_once(buzzer: Buzzer):
    buzzer.on()
    time.sleep(0.15)
    buzzer.off()

def on_button_pressed():
    print("按鈕被按下，嗶嗶兩聲測試")
    beep_once(buzzer)
    time.sleep(0.15)
    beep_once(buzzer)

buzzer = Buzzer(BUZZER_PIN)
button = Button(BUTTON_PIN, pull_up=True)

def main():
    button.when_pressed = on_button_pressed
    print("按 Start 按鈕測試蜂鳴器，Ctrl+C 結束")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("結束")
        buzzer.off()

if __name__ == "__main__":
    main()
