# 動感投籃機（Basketball Shooting Game）  
Raspberry Pi 版操作與組裝 SOP（Markdown）
---
影片：https://youtube.com/shorts/cjnFgCmjGvc?feature=share

![S__17793064_0](https://github.com/user-attachments/assets/ef8e1a1a-38a1-45e2-8934-6938c7c43f4f)

## 一、系統目標與整體說明

### 1.1 系統概要

- 平台：Raspberry Pi 4 + Python 3 + Flask Web  
- 玩法：縮小版投籃機，玩家將小球投入小籃框，系統偵測進球並計分。  
- 顯示與操作：
  - 20×4 I2C LCD 即時顯示時間、Round / Game 狀態與分數。
  - Flask Web 介面顯示分數、倒數計時、歷史紀錄，並可控制開始、停止、模式、時間與音效。
  - 實體 Start 按鈕（GPIO 17）可直接啟動一個 Round，邏輯與 Web Start 完全相同。  

### 1.2 遊戲架構

- 每一個 **Round 固定包含兩場 Game**：Game 1、Game 2。
- 每場 Game 有：
  - 倒數階段：3 → 2 → 1 → GO!
  - 正式遊戲時間：預設 30 秒（可在 Web 調整）。
  - 可選擇Mode1(籃框90度)、Mode2(籃框45-135度定速移動)、Mode3(籃框30-150度隨機移動)
- 每顆有效進球自動加分並播放音效。
- Round 結束時會計算本 Round 總分，並寫入歷史紀錄檔。

---

## 二、硬體規格

### 2.1 核心板與儲存

- Raspberry Pi 4B（含官方 5V / 3A 電源）。
- microSD 卡 16GB 以上。

### 2.2 感測與動作元件

- **SG90 伺服馬達 ×1**  
  - 控制籃框左右轉動角度。
- **GP2Y0A51SK0F 距離感測器 ×1**  
  - 負責偵測球是否穿過籃框。
- **MCP3008 10-bit ADC ×1**  
  - 將 GP2Y 類比電壓轉成數位值，由 Raspberry Pi 讀取。
- **20×4 I2C LCD 模組 ×1**  
  - 用於顯示當前時間、Round / Game 編號、剩餘時間與分數。
- **蜂鳴器 HPE-122（主動式） ×1**  
  - 音效提示：倒數嗶聲、進球音效、過場提示。
- **Start 實體按鈕 ×1**  
  - GPIO 17，內部上拉，按下接 GND。

### 2.3 機構與工具

- 紙箱
- 紙杯(籃框)
- 膠帶
- 雙面膠
- 美工刀
- 剪刀
- 釘書機

---

## 三、接線說明

### 3.1 電源軌規劃

- **5V 電源軌**
  - Raspberry Pi Pin 2（5V）→ 麵包板上方 **+ 軌**
  - 供給：LCD VCC、GP2Y0A51SK0F Vcc、SG90 紅線 (VCC)、蜂鳴器 HPE-122 正極
- **3.3V 電源軌**
  - Raspberry Pi Pin 1（3.3V）→ 麵包板下方 **+ 軌**
  - 供給：MCP3008 VDD、MCP3008 VREF
- **GND 共地**
  - Raspberry Pi Pin 6（GND）→ 麵包板上方 **− 軌**
  - 麵包板下方 − 軌再用一條線接回上方 − 軌  
  → **Raspberry Pi、MCP3008、感測器、伺服馬達、蜂鳴器、按鈕全部共地**。

---

### 3.2 MCP3008 + GP2Y0A51SK0F 距離感測器

**GP2Y0A51SK0F**
<img width="600" height="429" alt="image" src="https://github.com/user-attachments/assets/effd1c77-b1c0-40dd-85ee-0879a1b238dd" />

| 腳位 | 接到         |
|------|--------------|
| Vcc  | 5V 軌        |
| GND  | GND 軌       |
| Vo   | MCP3008 CH0  |


**MCP3008 腳位**
<img width="216" height="163" alt="image" src="https://github.com/user-attachments/assets/a4ec5d31-97f0-497d-87b7-b462fba39524" />

| MCP3008 腳位 | 功能   | 接到                       |
|--------------|--------|----------------------------|
| Pin 1        | CH0    | GP2Y Vo                    |
| Pin 9        | DGND   | GND                        |
| Pin 10       | CS/SHDN| Raspberry Pi GPIO 8 (CE0)  |
| Pin 11       | DIN    | Raspberry Pi GPIO 10 (MOSI)|
| Pin 12       | DOUT   | Raspberry Pi GPIO 9 (MISO) |
| Pin 13       | CLK    | Raspberry Pi GPIO 11 (SCLK)|
| Pin 14       | AGND   | GND                        |
| Pin 15       | VREF   | 3.3V 軌                   |
| Pin 16       | VDD    | 3.3V 軌                   |

---

### 3.3 20×4 I2C LCD
<img width="231" height="211" alt="image" src="https://github.com/user-attachments/assets/ab5453dd-440a-4baa-bb3f-4f2b5ee7cd54" />

LCD 背板 4 Pin：

| LCD 腳位 | 接到                        |
|---------|-----------------------------|
| GND     | GND 軌                      |
| VCC     | 5V 軌                       |
| SDA     | Raspberry Pi GPIO 2 (Pin 3) |
| SCL     | Raspberry Pi GPIO 3 (Pin 5) |

---

### 3.4 SG90 伺服馬達（籃框）
<img width="657" height="418" alt="image" src="https://github.com/user-attachments/assets/2418ec3f-ab44-48ce-a2f8-78e838519c96" />


| SG90 線色 | 功能   | 接到                 |
|-----------|--------|----------------------|
| 橘色      | Signal | Raspberry Pi GPIO 23 |
| 紅色      | VCC    | 5V 軌               |
| 棕色      | GND    | GND 軌              |

- 安全角度範圍：**30° ~ 150°**。
- 程式啟動與每場 Game 結束時，SG90 **強制回到 90°**，並維持 PWM 輸出，讓籃框穩定停在中間。

---

### 3.5 蜂鳴器 HPE-122

| 腳位 | 接到                 |
|------|----------------------|
| 長腳 + | Raspberry Pi GPIO 25（可串 10kΩ 降低音量） |
| 短腳 − | GND 軌              |

---

### 3.6 Start 實體按鈕

| 腳位 | 接到                 |
|------|----------------------|
| 一腳 | Raspberry Pi GPIO 17 |
| 一腳 | GND 軌               |

- GPIO 17 在程式內設為 **pull-up**：
  - 放開：讀值 HIGH
  - 按下：接 GND → 讀值 LOW
<img width="490" height="432" alt="image" src="https://github.com/user-attachments/assets/2b27c67a-04b1-4aa3-b5ab-3ea59572c5f4" />

![S__17793052_0](https://github.com/user-attachments/assets/070c9492-8d59-4d58-a5cd-5ecd91d7bd2d)
![S__17793053_0](https://github.com/user-attachments/assets/ffdc2f28-8cf1-4b34-86e5-de03544ab5da)
![S__17793048_0](https://github.com/user-attachments/assets/34212eaa-fd35-403d-bf15-ef229bdb0195)


---

## 四、程式架構

### 4.1 檔案結構

```text
專案目錄/
├── app.py          # Flask Web 伺服器
├── game_logic.py   # 遊戲主邏輯（GPIO / Servo / IR / LCD / 按鈕）
├── score_history.json  # 遊戲歷史紀錄（自動產生）
├── game_config.json    # Web 設定檔（自動產生）
└── templates/
    └── index.html  # Web 控制台介面
```

### 4.2 `game_logic.py` 職責

- 啟動時初始化：
  - GPIO 模式、MCP3008 SPI、SG90 伺服馬達、蜂鳴器、LCD。
  - 讀取 `game_config.json` （如存在）載入上次使用的 `Game1_Mode / Game2_Mode / Game_Time / Sound_Mode`。
  - 預設顯示 LCD：「Basketball Ready」。
  - 啟動 **GoalDetector** thread（高頻讀取 IR 電壓做進球判定）。
  - 啟動 **start_button_monitor_loop**，負責監聽 GPIO 17 的按鍵事件。
- 提供給 Flask 的介面函數：
  - `start_game()` / `stop_game()`
  - `set_sound_mode(mode)`、`set_mute(muted)`
  - `set_game_time(seconds)`、`set_game_modes(game1, game2)`
  - `get_status()` 給 Web 查詢即時狀態。

### 4.3 `app.py` 職責

- 啟動 Flask 伺服器 `host=0.0.0.0, port=5000`。
- 提供 HTTP API：
  - `/`：回傳 `index.html`
  - `/start`：開始一個 Round（呼叫 `start_game()`）
  - `/stop`：停止遊戲（呼叫 `stop_game()`）
  - `/status`：回傳目前狀態 JSON（提供 Web 輪詢更新）
  - `/sound/<mode>`：設定進球音效模式（`beep` / `cheer`）
  - `/mute` / `/unmute`：控制靜音
  - `/set_time?seconds=30`：設定每場遊戲秒數
  - `/set_modes?game1=1&game2=3`：設定下一個 Round 的 Game1 / Game2 模式

### 4.4 `index.html` Web 介面

- 顯示：
  - 狀態：STOPPED / RUNNING
  - Round、Game 編號
  - 本場得分、本輪總得分
  - 本場剩餘時間（大字體倒數）
  - 音效模式、靜音狀態
  - 每場秒數設定值
  - 最近 10 次 Round 的紀錄與歷史最高分（由 `score_history.json` 讀取）

- 控制：
  - Start Round / Stop 按鈕（對應 `start_game()` / `stop_game()`）
  - Game1 / Game2 模式選擇（Mode1 / Mode2 / Mode3）
  - 每場秒數輸入與套用
  - 音效模式切換（嗶嗶 / 歡呼）、靜音切換

- 額外：
  - 全螢幕倒數 Overlay：顯示 3 → 2 → 1 → GO!，與蜂鳴器倒數音效同步。
  - 不使用快取（HTTP header + meta），避免畫面殘留舊狀態。

---

## 五、遊戲流程與狀態機

### 5.1 Round / Game 架構

- **按一次 Start（Web 或實體按鈕）**：
  - `CURRENT_ROUND += 1`
  - Round 中固定包含 **Game1 + Game2** 兩場。
- Game 模式由 Web 預先設定：
  - `Game1_Mode ∈ {1, 2, 3}`
  - `Game2_Mode ∈ {1, 2, 3}`
  - 預設：Game1 = Mode1、Game2 = Mode2。
- 設定變更後，從下一個 Round 開始生效（避免進行中的 Round 模式突然改變）。

### 5.2 籃框模式定義（SG90）

- **Mode1：固定 90°**
  - Game 中整場維持 90 度。
- **Mode2：50° ↔ 130° 定速來回**
  - 角度範圍：50°–130°。
  - 每次更新角度增加/減少固定步長 3°。
  - 更新頻率約每 0.01 秒一次，體感為中高速。
- **Mode3：30° ↔ 150° 定速來回（高速大範圍）**
  - 角度範圍：30°–150°。
  - 每次更新角度增加/減少固定步長 5°。
  - 更新頻率約每 0.006 秒一次，速度明顯快於 Mode2。

> 每場 Game 結束或按 Stop 時，伺服都會強制回到 90°，保持籃框回到中間位置。

### 5.3 時間軸

**每場 Game 流程：**

1. **倒數階段**
   - LCD 只用單行顯示：3 → 2 → 1 → GO!
   - 蜂鳴器：
     - 3、2、1：短嗶。
![S__17793074_0](https://github.com/user-attachments/assets/65fcaf60-a7f6-4061-a2f2-6c42226da4da)
     - GO!：長嗶。
![S__17793070_0](https://github.com/user-attachments/assets/e37ece86-c04e-4b8f-9f2b-9d2cf2435f18)


2. **Playing 階段**
   - 持續時間：預設 30 秒（可由 Web 調整）。
   - 進球偵測啟用（GoalDetector enabled）。
   - 每次偵測到有效進球 → 分數 +1，播放進球音效。
3. **Game1 → Game2 過場**
   - Game1 結束後：
     1. 保留 Game1 最後畫面 2 秒。
     2. 清空 LCD → 短嗶一聲 → 再停 0.6 秒。
     3. 顯示 `NEXT GAME` 單行約 1 秒。
     4. 再進入 Game2 的倒數 3 → 2 → 1 → GO!。
4. **Round 結束**
   - Game2 結束後：
     - 保留 Game2 最後畫面 2 秒。
     - 顯示 Round 結束畫面：
       - 第 1 行：現在時間
       - 第 2 行：`ROUND X GAME 2`
       - 第 3 行：`Round End`
       - 第 4 行：`ROUND SCORE: N`（Game1+Game2 總分）

---

## 六、進球偵測邏輯（IR + MCP3008）

- 感測器：GP2Y0A51SK0F 固定在籃框一側，面向框內。
- 由 MCP3008 CH0 讀取 10-bit 類比值，換算成電壓約 0–3.3V。
- **判定條件：**
  - 進入門檻：電壓 ≥ 2.00V → 視為球靠近（entry）。
  - 放開門檻：電壓 ≤ 1.70V → 視為球離開（release）。
  - 事件寬度：entry 到 release 間時間長度 ≥ 5ms 才算「有效事件」。
  - Holdoff：每個事件完成後，**250ms 內不再接受新事件**，避免一顆球多次反彈被計成多分。
- 實作：
  - 由獨立 thread `GoalDetector` 高頻輪詢電壓（約數百 Hz 等級），主遊戲迴圈只根據事件序號 `seq` 來加分。

---

## 七、LCD 顯示規格（20×4）
![S__17793082_0](https://github.com/user-attachments/assets/e62a1497-3e7e-4795-adc0-9e9c37530284)


### 7.1 倒數畫面（Game 前）

- **單行顯示**：
  - 顯示內容：`3` → `2` → `1` → `GO!`
  - 其餘行保持空白。
  - 與蜂鳴器倒數音效同步。

### 7.2 遊戲中（Playing）

- 4 行內容：
  1. **第 1 行**：現在時間  
     例：`2025/12/10 03:15:40`
  2. **第 2 行**：`ROUND X GAME Y`
  3. **第 3 行**：遊戲剩餘秒數（實作格式示例：`LEFT: 23s`，可加上 mode 資訊）
  4. **第 4 行**：`GAME SCORE: N`（本場已累積分數）

### 7.3 過場畫面（Game1 → Game2）

- Game1 結束後：
  - 先保留原遊戲畫面 2 秒。
  - 清空 LCD + 短嗶一聲。
  - 顯示 `NEXT GAME`（單行），約 1 秒。

### 7.4 Round 結束畫面（Game2 結束後）

- 4 行內容：
  1. `2025/12/10 03:15:40`（當下時間）
  2. `ROUND X GAME 2`
  3. `Round End`
  4. `ROUND SCORE: N`（本 Round 總分）

---

## 八、Web 介面規格（Flask Dashboard）

### 8.1 顯示資訊

- 狀態：`RUNNING` / `STOPPED`
- Round 編號、Game 編號
- 本場得分（CURRENT_GAME_SCORE）
- 本輪總得分（ROUND_TOTAL_SCORE）
- 本場剩餘時間（倒數數字）
- 音效模式：`BEEP / CHEER`
- 靜音狀態：`ON / OFF`
- 每場秒數（GAME_TIME）
- 最近 10 個 Round 的紀錄與歷史最高分（由 `score_history.json` 讀取）
![S__17793071_0](https://github.com/user-attachments/assets/01a5c0a3-bf55-41b3-8f68-7ce072af3d92)
![S__17793058_0](https://github.com/user-attachments/assets/bfe81f88-da82-42e0-a75c-a088b79a91b5)

### 8.2 控制項

- **Start Round**：呼叫 `/start` → 對應 `start_game()`。
- **Stop**：呼叫 `/stop` → 對應 `stop_game()`，會結束當前 Round 並把 Servo 轉回 90°。
- **音效設定**：
  - 按鈕切換嗶嗶／歡呼 → `/sound/beep`、`/sound/cheer`。
  - 靜音 / 取消靜音 → `/mute`、`/unmute`（立即生效）。
- **時間與模式設定**：
  - 每場秒數：輸入數字後按「套用」→ `/set_time?seconds=xx`，從下一個 Round 開始採用。
  - Game1 / Game2 模式下拉選單：
    - Mode1（固定 90°）
    - Mode2（50↔130 定速）
    - Mode3（30↔150 定速高速）
    - 送出 `/set_modes?game1=..&game2=..` 後，從下一個 Round 生效。

### 8.3 倒數 Overlay

- 當 `pre_countdown_active = True` 時：
  - Web 會顯示全螢幕黑底，中央顯示 3 / 2 / 1 / GO!。
  - 與實際 LCD 倒數與蜂鳴器同步。

---

## 九、歷史紀錄檔格式（`score_history.json`）

每個 Round 結束時，寫入一筆 JSON 物件，欄位至少包含：

- `round_id`：Round 編號（從 1 開始）
- `start_time`：本 Round 開始時間（ISO 字串，例如 `2025-12-10T03:15:40`）
- `game1_mode`：Game1 的籃框模式（1 / 2 / 3）
- `game2_mode`：Game2 的籃框模式（1 / 2 / 3）
- `game1_score`：Game1 最終得分
- `game2_score`：Game2 最終得分
- `round_total_score`：本 Round 總分（Game1 + Game2）

Web 端 `/status` 會整理出：

- `history_recent`：最近 10 筆 Round 紀錄。
- `history_best`：歷史最高 `round_total_score`。

---

## 十、啟動與操作步驟（實作流程）

1. 將所有硬體依本 SOP 接線完成，確認：
   - 5V / 3.3V / GND 軌無短路。
   - SG90 固定好籃框，初始角度不會撞到機構。
   - GP2Y0A51SK0F 面向籃框內，出球時會明顯改變距離。
2. 在 Raspberry Pi 上安裝所需 Python 套件：
   - `RPi.GPIO`、`spidev`、`I2C_LCD_driver`（或學長提供的同名模組）、`flask` 等。
3. 在專案資料夾執行：
   - `python3 app.py`
   - 看到終端機列出 `Basketball Ready` 即完成初始化。
4. 在同一網段 PC / 手機瀏覽器開啟：
   - `http://<樹莓派 IP>:5000/`
5. 操作流程：
   - 在 Web 設定：
     - 每場秒數（例如 30 秒）
     - Game1 / Game2 模式（例如 Mode1 / Mode2）
     - 音效模式與是否靜音
   - 按下 Web 上的「Start Round」或實體 Start 按鈕：
     - 螢幕與蜂鳴器進行倒數 → Game1 → 過場 → 倒數 → Game2 → Round End。
   - 完成後可在 Web 下方看最近 10 次 Round 的分數與歷史最佳分數。
   
