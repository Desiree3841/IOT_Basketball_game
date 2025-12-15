#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sensor_event_test.py
MCP3008(CH0) + GP2Y 類比電壓事件偵測（hysteresis + holdoff）
設定：entry=2.00V, release=1.70V, holdoff=250ms
"""

import time
from datetime import datetime

try:
    import spidev
except Exception as e:
    raise RuntimeError("找不到 spidev，請確認是在 Raspberry Pi 且已啟用 SPI。") from e


# ====== 硬體設定 ======
SPI_BUS = 0
SPI_DEV = 0          # CE0(GPIO8)
ADC_CH = 0           # MCP3008 CH0
VREF = 3.3
ADC_MAX = 1023

# ====== 事件門檻（你指定） ======
ENTRY_V = 2.00
RELEASE_V = 1.70
HOLDOFF_MS = 250

# SPI 速度（可依需要調整）
SPI_MAX_HZ = 1_000_000


def setup_spi():
    spi = spidev.SpiDev()
    spi.open(SPI_BUS, SPI_DEV)
    spi.max_speed_hz = SPI_MAX_HZ
    return spi


def read_adc_raw(spi, ch: int) -> int:
    # MCP3008 讀法： [1, (8+ch)<<4, 0]
    r = spi.xfer2([1, (8 + ch) << 4, 0])
    return ((r[1] & 3) << 8) + r[2]


def read_voltage(spi, ch: int) -> float:
    raw = read_adc_raw(spi, ch)
    return raw * VREF / ADC_MAX


def main():
    spi = setup_spi()

    holdoff_s = HOLDOFF_MS / 1000.0

    in_event = False
    event_start_ts = 0.0
    peak_v = 0.0

    next_allowed_ts = 0.0  # holdoff 控制：在這之前不允許新事件

    # 取樣率統計
    cnt = 0
    rate_t0 = time.perf_counter()

    print(f"START | entry={ENTRY_V:.2f}V | release={RELEASE_V:.2f}V | holdoff={HOLDOFF_MS}ms")
    print("按 Ctrl+C 結束。\n")

    try:
        while True:
            now = time.perf_counter()
            v = read_voltage(spi, ADC_CH)
            cnt += 1

            # 每秒印一次有效取樣率
            if (now - rate_t0) >= 1.0:
                eff_rate = cnt / (now - rate_t0)
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"{ts} | eff_rate≈{eff_rate:.0f}Hz | v={v:.3f}V")
                cnt = 0
                rate_t0 = now

            # ====== 事件偵測（hysteresis + holdoff） ======
            if not in_event:
                if (now >= next_allowed_ts) and (v >= ENTRY_V):
                    in_event = True
                    event_start_ts = now
                    peak_v = v
            else:
                if v > peak_v:
                    peak_v = v

                # 低於 release 視為事件結束
                if v <= RELEASE_V:
                    width_ms = (now - event_start_ts) * 1000.0
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    print(f"EVENT | {ts} | peak_v={peak_v:.3f}V | width_ms={width_ms:.1f}ms")

                    in_event = False
                    next_allowed_ts = now + holdoff_s

    except KeyboardInterrupt:
        print("\nSTOP (Ctrl+C)")

    finally:
        try:
            spi.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
