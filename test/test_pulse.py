# mode2_mode3_pulse_ms.py
# -*- coding: utf-8 -*-
import time
import random
import threading
import argparse

import spidev
import RPi.GPIO as GPIO

# ---------- MCP3008 ----------
def setup_spi():
    spi = spidev.SpiDev()
    spi.open(0, 0)              # /dev/spidev0.0  (CE0=GPIO8)
    spi.max_speed_hz = 1_000_000
    return spi

def read_mcp3008(spi, ch: int) -> int:
    val = spi.xfer2([1, (8 + ch) << 4, 0])
    return ((val[1] & 3) << 8) + val[2]

def read_voltage(spi, ch: int) -> float:
    raw = read_mcp3008(spi, ch)
    return raw * 3.3 / 1023.0

# ---------- SG90 (RPi.GPIO PWM) ----------
def angle_to_duty(angle: float) -> float:
    # SG90 常見 mapping：0°~180° -> duty 約 2.5~12.5
    return 2.5 + (float(angle) / 180.0) * 10.0

class ServoRunner:
    def __init__(self, pin=23, min_a=30.0, max_a=150.0, center=90.0):
        self.pin = pin
        self.min_a = min_a
        self.max_a = max_a
        self.center = center

        self._lock = threading.Lock()
        self._mode = 2
        self._running = False

        # state
        self._angle = center
        self._dir = 1

        # mode2 params
        self.m2_min = max(45.0, self.min_a)
        self.m2_max = min(135.0, self.max_a)

        # mode3 params
        self._target = center
        self._step_deg = 4.0
        self._step_dt = 0.02

    def start(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        self.pwm = GPIO.PWM(self.pin, 50)  # 50Hz
        self.pwm.start(0)
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        with self._lock:
            self._running = False
        try:
            self.set_angle(self.center)
            time.sleep(0.1)
        except Exception:
            pass
        try:
            self.pwm.ChangeDutyCycle(0)
            self.pwm.stop()
        except Exception:
            pass

    def set_mode(self, mode: int):
        with self._lock:
            self._mode = int(mode)
            # reset state
            self._angle = self.center
            self._dir = 1
            if self._mode == 3:
                self._pick_new_target()

    def set_angle(self, angle: float):
        a = max(self.min_a, min(self.max_a, float(angle)))
        duty = angle_to_duty(a)
        # 重點：不做 sleep(0.2)；用連續 PWM + 小步更新達到平滑
        self.pwm.ChangeDutyCycle(duty)
        self._angle = a

    def _pick_new_target(self):
        self._target = random.uniform(self.min_a, self.max_a)
        self._step_deg = random.uniform(2.0, 8.0)       # 速度（每步幾度）
        self._step_dt  = random.uniform(0.01, 0.04)     # 節奏（每步間隔秒）

    def _loop(self):
        next_t = time.perf_counter()
        while True:
            with self._lock:
                if not self._running:
                    break
                mode = self._mode

            if mode == 1:
                self.set_angle(self.center)
                time.sleep(0.05)
                continue

            if mode == 2:
                # 45 <-> 135 等速擺動（小步進讓它平滑）
                step_deg = 2.0
                step_dt  = 0.02
                a = self._angle + self._dir * step_deg
                if a >= self.m2_max:
                    a = self.m2_max
                    self._dir = -1
                elif a <= self.m2_min:
                    a = self.m2_min
                    self._dir = 1
                self.set_angle(a)
                time.sleep(step_dt)
                continue

            if mode == 3:
                # 30~150 隨機目標 + 隨機速度/節奏
                diff = self._target - self._angle
                if abs(diff) <= self._step_deg:
                    self.set_angle(self._target)
                    self._pick_new_target()
                else:
                    step = self._step_deg if diff > 0 else -self._step_deg
                    self.set_angle(self._angle + step)
                time.sleep(self._step_dt)
                continue

# ---------- Sensor sampler + pulse width ----------
class PulseMeasurer:
    def __init__(self, spi, ch=0, sample_hz=800.0, threshold=1.55, holdoff_ms=300.0):
        self.spi = spi
        self.ch = ch
        self.dt = 1.0 / max(1.0, sample_hz)
        self.threshold = float(threshold)
        self.holdoff_s = float(holdoff_ms) / 1000.0

        self._lock = threading.Lock()
        self._running = False

        # stats
        self.eff_hz = 0.0
        self.max_v = 0.0
        self.min_v = 99.0

        # pulse detection
        self.in_zone = False
        self.t_enter = 0.0
        self.peak_v = 0.0
        self.last_event_t = 0.0

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        with self._lock:
            self._running = False

    def _loop(self):
        t0 = time.perf_counter()
        n = 0
        next_t = time.perf_counter()

        while True:
            with self._lock:
                if not self._running:
                    break

            now = time.perf_counter()
            v = read_voltage(self.spi, self.ch)

            # stats
            if v > self.max_v: self.max_v = v
            if v < self.min_v: self.min_v = v

            # holdoff
            if (now - self.last_event_t) >= self.holdoff_s:
                above = (v >= self.threshold)

                if above and (not self.in_zone):
                    self.in_zone = True
                    self.t_enter = now
                    self.peak_v = v

                elif above and self.in_zone:
                    if v > self.peak_v:
                        self.peak_v = v

                elif (not above) and self.in_zone:
                    t_exit = now
                    dur_ms = (t_exit - self.t_enter) * 1000.0
                    self.last_event_t = now
                    self.in_zone = False
                    print(f"EVENT width={dur_ms:6.1f} ms | peak={self.peak_v:.3f} V")

            n += 1
            if (now - t0) >= 2.0:
                self.eff_hz = n / (now - t0)
                print(f"[INFO] effective_rate ≈ {self.eff_hz:.0f} Hz | v_now={v:.3f}V | v_max={self.max_v:.3f}V")
                t0 = now
                n = 0

            # 精準節拍：不是固定 sleep(0.2)，而是用 next_t 控制小間隔
            next_t += self.dt
            sleep_s = next_t - time.perf_counter()
            if sleep_s > 0:
                time.sleep(sleep_s)
            else:
                # 落後太多就重置，避免越積越慢
                next_t = time.perf_counter()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", type=int, default=2, choices=[1,2,3], help="servo mode 1/2/3")
    ap.add_argument("--seconds", type=float, default=20.0, help="run seconds")
    ap.add_argument("--ch", type=int, default=0, help="MCP3008 channel")
    ap.add_argument("--hz", type=float, default=800.0, help="sensor sample rate Hz")
    ap.add_argument("--threshold", type=float, default=1.55, help="event threshold V")
    ap.add_argument("--holdoff_ms", type=float, default=300.0, help="debounce/holdoff ms")
    args = ap.parse_args()

    spi = setup_spi()
    servo = ServoRunner(pin=23, min_a=30.0, max_a=150.0, center=90.0)
    meas = PulseMeasurer(spi, ch=args.ch, sample_hz=args.hz, threshold=args.threshold, holdoff_ms=args.holdoff_ms)

    try:
        servo.start()
        servo.set_mode(args.mode)

        meas.start()

        print(f"RUN mode={args.mode} for {args.seconds:.1f}s | threshold={args.threshold:.3f}V | sample_hz={args.hz:.0f}")
        t_end = time.time() + args.seconds
        while time.time() < t_end:
            time.sleep(0.2)

    finally:
        meas.stop()
        servo.stop()
        spi.close()
        try:
            GPIO.cleanup()
        except Exception:
            pass

        print("\nDONE")
        print(f"max_v={meas.max_v:.3f}V | min_v={meas.min_v:.3f}V | last_eff_rate≈{meas.eff_hz:.0f}Hz")

if __name__ == "__main__":
    main()
