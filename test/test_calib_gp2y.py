#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from statistics import mean
from gpiozero import MCP3008

CHANNEL = 0          # GP2Y 接在 CH0
SAMPLES = 50         # 每階段取樣次數
INTERVAL = 0.05      # 每筆間隔時間（秒）

def measure_phase(desc: str):
    adc = MCP3008(channel=CHANNEL)
    print(f"=== {desc} 測量階段 ===")
    values = []
    for i in range(SAMPLES):
        v = adc.value          # 0.0 ~ 1.0
        values.append(v)
        print(f"{i+1:02d}: value={v:.4f}")
        time.sleep(INTERVAL)
    avg = mean(values)
    print(f"{desc} 平均 value = {avg:.4f}")
    print()
    return avg

def main():
    print("GP2Y0A51SK0F 兩階段量測工具")
    print("STEP 1：保持沒有球通過，感測器只看到籃框內壁")
    input("準備好後按 Enter 開始量測背景值...")

    bg_avg = measure_phase("【背景值（無球）】")

    print("STEP 2：讓球停在『你認為是進球位置』附近（感測區內）")
    print("例如：球卡在籃框中心附近，或拿手固定在 GP2Y 前方 5~10cm 處")
    input("準備好後按 Enter 開始量測進球值...")

    hit_avg = measure_phase("【進球值（有球）】")

    print("=== 測量結果 ===")
    print(f"背景平均 value（無球） = {bg_avg:.4f}")
    print(f"進球平均 value（有球） = {hit_avg:.4f}")

    # 建議 threshold：取兩者中間
    threshold = (bg_avg + hit_avg) / 2.0
    print(f"\n建議 GOAL_THRESHOLD（介於兩者中間） ≈ {threshold:.4f}")
    print("請把這個數字填回你的 basketball_game.py 裡的 GOAL_THRESHOLD 變數。")
    print("\n提醒：之後可以再微調：")
    print("  - 若太容易誤判為進球 → 門檻往『背景值』那邊拉近一點")
    print("  - 若太難判到進球 → 門檻往『進球值』那邊拉近一點")

if __name__ == "__main__":
    main()
