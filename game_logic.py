# game_logic.py
# -*- coding: utf-8 -*-
"""
投籃機核心邏輯（Mode2/Mode3：來回掃動；Mode3 不定速）

本版修正重點（針對你遇到的「伺服器卡 90 度、不照 Mode2/3 動」）：
1) 【致命 bug 修正】servo 計時全部統一用 time.monotonic()
   - 原版 servo_set_mode() 用 time.time()、servo_tick() 用 time.monotonic()
   - 會導致 (now - last_update) 永遠為負值 → servo_tick 永遠 return → 伺服器卡住
2) Mode2：45°~135° 等速來回（平滑：小步長 + 50Hz 更新）
3) Mode3：30°~150° 隨機目標 + 隨機速度（不定速、更平滑、稍快）
4) 開始/結束/STOP：回到 90°
5) set_servo_angle：同 duty 不重複寫入，降低抖動與 CPU 壓力
"""

import os
import time
import json
import threading
import random
from datetime import datetime

# -------------------------
# 環境檢查（GPIO/SPI 常需 root）
# -------------------------
try:
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("⚠️ 建議用 sudo 執行：sudo python3 app.py（GPIO / SPI 通常需要 root 權限）")
except Exception:
    pass

# -------------------------
# GPIO / SPI
# -------------------------
try:
    import RPi.GPIO as GPIO
    import spidev
    _ON_RPI = True
except Exception:
    _ON_RPI = False

    class _DummyGPIO:
        BCM = 0
        OUT = 0
        IN = 0
        LOW = 0
        HIGH = 1
        PUD_UP = 0

        def setwarnings(self, *a, **k): pass
        def setmode(self, *a, **k): pass
        def setup(self, *a, **k): pass
        def output(self, *a, **k): pass
        def input(self, *a, **k): return 1
        def PWM(self, *a, **k):
            class _P:
                def start(self, *a, **k): pass
                def ChangeDutyCycle(self, *a, **k): pass
                def stop(self, *a, **k): pass
            return _P()

    class _DummySPI:
        def open(self, *a, **k): pass
        def xfer2(self, x): return [0, 0, 0]
        max_speed_hz = 0

    GPIO = _DummyGPIO()
    spidev = type("spidev", (), {"SpiDev": lambda: _DummySPI()})

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# =========================
# 常數 / 腳位
# =========================
BUZZER_PIN = 25

SERVO_PIN = 23
SERVO_MIN_ANGLE = 30.0
SERVO_MAX_ANGLE = 150.0
SERVO_CENTER_ANGLE = 90.0  # 你確認在 30~150 之間 90 度是安全中心

# Mode2：你指定 45~135 度等速來回
MODE2_MIN_ANGLE = 45.0
MODE2_MAX_ANGLE = 135.0
MODE2_TICK_INTERVAL = 0.020   # 50Hz（與 50Hz PWM 同步，平滑又不抖）
MODE2_SPEED_DPS = 110.0       # deg/sec（等速）

# Mode3：30~150 不定速（隨機目標/隨機速度）
MODE3_MIN_ANGLE = 30.0
MODE3_MAX_ANGLE = 150.0
MODE3_TICK_INTERVAL = 0.020   # 50Hz
MODE3_SPEED_MIN_DPS = 120.0   # 稍快一點
MODE3_SPEED_MAX_DPS = 170.0
MODE3_TARGET_MARGIN_DEG = 1.0

START_BUTTON_PIN = 17

# MCP3008 / IR 參數
MCP3008_CHANNEL = 0
GOAL_ENTRY_V = 2.00
GOAL_RELEASE_V = 1.70
GOAL_HOLDOFF_MS = 250
GOAL_MIN_WIDTH_MS = 5.0

# LCD 節流
LCD_FPS = 6.0

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "score_history.json")
CONFIG_FILE = os.path.join(BASE_DIR, "game_config.json")

