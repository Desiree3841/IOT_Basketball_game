#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import json
import urllib.request

URL = "http://127.0.0.1:5000/status"

def fetch_status():
    # 帶 ts 避免任何中間快取
    url = f"{URL}?ts={int(time.time()*1000)}"
    with urllib.request.urlopen(url, timeout=1.5) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    print("開始讀取 /status ...（按 Ctrl+C 結束）")
    while True:
        try:
            s = fetch_status()
            ts = s.get("timestamp", "-")
            baseline_ready = s.get("baseline_ready", False)
            baseline_v = float(s.get("baseline_v", 0.0))
            thr_v = float(s.get("goal_threshold_v", 0.0))
            sensor_v = float(s.get("sensor_v", 0.0))

            print(
                f"{ts} | baseline_ready={baseline_ready} "
                f"| baseline_v={baseline_v:.3f}V "
                f"| goal_threshold_v={thr_v:.3f}V "
                f"| sensor_v={sensor_v:.3f}V"
            )
        except Exception as e:
            print("讀取失敗：", e)

        time.sleep(0.2)

if __name__ == "__main__":
    main()
