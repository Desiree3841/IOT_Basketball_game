# I2C_LCD_driver.py
# 適用 20x4 I2C LCD（PCF8574 背包），位址 0x27

import smbus
import time

# I2C 位址
LCD_ADDR = 0x27

# LCD 參數
LCD_WIDTH = 20   # 每行 20 字元

LCD_CHR = 1
LCD_CMD = 0

LCD_LINE_1 = 0x80
LCD_LINE_2 = 0xC0
LCD_LINE_3 = 0x94
LCD_LINE_4 = 0xD4

LCD_BACKLIGHT = 0x08
ENABLE = 0b00000100

E_PULSE = 0.0005
E_DELAY = 0.0005


class lcd:
    def __init__(self, addr=LCD_ADDR):
        self.addr = addr
        self.bus = smbus.SMBus(1)
        self.lcd_init()

    def lcd_init(self):
        # 初始化流程（4-bit 模式）
        self.lcd_write(0x33, LCD_CMD)
        self.lcd_write(0x32, LCD_CMD)
        self.lcd_write(0x28, LCD_CMD)  # 2 line, 5x8 font
        self.lcd_write(0x0C, LCD_CMD)  # 顯示開啟, 游標關閉
        self.lcd_write(0x06, LCD_CMD)  # 自動游標右移
        self.lcd_write(0x01, LCD_CMD)  # 清除畫面
        time.sleep(E_DELAY)

    def lcd_write(self, bits, mode):
        """送出高 4 bit + 低 4 bit"""
        high = mode | (bits & 0xF0) | LCD_BACKLIGHT
        low = mode | ((bits << 4) & 0xF0) | LCD_BACKLIGHT

        self.bus.write_byte(self.addr, high)
        self.lcd_toggle_enable(high)

        self.bus.write_byte(self.addr, low)
        self.lcd_toggle_enable(low)

    def lcd_toggle_enable(self, bits):
        time.sleep(E_DELAY)
        self.bus.write_byte(self.addr, bits | ENABLE)
        time.sleep(E_PULSE)
        self.bus.write_byte(self.addr, bits & ~ENABLE)
        time.sleep(E_DELAY)

    def lcd_clear(self):
        self.lcd_write(0x01, LCD_CMD)
        time.sleep(E_DELAY)

    def lcd_display_string(self, string, line):
        """line = 1~4"""
        if line == 1:
            self.lcd_write(LCD_LINE_1, LCD_CMD)
        elif line == 2:
            self.lcd_write(LCD_LINE_2, LCD_CMD)
        elif line == 3:
            self.lcd_write(LCD_LINE_3, LCD_CMD)
        elif line == 4:
            self.lcd_write(LCD_LINE_4, LCD_CMD)

        for ch in string.ljust(LCD_WIDTH, " "):
            self.lcd_write(ord(ch), LCD_CHR)