# =========================
# LCD（20×4 I2C）
# =========================
class LCDManager:
    def __init__(self):
        self.available = False
        self._lock = threading.Lock()
        self._last_lines = ["", "", "", ""]
        self._last_flush_ts = 0.0
        try:
            import I2C_LCD_driver
            self._lcd = I2C_LCD_driver.lcd()
            self.available = True
        except Exception as e:
            print("⚠️ LCD driver not available, fallback to console:", e)
            self._lcd = None
            self.available = False

    def show(self, l1="", l2="", l3="", l4="", force=False):
        now = time.monotonic()
        if not force and (now - self._last_flush_ts) < (1.0 / LCD_FPS):
            return

        lines = [
            (l1 or "")[:20].ljust(20),
            (l2 or "")[:20].ljust(20),
            (l3 or "")[:20].ljust(20),
            (l4 or "")[:20].ljust(20),
        ]

        with self._lock:
            if not force and lines == self._last_lines:
                return
            self._last_lines = lines
            self._last_flush_ts = now

            if self.available:
                try:
                    for i, s in enumerate(lines, start=1):
                        self._lcd.lcd_display_string(s, i)
                except Exception as e:
                    print("⚠️ LCD write error:", e)
            else:
                print("[LCD]")
                for s in lines:
                    print(s)

_lcdm = LCDManager()

def lcd_show_4_lines(l1="", l2="", l3="", l4="", force=False):
    _lcdm.show(l1, l2, l3, l4, force=force)

# =========================
# 蜂鳴器
# =========================
GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.output(BUZZER_PIN, GPIO.LOW)

SOUND_MODE = "beep"       # "beep" / "cheer"
SOUND_ENABLED = True      # 靜音立即生效

def _buzzer_on():
    GPIO.output(BUZZER_PIN, GPIO.HIGH)

def _buzzer_off():
    GPIO.output(BUZZER_PIN, GPIO.LOW)

def _short_beep():
    if not SOUND_ENABLED:
        return
    _buzzer_on()
    time.sleep(0.10)
    _buzzer_off()
    time.sleep(0.05)

def _long_beep():
    if not SOUND_ENABLED:
        return
    _buzzer_on()
    time.sleep(0.35)
    _buzzer_off()
    time.sleep(0.05)

def play_goal_sound():
    """依 SOUND_MODE 播放進球音效；可在遊戲中切換模式。"""
    if not SOUND_ENABLED:
        return
    if SOUND_MODE == "beep":
        for _ in range(2):
            _buzzer_on(); time.sleep(0.10)
            _buzzer_off(); time.sleep(0.10)
    else:
        pattern = [0.05, 0.05, 0.05, 0.05, 0.10]
        for d in pattern:
            _buzzer_on(); time.sleep(d)
            _buzzer_off(); time.sleep(0.03)

# =========================
# SG90 舵機 & 模式控制（方法二：PWM 不歸零）
# =========================
GPIO.setup(SERVO_PIN, GPIO.OUT)
servo_pwm = GPIO.PWM(SERVO_PIN, 50)  # 50Hz
servo_pwm.start(0)

_SERVO_LOCK = threading.Lock()

CURRENT_GAME_MODE = 0
servo_current_angle = SERVO_CENTER_ANGLE
servo_last_update = 0.0
servo_direction = 1

# Mode 參數（每次 set_mode 更新）
servo_tick_interval = MODE2_TICK_INTERVAL
servo_step_deg = 2.0

# Mode3 狀態
servo_mode3_target_angle = SERVO_CENTER_ANGLE
servo_mode3_speed_dps = MODE3_SPEED_MIN_DPS

_last_servo_duty = None

def set_servo_angle(angle: float, force: bool = False):
    """
    限制角度在安全範圍，持續輸出 PWM（不歸 0）。
    同 duty 不重複寫入，避免固定角度時一直刷新造成抖動加劇。
    """
    global _last_servo_duty

    a = max(SERVO_MIN_ANGLE, min(SERVO_MAX_ANGLE, float(angle)))
    duty = 2.5 + (a / 180.0) * 10.0

    with _SERVO_LOCK:
        if (not force) and (_last_servo_duty is not None) and (abs(duty - _last_servo_duty) < 0.02):
            return
        servo_pwm.ChangeDutyCycle(duty)
        _last_servo_duty = duty

