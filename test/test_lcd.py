import time
import I2C_LCD_driver

lcd = I2C_LCD_driver.lcd()

lcd.lcd_clear()
lcd.lcd_display_string("Hello, LomicaPi!", 1)
lcd.lcd_display_string("I2C addr: 0x27", 2)
lcd.lcd_display_string("20x4 LCD Test", 3)

time.sleep(5)

lcd.lcd_clear()
lcd.lcd_display_string("OK, LCD Ready", 1)
time.sleep(2)
lcd.lcd_clear()