def _servo_reset_to_center():
    """強制回到 90 度（初始化、STOP、每場結束都呼叫）"""
    global servo_current_angle, servo_last_update, CURRENT_GAME_MODE, servo_direction
    CURRENT_GAME_MODE = 1
    servo_direction = 1
    servo_current_angle = SERVO_CENTER_ANGLE
    set_servo_angle(servo_current_angle, force=True)
    servo_last_update = time.monotonic()

def _mode3_pick_new_target():
    global servo_mode3_target_angle, servo_mode3_speed_dps
    servo_mode3_target_angle = random.uniform(MODE3_MIN_ANGLE, MODE3_MAX_ANGLE)
    servo_mode3_speed_dps = random.uniform(MODE3_SPEED_MIN_DPS, MODE3_SPEED_MAX_DPS)

def servo_set_mode(mode: int):
    """
    Mode1：固定 90°
    Mode2：45°~135° 等速來回
    Mode3：30°~150° 不定速（隨機目標 + 隨機速度）
    """
    global CURRENT_GAME_MODE
    global servo_current_angle, servo_last_update, servo_direction
    global servo_tick_interval, servo_step_deg
    global servo_mode3_target_angle, servo_mode3_speed_dps

    m = int(mode)
    CURRENT_GAME_MODE = m

    now = time.monotonic()  # ✅ 全面統一 monotonic

    if m == 1:
        servo_current_angle = SERVO_CENTER_ANGLE
        servo_direction = 1
        set_servo_angle(servo_current_angle, force=True)
        servo_last_update = now
        return

    if m == 2:
        servo_current_angle = SERVO_CENTER_ANGLE
        servo_direction = 1
        servo_tick_interval = MODE2_TICK_INTERVAL
        servo_step_deg = MODE2_SPEED_DPS * MODE2_TICK_INTERVAL
        set_servo_angle(servo_current_angle, force=True)
        servo_last_update = now
        return

    if m == 3:
        servo_current_angle = SERVO_CENTER_ANGLE
        servo_direction = 1
        servo_tick_interval = MODE3_TICK_INTERVAL
        _mode3_pick_new_target()
        set_servo_angle(servo_current_angle, force=True)
        servo_last_update = now
        return

def servo_tick():
    """
    由遊戲主迴圈高頻呼叫。
    ✅ 這裡只用 time.monotonic()，避免時間基準混用導致伺服器卡死。
    """
    global servo_current_angle, servo_last_update, servo_direction
    global servo_tick_interval, servo_step_deg
    global servo_mode3_target_angle, servo_mode3_speed_dps

    if CURRENT_GAME_MODE == 1:
        return

    now = time.monotonic()

    # 防禦：理論上 monotonic 不倒退，但保留保護
    if now < servo_last_update:
        servo_last_update = now
        return

    if (now - servo_last_update) < servo_tick_interval:
        return

    servo_last_update = now

    if CURRENT_GAME_MODE == 2:
        min_a = MODE2_MIN_ANGLE
        max_a = MODE2_MAX_ANGLE

        servo_current_angle += servo_direction * servo_step_deg
        if servo_current_angle >= max_a:
            servo_current_angle = max_a
            servo_direction = -1
        elif servo_current_angle <= min_a:
            servo_current_angle = min_a
            servo_direction = 1

        set_servo_angle(servo_current_angle)
        return

    if CURRENT_GAME_MODE == 3:
        # 不定速：朝 target 走，走到就換新 target + 新速度
        step = servo_mode3_speed_dps * servo_tick_interval
        diff = servo_mode3_target_angle - servo_current_angle

        if abs(diff) <= max(MODE3_TARGET_MARGIN_DEG, step):
            servo_current_angle = servo_mode3_target_angle
            set_servo_angle(servo_current_angle)
            _mode3_pick_new_target()
            return

        servo_current_angle += (step if diff > 0 else -step)
        servo_current_angle = max(MODE3_MIN_ANGLE, min(MODE3_MAX_ANGLE, servo_current_angle))
        set_servo_angle(servo_current_angle)
        return

# =========================
# MCP3008 / IR 讀取
# =========================
def _setup_spi():
    try:
        spi_dev = spidev.SpiDev()
        spi_dev.open(0, 0)
        spi_dev.max_speed_hz = 1_000_000
        return spi_dev
    except Exception as e:
        print("⚠️ SPI open failed:", e)
        return spidev.SpiDev()  # dummy

_spi = _setup_spi()

def read_adc_channel(ch: int) -> int:
    val = _spi.xfer2([1, (8 + ch) << 4, 0])
    return ((val[1] & 3) << 8) + val[2]

def read_ir_voltage() -> float:
    raw = read_adc_channel(MCP3008_CHANNEL)
    return raw * 3.3 / 1023.0

# =========================
# 設定 & 歷史紀錄
# =========================
def _load_config():
    global GAME1_MODE, GAME2_MODE, GAME_TIME, SOUND_MODE
    if not os.path.exists(CONFIG_FILE):
        return
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        g1 = int(cfg.get("game1_mode", GAME1_MODE))
        g2 = int(cfg.get("game2_mode", GAME2_MODE))
        gt = int(cfg.get("game_time", GAME_TIME))
        sm = str(cfg.get("sound_mode", SOUND_MODE))
        if g1 in (1, 2, 3):
            GAME1_MODE = g1
        if g2 in (1, 2, 3):
            GAME2_MODE = g2
        GAME_TIME = max(3, min(3600, gt))
        if sm in ("beep", "cheer"):
            SOUND_MODE = sm
    except Exception as e:
        print("⚠️ config load error:", e)

def _save_config():
    try:
        cfg = {
            "game1_mode": int(GAME1_MODE),
            "game2_mode": int(GAME2_MODE),
            "game_time": int(GAME_TIME),
            "sound_mode": str(SOUND_MODE),
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("⚠️ config save error:", e)

def _load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def _save_history_all(history_list):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[HISTORY] save error:", e)

def save_round_history_entry(entry: dict):
    history = _load_history()
    history.append(entry)
    _save_history_all(history)

def get_history_summary(max_recent: int = 10):
    history = _load_history()
    recent = history[-max_recent:]
    best = 0
    for h in history:
        try:
            best = max(best, int(h.get("round_total_score", 0)))
        except Exception:
            pass
    return recent, best

def _format_time_now_str() -> str:
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")

# =========================
# 高頻 IR 進球偵測 Thread
# =========================
class GoalDetector(threading.Thread):
    def __init__(self, entry_v: float, release_v: float, holdoff_ms: int, min_width_ms: float):
        super().__init__(daemon=True)
        self.entry_v = float(entry_v)
        self.release_v = float(release_v)
        self.holdoff_s = float(holdoff_ms) / 1000.0
        self.min_width_ms = float(min_width_ms)

        self._lock = threading.Lock()
        self.enabled = False
        self._stop = False

        self.in_zone = False
        self.holdoff_until = 0.0
        self.event_start = 0.0
        self.peak_v = 0.0

        self.seq = 0
        self.last_event_peak_v = 0.0
        self.last_event_width_ms = 0.0
        self.last_event_ts = ""

        self.sensor_v = 0.0
        self.last_eff_rate = 0.0

    def set_enabled(self, flag: bool):
        with self._lock:
            self.enabled = bool(flag)
            self.in_zone = False
            self.holdoff_until = 0.0
            self.event_start = 0.0
            self.peak_v = 0.0

    def consume_since(self, last_seq: int) -> int:
        with self._lock:
            return max(0, self.seq - int(last_seq))

    def get_debug(self):
        with self._lock:
            return {
                "sensor_v": float(self.sensor_v),
                "entry_v": float(self.entry_v),
                "release_v": float(self.release_v),
                "holdoff_ms": int(self.holdoff_s * 1000),
                "min_width_ms": float(self.min_width_ms),
                "event_seq": int(self.seq),
                "last_event_peak_v": float(self.last_event_peak_v),
                "last_event_width_ms": float(self.last_event_width_ms),
                "last_event_ts": str(self.last_event_ts),
                "last_eff_rate_hz": float(self.last_eff_rate),
            }

    def run(self):
        hz_cnt = 0
        hz_t0 = time.perf_counter()
        try:
            while not self._stop:
                t = time.perf_counter()
                try:
                    v = read_ir_voltage()
                except Exception:
                    v = 0.0

                hz_cnt += 1
                if (t - hz_t0) >= 1.0:
                    eff = hz_cnt / (t - hz_t0)
                    hz_cnt = 0
                    hz_t0 = t
                    with self._lock:
                        self.last_eff_rate = eff

                with self._lock:
                    self.sensor_v = v
                    enabled = self.enabled
                    in_zone = self.in_zone
                    holdoff_until = self.holdoff_until
                    event_start = self.event_start
                    peak_v = self.peak_v

                if enabled:
                    if t >= holdoff_until:
                        if (not in_zone) and (v >= self.entry_v):
                            in_zone = True
                            event_start = t
                            peak_v = v
                        elif in_zone:
                            if v > peak_v:
                                peak_v = v
                            if v <= self.release_v:
                                width_ms = (t - event_start) * 1000.0
                                valid = (width_ms >= self.min_width_ms)

                                with self._lock:
                                    if valid:
                                        self.seq += 1
                                        self.last_event_peak_v = float(peak_v)
                                        self.last_event_width_ms = float(width_ms)
                                        self.last_event_ts = datetime.now().strftime(
                                            "%Y-%m-%d %H:%M:%S.%f"
                                        )[:-3]
                                    self.in_zone = False
                                    self.holdoff_until = t + self.holdoff_s
                                    self.event_start = 0.0
                                    self.peak_v = 0.0

                                in_zone = False
                            else:
                                with self._lock:
                                    self.in_zone = True
                                    self.event_start = event_start
                                    self.peak_v = float(peak_v)

                        with self._lock:
                            self.in_zone = in_zone

                time.sleep(0)

        except Exception as e:
            print("⚠️ GoalDetector stopped:", e)

_goal = GoalDetector(GOAL_ENTRY_V, GOAL_RELEASE_V, GOAL_HOLDOFF_MS, GOAL_MIN_WIDTH_MS)

# =========================
# 遊戲狀態
# =========================
STATE_LOCK = threading.Lock()

CURRENT_ROUND = 0
CURRENT_GAME = 0  # 0/1/2

GAME1_MODE = 1
GAME2_MODE = 2
GAME_TIME = 30  # 預設每場 30 秒

GAME_RUNNING = False
PRE_COUNTDOWN_ACTIVE = False
PRE_COUNTDOWN_VALUE = 0

NEXT_GAME_HINT_ACTIVE = False
NEXT_GAME_HINT_MESSAGE = ""

GAME1_SCORE = 0
GAME2_SCORE = 0
CURRENT_GAME_SCORE = 0
ROUND_TOTAL_SCORE = 0
REMAINING_TIME = 0
ROUND_START_TIME_ISO = None

BUTTON_PRESS_COUNT = 0  # 實體按鍵 debug

# =========================
# 倒數邏輯
# =========================
def pre_start_countdown():
    global PRE_COUNTDOWN_ACTIVE, PRE_COUNTDOWN_VALUE
    with STATE_LOCK:
        if not GAME_RUNNING:
            return
        PRE_COUNTDOWN_ACTIVE = True

    for val in [3, 2, 1]:
        with STATE_LOCK:
            if not GAME_RUNNING:
                PRE_COUNTDOWN_ACTIVE = False
                PRE_COUNTDOWN_VALUE = 0
                return
            PRE_COUNTDOWN_VALUE = val

        lcd_show_4_lines("", str(val), "", "", force=True)
        _short_beep()
        time.sleep(1.0)

    with STATE_LOCK:
        if not GAME_RUNNING:
            PRE_COUNTDOWN_ACTIVE = False
            PRE_COUNTDOWN_VALUE = 0
            return
        PRE_COUNTDOWN_VALUE = 0

    lcd_show_4_lines("", "GO!", "", "", force=True)
    _long_beep()
    time.sleep(0.5)

    with STATE_LOCK:
        PRE_COUNTDOWN_ACTIVE = False
        PRE_COUNTDOWN_VALUE = 0

# =========================
# 單場 Game
# =========================
def play_single_game(game_index: int, mode: int):
    global CURRENT_GAME_SCORE, ROUND_TOTAL_SCORE, REMAINING_TIME
    global GAME1_SCORE, GAME2_SCORE

    # 每場開始先回中心，再進入模式（你要求開始/結束都回 90）
    _servo_reset_to_center()
    servo_set_mode(mode)

    with _goal._lock:
        last_seq = _goal.seq
    _goal.set_enabled(True)

    CURRENT_GAME_SCORE = 0
    REMAINING_TIME = int(GAME_TIME)
    start_time = time.time()

    while True:
        with STATE_LOCK:
            if not GAME_RUNNING:
                break

        elapsed = time.time() - start_time
        left = max(0, int(GAME_TIME) - int(elapsed))
        REMAINING_TIME = left

        # 更新 SG90
        servo_tick()

        # 進球事件
        add = _goal.consume_since(last_seq)
        if add > 0:
            with _goal._lock:
                last_seq = _goal.seq
            CURRENT_GAME_SCORE += add
            ROUND_TOTAL_SCORE += add
            play_goal_sound()

        if game_index == 1:
            GAME1_SCORE = CURRENT_GAME_SCORE
        else:
            GAME2_SCORE = CURRENT_GAME_SCORE

        # LCD 顯示：第 3 行先顯示 Mode，再顯示秒數
        line1 = _format_time_now_str()
        line2 = f"ROUND {CURRENT_ROUND} GAME {game_index}"
        line3 = f"MODE:{mode} LEFT:{left:02d}s"
        line4 = f"GAME SCORE: {CURRENT_GAME_SCORE}"
        lcd_show_4_lines(line1, line2, line3, line4)

        if left <= 0:
            break

        # 主迴圈小 sleep（servo_tick 內部有節流；這裡留給 OS 排程）
        time.sleep(0.005)

    _goal.set_enabled(False)
    _servo_reset_to_center()

# =========================
# Game1 → Game2 過場
# =========================
def game1_to_game2_transition():
    global NEXT_GAME_HINT_ACTIVE, NEXT_GAME_HINT_MESSAGE

    time.sleep(2.0)

    lcd_show_4_lines("", "", "", "", force=True)
    _short_beep()
    time.sleep(0.6)

    with STATE_LOCK:
        NEXT_GAME_HINT_ACTIVE = True
        NEXT_GAME_HINT_MESSAGE = "NEXT GAME"

    lcd_show_4_lines("NEXT GAME", "", "", "", force=True)
    time.sleep(1.0)

    with STATE_LOCK:
        NEXT_GAME_HINT_ACTIVE = False
        NEXT_GAME_HINT_MESSAGE = ""

    pre_start_countdown()

# =========================
# Round 主流程
# =========================
def round_thread(round_start_time_iso: str, g1_mode: int, g2_mode: int, g_time: int):
    global CURRENT_ROUND, CURRENT_GAME, CURRENT_GAME_MODE
    global GAME_RUNNING, ROUND_START_TIME_ISO
    global GAME1_SCORE, GAME2_SCORE, CURRENT_GAME_SCORE, ROUND_TOTAL_SCORE, REMAINING_TIME
    global GAME_TIME

    with STATE_LOCK:
        if GAME_RUNNING:
            return
        GAME_RUNNING = True
        CURRENT_ROUND += 1
        CURRENT_GAME = 0
        CURRENT_GAME_MODE = 0
        ROUND_START_TIME_ISO = round_start_time_iso

        GAME1_SCORE = 0
        GAME2_SCORE = 0
        CURRENT_GAME_SCORE = 0
        ROUND_TOTAL_SCORE = 0
        REMAINING_TIME = 0

        GAME_TIME = int(g_time)

    try:
        # Round 開始先回中心
        _servo_reset_to_center()

        # Game1
        with STATE_LOCK:
            CURRENT_GAME = 1
            CURRENT_GAME_MODE = int(g1_mode)

        pre_start_countdown()
        with STATE_LOCK:
            if not GAME_RUNNING:
                raise RuntimeError("stopped during Game1 countdown")

        play_single_game(1, int(g1_mode))

        with STATE_LOCK:
            if not GAME_RUNNING:
                raise RuntimeError("stopped after Game1")

        # 過場
        game1_to_game2_transition()
        with STATE_LOCK:
            if not GAME_RUNNING:
                raise RuntimeError("stopped during transition")

        # Game2
        with STATE_LOCK:
            CURRENT_GAME = 2
            CURRENT_GAME_MODE = int(g2_mode)

        play_single_game(2, int(g2_mode))

        with STATE_LOCK:
            if not GAME_RUNNING:
                raise RuntimeError("stopped after Game2")

        # Round 結束畫面
        time.sleep(2.0)
        line1 = _format_time_now_str()
        line2 = f"ROUND {CURRENT_ROUND} GAME 2"
        line3 = "Round End"
        line4 = f"ROUND SCORE:{ROUND_TOTAL_SCORE}"
        lcd_show_4_lines(line1, line2, line3, line4, force=True)

        entry = {
            "round_id": int(CURRENT_ROUND),
            "start_time": str(ROUND_START_TIME_ISO),
            "game1_mode": int(g1_mode),
            "game2_mode": int(g2_mode),
            "game1_score": int(GAME1_SCORE),
            "game2_score": int(GAME2_SCORE),
            "round_total_score": int(ROUND_TOTAL_SCORE),
        }
        save_round_history_entry(entry)

    except Exception as e:
        print("[ROUND] stopped or error:", e)

    finally:
        with STATE_LOCK:
            GAME_RUNNING = False
            CURRENT_GAME = 0
            CURRENT_GAME_MODE = 0
            REMAINING_TIME = 0
        _goal.set_enabled(False)
        _servo_reset_to_center()

# =========================
# 提供給 Flask 的 API
# =========================
def start_game():
    global GAME1_MODE, GAME2_MODE, GAME_TIME
    with STATE_LOCK:
        if GAME_RUNNING:
            return
        g1 = int(GAME1_MODE)
        g2 = int(GAME2_MODE)
        gt = int(GAME_TIME)

    round_start_time_iso = datetime.now().isoformat(timespec="seconds")
    t = threading.Thread(
        target=round_thread,
        args=(round_start_time_iso, g1, g2, gt),
        daemon=True,
    )
    t.start()

def stop_game():
    global GAME_RUNNING
    with STATE_LOCK:
        GAME_RUNNING = False
    _goal.set_enabled(False)
    _servo_reset_to_center()

def set_sound_mode(mode: str):
    global SOUND_MODE
    if mode not in ("beep", "cheer"):
        return
    with STATE_LOCK:
        SOUND_MODE = mode
    _save_config()

def set_mute(muted: bool):
    global SOUND_ENABLED
    with STATE_LOCK:
        SOUND_ENABLED = (not muted)
        if muted:
            _buzzer_off()

def set_game_time(seconds: int):
    global GAME_TIME
    try:
        s = int(seconds)
    except Exception:
        return
    s = max(3, min(3600, s))
    with STATE_LOCK:
        GAME_TIME = s
    _save_config()

def set_game_modes(game1_mode: int, game2_mode: int):
    global GAME1_MODE, GAME2_MODE
    try:
        g1 = int(game1_mode)
        g2 = int(game2_mode)
    except Exception:
        return
    if g1 not in (1, 2, 3) or g2 not in (1, 2, 3):
        return
    with STATE_LOCK:
        GAME1_MODE = g1
        GAME2_MODE = g2
    _save_config()

def get_status():
    with STATE_LOCK:
        history_recent, history_best = get_history_summary()
        dbg = _goal.get_debug()

        status = {
            "round": int(CURRENT_ROUND),
            "game": int(CURRENT_GAME),

            "score": int(CURRENT_GAME_SCORE),
            "round_total": int(ROUND_TOTAL_SCORE),

            "game1_mode": int(GAME1_MODE),
            "game2_mode": int(GAME2_MODE),
            "current_game_mode": int(CURRENT_GAME_MODE),

            "game1_score": int(GAME1_SCORE),
            "game2_score": int(GAME2_SCORE),
            "remaining_time": int(REMAINING_TIME),

            "running": bool(GAME_RUNNING or PRE_COUNTDOWN_ACTIVE),
            "sound_mode": str(SOUND_MODE),
            "muted": bool(not SOUND_ENABLED),
            "game_time": int(GAME_TIME),

            "pre_countdown_active": bool(PRE_COUNTDOWN_ACTIVE),
            "pre_countdown_value": int(PRE_COUNTDOWN_VALUE),

            "next_game_hint_active": bool(NEXT_GAME_HINT_ACTIVE),
            "next_game_hint_message": str(NEXT_GAME_HINT_MESSAGE),

            "round_start_time": ROUND_START_TIME_ISO,

            "history_recent": history_recent,
            "history_best": int(history_best),

            "button_press_count": int(BUTTON_PRESS_COUNT),

            # IR debug
            "sensor_v": float(dbg["sensor_v"]),
            "goal_entry_v": float(dbg["entry_v"]),
            "goal_release_v": float(dbg["release_v"]),
            "goal_holdoff_ms": int(dbg["holdoff_ms"]),
            "goal_min_width_ms": float(dbg["min_width_ms"]),
            "goal_event_seq": int(dbg["event_seq"]),
            "last_event_peak_v": float(dbg["last_event_peak_v"]),
            "last_event_width_ms": float(dbg["last_event_width_ms"]),
            "last_event_ts": str(dbg["last_event_ts"]),
            "sensor_eff_rate_hz": float(dbg["last_eff_rate_hz"]),

            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
    return status

# =========================
# 實體 Start 按鈕監聽
# =========================
GPIO.setup(START_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def start_button_monitor_loop():
    global BUTTON_PRESS_COUNT
    last_pressed = 0.0
    print("[BUTTON] monitor started, waiting for GPIO 17 LOW ...")
    while True:
        try:
            if GPIO.input(START_BUTTON_PIN) == GPIO.LOW:
                now = time.time()
                if now - last_pressed > 0.8:
                    last_pressed = now
                    BUTTON_PRESS_COUNT += 1
                    print(f"[BUTTON] pressed, count={BUTTON_PRESS_COUNT} → start_game()")
                    start_game()

                while GPIO.input(START_BUTTON_PIN) == GPIO.LOW:
                    time.sleep(0.03)

            time.sleep(0.03)
        except Exception as e:
            print("[BUTTON] error:", e)
            time.sleep(0.3)

# =========================
# 初始化
# =========================
_load_config()
_goal.start()
threading.Thread(target=start_button_monitor_loop, daemon=True).start()

_servo_reset_to_center()
lcd_show_4_lines("Basketball Ready", "", "", "", force=True)
