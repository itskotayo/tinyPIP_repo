# ============================================================
# tinypip_os_v1_8_0.py
# TinyPIP OS v1.8.0
# No Module Manager • No Font Scaling • Title Offset Fix
# GPS/Weather/Tracker/Set Date/Set Time
# ============================================================

UPDATE_STATE = 0
UPDATE_STATE_TIME = 0

from machine import Pin, SPI, PWM, RTC
import framebuf
import utime
import os
import gc
import network
import urandom
import math
import random
from wifi_update import wifi_fallback_update

try:
    import bluetooth
    HAS_BLE = True
except:
    HAS_BLE = False

rtc = RTC()

OS_VERSION = "v1.8.0"
OS_YEAR    = "2026"

LAST_UPDATE_OK = False
LAST_UPDATE_TIME = 0

# ============================================================
# LCD DRIVER
# ============================================================

BL = 13
DC = 8
RST = 12
MOSI = 11
SCK = 10
CS = 9

class LCD_1inch3(framebuf.FrameBuffer):
    def __init__(self):
        self.width = 240
        self.height = 240
        
        self.cs = Pin(CS, Pin.OUT)
        self.rst = Pin(RST, Pin.OUT)
        
        self.cs(1)
        self.spi = SPI(1)
        self.spi = SPI(1, 1000_000)
        self.spi = SPI(1, 100000_000, polarity=0, phase=0,
                       sck=Pin(SCK), mosi=Pin(MOSI), miso=None)
        self.dc = Pin(DC, Pin.OUT)
        self.dc(1)
        self.buffer = bytearray(self.height * self.width * 2)
        super().__init__(self.buffer, self.width, self.height, framebuf.RGB565)
        self.init_display()
        
        self.red   = 0x07E0
        self.green = 0x001f
        self.blue  = 0xf800
        self.white = 0xffff
        
    def write_cmd(self, cmd):
        self.cs(1)
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.cs(1)
        self.dc(1)
        self.cs(0)
        self.spi.write(bytearray([buf]))
        self.cs(1)

    def init_display(self):
        self.rst(1)
        self.rst(0)
        self.rst(1)
        
        self.write_cmd(0x36)
        self.write_data(0x70)

        self.write_cmd(0x3A)
        self.write_data(0x05)

        self.write_cmd(0xB2)
        for v in [0x0C,0x0C,0x00,0x33,0x33]:
            self.write_data(v)

        self.write_cmd(0xB7)
        self.write_data(0x35)

        self.write_cmd(0xBB)
        self.write_data(0x19)

        self.write_cmd(0xC0)
        self.write_data(0x2C)

        self.write_cmd(0xC2)
        self.write_data(0x01)

        self.write_cmd(0xC3)
        self.write_data(0x12)

        self.write_cmd(0xC4)
        self.write_data(0x20)

        self.write_cmd(0xC6)
        self.write_data(0x0F)

        self.write_cmd(0xD0)
        self.write_data(0xA4)
        self.write_data(0xA1)

        self.write_cmd(0xE0)
        for v in [0xD0,0x04,0x0D,0x11,0x13,0x2B,0x3F,0x54,0x4C,0x18,0x0D,0x0B,0x1F,0x23]:
            self.write_data(v)

        self.write_cmd(0xE1)
        for v in [0xD0,0x04,0x0C,0x11,0x13,0x2C,0x3F,0x44,0x51,0x2F,0x1F,0x1F,0x20,0x23]:
            self.write_data(v)
        
        self.write_cmd(0x21)
        self.write_cmd(0x11)
        self.write_cmd(0x29)

    def show(self):
        self.write_cmd(0x2A)
        for v in [0x00,0x00,0x00,0xEF]:
            self.write_data(v)
        
        self.write_cmd(0x2B)
        for v in [0x00,0x00,0x00,0xEF]:
            self.write_data(v)
        
        self.write_cmd(0x2C)
        
        self.cs(1)
        self.dc(1)
        self.cs(0)
        self.spi.write(self.buffer)
        self.cs(1)

# ============================================================
# COLOUR FUNCTION
# ============================================================

def colour(R, G, B):
    rp = int(R * 31 / 255)
    r = rp * 8
    gp = int(G * 63 / 255)
    g = ((gp & 1) << 13) | ((gp & 2) << 13) | ((gp & 4) << 13) | ((gp & 8) >> 3) | ((gp & 16) >> 3) | ((gp & 32) >> 3)
    bp = int(B * 31 / 255)
    b = bp * 256
    return r + g + b

# ============================================================
# TERMINAL THEME / COLORS
# ============================================================

COLOR_MODE = "GREEN"

PIP_GREEN = 0
PIP_DARK  = 0
PIP_DIM   = 0
PIP_BLACK = colour(0, 0, 0)
PIP_RED = colour(255, 60, 60)

def apply_theme():
    global PIP_GREEN, PIP_DARK, PIP_DIM
    if COLOR_MODE == "GREEN":
        PIP_GREEN = colour(0, 255, 0)
        PIP_DARK  = colour(0, 40, 0)
        PIP_DIM   = colour(0, 120, 0)
    else:
        PIP_GREEN = colour(255, 180, 0)
        PIP_DARK  = colour(40, 20, 0)
        PIP_DIM   = colour(120, 80, 0)

# ============================================================
# BIG DIGIT FONT + DRAWING
# ============================================================

BIG_FONT = {
    "0": [
        " ###### ",
        "##    ##",
        "##   ###",
        "##  # ##",
        "## #  ##",
        "###   ##",
        "##    ##",
        " ###### "
    ],
    "1": [
        "   ##   ",
        " ####   ",
        "   ##   ",
        "   ##   ",
        "   ##   ",
        "   ##   ",
        "   ##   ",
        " ###### "
    ],
    "2": [
        " ###### ",
        "##    ##",
        "      ##",
        "     ## ",
        "   ###  ",
        "  ##    ",
        " ##     ",
        "########"
    ],
    "3": [
        " ###### ",
        "##    ##",
        "      ##",
        "   #### ",
        "      ##",
        "      ##",
        "##    ##",
        " ###### "
    ],
    "4": [
        "##   ## ",
        "##   ## ",
        "##   ## ",
        "##   ## ",
        "########",
        "     ## ",
        "     ## ",
        "     ## "
    ],
    "5": [
        "########",
        "##      ",
        "##      ",
        "######  ",
        "     ## ",
        "     ## ",
        "##   ## ",
        " ###### "
    ],
    "6": [
        " ###### ",
        "##    ##",
        "##      ",
        "######  ",
        "##   ## ",
        "##   ## ",
        "##   ## ",
        " ###### "
    ],
    "7": [
        "########",
        "     ## ",
        "    ##  ",
        "   ##   ",
        "  ##    ",
        " ##     ",
        "##      ",
        "##      "
    ],
    "8": [
        " ###### ",
        "##    ##",
        "##    ##",
        " ###### ",
        "##    ##",
        "##    ##",
        "##    ##",
        " ###### "
    ],
    "9": [
        " ###### ",
        "##    ##",
        "##    ##",
        " #######",
        "      ##",
        "      ##",
        "##    ##",
        " ###### "
    ],
    ":": [
        "   ",
        "## ",
        "## ",
        "   ",
        "   ",
        "## ",
        "## ",
        "   "
    ]
}

def draw_big_char(x, y, ch, color):
    if ch not in BIG_FONT:
        return
    pattern = BIG_FONT[ch]
    for row, line in enumerate(pattern):
        for col, pixel in enumerate(line):
            if pixel == "#":
                LCD.fill_rect(x + col*2, y + row*2, 2, 2, color)

def draw_big_text(x, y, text, color):
    for i, ch in enumerate(text):
        draw_big_char(x + i*18, y, ch, color)

# ============================================================
# MEDIUM FONT (BEGINNING)
# ============================================================

MED_FONT = {
    "A": [
        "   ####    ",
        "  ##  ##   ",
        " ##    ##  ",
        " ##    ##  ",
        " ########  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  "
    ],
    "B": [
        " #######   ",
        " ##    ##  ",
        " ##    ##  ",
        " #######   ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " #######   "
    ],
    "C": [
        "  ######   ",
        " ##    ##  ",
        " ##        ",
        " ##        ",
        " ##        ",
        " ##        ",
        " ##    ##  ",
        "  ######   "
    ],
    "D": [
        " #######   ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " #######   "
    ],
    "E": [
        " ########  ",
        " ##        ",
        " ##        ",
        " #######   ",
        " ##        ",
        " ##        ",
        " ##        ",
        " ########  "
    ],
    "F": [
        " ########  ",
        " ##        ",
        " ##        ",
        " #######   ",
        " ##        ",
        " ##        ",
        " ##        ",
        " ##        "
    ],
    "G": [
        "  ######   ",
        " ##    ##  ",
        " ##        ",
        " ##  ####  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        "  ######   "
    ],
    "H": [
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ########  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  "
    ],
    "I": [
        " #######   ",
        "   ##      ",
        "   ##      ",
        "   ##      ",
        "   ##      ",
        "   ##      ",
        "   ##      ",
        " #######   "
    ],
    "J": [
        "     ###   ",
        "      ##   ",
        "      ##   ",
        "      ##   ",
        "      ##   ",
        " ##   ##   ",
        " ##   ##   ",
        "  #####    "
    ],
    "K": [
        " ##   ##   ",
        " ##  ##    ",
        " ## ##     ",
        " ####      ",
        " ####      ",
        " ## ##     ",
        " ##  ##    ",
        " ##   ##   "
    ],
    "L": [
        " ##        ",
        " ##        ",
        " ##        ",
        " ##        ",
        " ##        ",
        " ##        ",
        " ##        ",
        " ########  "
    ],
    "M": [
        " ##    ##  ",
        " ###  ###  ",
        " ########  ",
        " ## ## ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  "
    ],
    "N": [
        " ##    ##  ",
        " ###   ##  ",
        " ####  ##  ",
        " ## ## ##  ",
        " ##  ####  ",
        " ##   ###  ",
        " ##    ##  ",
        " ##    ##  "
    ],
    "O": [
        "  ######   ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        "  ######   "
    ],
    "P": [
        " #######   ",
        " ##    ##  ",
        " ##    ##  ",
        " #######   ",
        " ##        ",
        " ##        ",
        " ##        ",
        " ##        "
    ],
    "Q": [
        "  ######   ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##  # ##  ",
        " ##   ###  ",
        " ##    ##  ",
        "  #######  "
    ],
    "R": [
        " #######   ",
        " ##    ##  ",
        " ##    ##  ",
        " #######   ",
        " ##  ##    ",
        " ##   ##   ",
        " ##    ##  ",
        " ##    ##  "
    ],
    "S": [
        "  ######   ",
        " ##    ##  ",
        " ##        ",
        "  ######   ",
        "       ##  ",
        "       ##  ",
        " ##    ##  ",
        "  ######   "
    ],
    "T": [
        " ########  ",
        "    ##     ",
        "    ##     ",
        "    ##     ",
        "    ##     ",
        "    ##     ",
        "    ##     ",
        "    ##     "
    ],
    "U": [
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        "  ######   "
    ],
    "V": [
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        "  ##  ##   ",
        "   ####    ",
        "   ####    ",
        "    ##     "
    ],
    "W": [
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        " ## ## ##  ",
        " ########  ",
        " ###  ###  ",
        " ##    ##  ",
        " ##    ##  "
    ],
    "X": [
        " ##    ##  ",
        "  ##  ##   ",
        "   ####    ",
        "    ##     ",
        "   ####    ",
        "  ##  ##   ",
        " ##    ##  ",
        " ##    ##  "
    ],
    "Y": [
        " ##    ##  ",
        " ##    ##  ",
        "  ##  ##   ",
        "   ####    ",
        "    ##     ",
        "    ##     ",
        "    ##     ",
        "    ##     "
    ],
    "Z": [
        " ########  ",
        "      ##   ",
        "     ##    ",
        "    ##     ",
        "   ##      ",
        "  ##       ",
        " ##        ",
        " ########  "
    ],

    "0": [
        "  ######   ",
        " ##    ##  ",
        " ##   ###  ",
        " ##  # ##  ",
        " ## #  ##  ",
        " ###   ##  ",
        " ##    ##  ",
        "  ######   "
    ],
    "1": [
        "   ##      ",
        " ####      ",
        "   ##      ",
        "   ##      ",
        "   ##      ",
        "   ##      ",
        "   ##      ",
        " ######    "
    ],
    "2": [
        "  ######   ",
        " ##    ##  ",
        "       ##  ",
        "     ##    ",
        "   ###     ",
        "  ##       ",
        " ##        ",
        " ########  "
    ],
    "3": [
        "  ######   ",
        " ##    ##  ",
        "       ##  ",
        "   ####    ",
        "       ##  ",
        "       ##  ",
        " ##    ##  ",
        "  ######   "
    ],
    "4": [
        " ##   ##   ",
        " ##   ##   ",
        " ##   ##   ",
        " ########  ",
        "      ##   ",
        "      ##   ",
        "      ##   ",
        "      ##   "
    ],
    "5": [
        " ########  ",
        " ##        ",
        " ##        ",
        " ######    ",
        "      ##   ",
        "      ##   ",
        " ##   ##   ",
        "  ######   "
    ],
    "6": [
        "  ######   ",
        " ##    ##  ",
        " ##        ",
        " ######    ",
        " ##   ##   ",
        " ##   ##   ",
        " ##   ##   ",
        "  ######   "
    ],
    "7": [
        " ########  ",
        "      ##   ",
        "     ##    ",
        "    ##     ",
        "   ##      ",
        "  ##       ",
        " ##        ",
        " ##        "
    ],
    "8": [
        "  ######   ",
        " ##    ##  ",
        " ##    ##  ",
        "  ######   ",
        " ##    ##  ",
        " ##    ##  ",
        " ##    ##  ",
        "  ######   "
    ],
    "9": [
        "  ######   ",
        " ##    ##  ",
        " ##    ##  ",
        "  #######  ",
        "       ##  ",
        "       ##  ",
        " ##    ##  ",
        "  ######   "
    ],

    "-": [
        "          ",
        "          ",
        "          ",
        "  ######  ",
        "  ######  ",
        "          ",
        "          ",
        "          "
    ],
    ":": [
        "    ",
        " ## ",
        " ## ",
        "    ",
        "    ",
        " ## ",
        " ## ",
        "    "
    ],
    "/": [
        "      ##  ",
        "     ##   ",
        "    ##    ",
        "   ##     ",
        "  ##      ",
        " ##       ",
        "##        ",
        "          "
    ],
    " ": [
        "          ",
        "          ",
        "          ",
        "          ",
        "          ",
        "          ",
        "          ",
        "          "
    ],
}
# --- LOWERCASE MED FONT ---
MED_FONT["a"] = [
    "          ",
    "   ####   ",
    "       ## ",
    "   ###### ",
    "  ##   ## ",
    "  ##   ## ",
    "   ###### ",
    "          "
],

MED_FONT["b"] = [
    " ##       ",
    " ##       ",
    " ## ####  ",
    " ###   ## ",
    " ##    ## ",
    " ##    ## ",
    " ###   ## ",
    "  ######  "
],

MED_FONT["c"] = [
    "          ",
    "   #####  ",
    "  ##   ## ",
    " ##       ",
    " ##       ",
    "  ##   ## ",
    "   #####  ",
    "          "
],

MED_FONT["d"] = [
    "       ## ",
    "       ## ",
    "   ###### ",
    "  ##   ###",
    " ##    ## ",
    " ##    ## ",
    "  ##   ###",
    "   ###### "
],

MED_FONT["e"] = [
    "          ",
    "   #####  ",
    "  ##   ## ",
    " ######## ",
    " ##       ",
    "  ##   ## ",
    "   #####  ",
    "          "
],

MED_FONT["f"] = [
    "    ####  ",
    "   ##     ",
    " #######  ",
    "   ##     ",
    "   ##     ",
    "   ##     ",
    "   ##     ",
    "          "
],

MED_FONT["g"] = [
    "          ",
    "   ###### ",
    "  ##   ## ",
    "  ##   ## ",
    "   ###### ",
    "       ## ",
    "  ##   ## ",
    "   #####  "
],

MED_FONT["h"] = [
    " ##       ",
    " ##       ",
    " ## ####  ",
    " ###  ##  ",
    " ##   ##  ",
    " ##   ##  ",
    " ##   ##  ",
    "          "
],

MED_FONT["i"] = [
    "   ##     ",
    "          ",
    "   ##     ",
    "   ##     ",
    "   ##     ",
    "   ##     ",
    "   ##     ",
    "          "
],

MED_FONT["j"] = [
    "     ##   ",
    "          ",
    "     ##   ",
    "     ##   ",
    "     ##   ",
    " ##  ##   ",
    " ##  ##   ",
    "  ####    "
],

MED_FONT["k"] = [
    " ##       ",
    " ##   ##  ",
    " ##  ##   ",
    " ####     ",
    " ####     ",
    " ##  ##   ",
    " ##   ##  ",
    "          "
],

MED_FONT["l"] = [
    "  ##      ",
    "  ##      ",
    "  ##      ",
    "  ##      ",
    "  ##      ",
    "  ##      ",
    "   ####   ",
    "          "
],

MED_FONT["m"] = [
    "          ",
    " #### ##  ",
    " ## ## ## ",
    " ## ## ## ",
    " ## ## ## ",
    " ##    ## ",
    " ##    ## ",
    "          "
],

MED_FONT["n"] = [
    "          ",
    " ## ####  ",
    " ###  ##  ",
    " ##   ##  ",
    " ##   ##  ",
    " ##   ##  ",
    " ##   ##  ",
    "          "
],

MED_FONT["o"] = [
    "          ",
    "   ####   ",
    "  ##  ##  ",
    " ##    ## ",
    " ##    ## ",
    "  ##  ##  ",
    "   ####   ",
    "          "
],

MED_FONT["p"] = [
    "          ",
    " ## ####  ",
    " ###   ## ",
    " ##    ## ",
    " ###   ## ",
    " #######  ",
    " ##       ",
    " ##       "
],

MED_FONT["q"] = [
    "          ",
    "   ###### ",
    "  ##   ## ",
    " ##    ## ",
    " ##   ### ",
    "  #### ## ",
    "       ## ",
    "       ## "
],

MED_FONT["r"] = [
    "          ",
    " ## ####  ",
    " ###   ## ",
    " ##       ",
    " ##       ",
    " ##       ",
    " ##       ",
    "          "
],

MED_FONT["s"] = [
    "          ",
    "  ######  ",
    " ##    ## ",
    "   ###    ",
    "      ### ",
    " ##    ## ",
    "  ######  ",
    "          "
],

MED_FONT["t"] = [
    "   ##     ",
    "   ##     ",
    " #######  ",
    "   ##     ",
    "   ##     ",
    "   ##     ",
    "    ####  ",
    "          "
],

MED_FONT["u"] = [
    "          ",
    " ##   ##  ",
    " ##   ##  ",
    " ##   ##  ",
    " ##   ##  ",
    " ##   ##  ",
    "  ######  ",
    "          "
],

MED_FONT["v"] = [
    "          ",
    " ##   ##  ",
    " ##   ##  ",
    "  ## ##   ",
    "  ## ##   ",
    "   ###    ",
    "    #     ",
    "          "
],

MED_FONT["w"] = [
    "          ",
    " ##   ##  ",
    " ##   ##  ",
    " ## # ##  ",
    " ######## ",
    " ### ###  ",
    " ##   ##  ",
    "          "
],

MED_FONT["x"] = [
    "          ",
    " ##   ##  ",
    "  ## ##   ",
    "   ###    ",
    "   ###    ",
    "  ## ##   ",
    " ##   ##  ",
    "          "
],

MED_FONT["y"] = [
    "          ",
    " ##   ##  ",
    " ##   ##  ",
    "  ## ##   ",
    "   ###    ",
    "    ##    ",
    "   ##     ",
    " ####     "
],

MED_FONT["z"] = [
    "          ",
    " #######  ",
    "     ##   ",
    "    ##    ",
    "   ##     ",
    "  ##      ",
    " #######  ",
    "          "
],

# ============================================================
# MEDIUM FONT DRAWING
# ============================================================

def draw_med_char(x, y, ch, color):
    lookup = ch
    if lookup not in MED_FONT:
        lookup = ch.upper()
    if lookup not in MED_FONT:
        return

    pattern = MED_FONT[lookup]
    ...
    # skip unknown characters
    if ch not in MED_FONT:
        return

    pattern = MED_FONT[ch]

    # validate glyph structure
    if not isinstance(pattern, list):
        return

    for row, line in enumerate(pattern):
        if not isinstance(line, str):
            continue  # skip malformed rows

        for col, pixel in enumerate(line):
            if pixel == "#":
                LCD.pixel(x + col, y + row, color)
                
def draw_med_text(x, y, text, color):
    text = sanitize_text(text)
    for i, ch in enumerate(text):
        draw_med_char(x + i * 12, y, ch, color)
    
# ============================================================
# ICONS
# ============================================================

def icon_battery(x, y, level, color):
    LCD.rect(x, y, 28, 12, color)
    LCD.fill_rect(x+28, y+4, 3, 4, color)
    bars = int((level / 100) * 4)
    for i in range(bars):
        LCD.fill_rect(x+3 + i*6, y+3, 5, 6, color)

def icon_circle_dot_small(x, y, color):
    # thick square icon
    LCD.rect(x+1, y+1, 12, 12, color)
    LCD.rect(x+3, y+3, 8, 8, color)
    LCD.fill_rect(x+5, y+5, 4, 4, color)

# ============================================================
# INITIALIZE LCD + BACKLIGHT
# ============================================================

pwm = PWM(Pin(BL))
pwm.freq(1000)
pwm.duty_u16(32768)

LCD = LCD_1inch3()
apply_theme()

# ============================================================
# BUTTONS
# ============================================================

keyA = Pin(15, Pin.IN, Pin.PULL_UP)
keyB = Pin(17, Pin.IN, Pin.PULL_UP)
keyX = Pin(19, Pin.IN, Pin.PULL_UP)
keyY = Pin(21, Pin.IN, Pin.PULL_UP)

up    = Pin(2, Pin.IN, Pin.PULL_UP)
down  = Pin(18, Pin.IN, Pin.PULL_UP)
left  = Pin(16, Pin.IN, Pin.PULL_UP)
right = Pin(20, Pin.IN, Pin.PULL_UP)
ctrl  = Pin(3, Pin.IN, Pin.PULL_UP)

def pressed(pin):
    return pin.value() == 0

# ============================================================
# TERMINAL EFFECTS
# ============================================================

def draw_scanlines():
    for yy in range(0, 240, 4):
        LCD.hline(0, yy, 240, PIP_DARK)

def draw_noise(density=150):
    for _ in range(density):
        x = urandom.getrandbits(8) % 240
        y = urandom.getrandbits(8) % 240
        if urandom.getrandbits(3) == 0:
            LCD.pixel(x, y, PIP_DIM)

def screen_flicker():
    LCD.fill(PIP_BLACK)
    LCD.show()
    utime.sleep_ms(40)
    draw_scanlines()
    LCD.show()
    utime.sleep_ms(40)

def draw_terminal_frame():
    LCD.rect(2, 48, 236, 190, PIP_GREEN)

def draw_footer(left_msg="B: BACK", right_msg="A: SELECT"):
    y = 220
    LCD.fill_rect(0, y-2, 240, 20, PIP_BLACK)
    if left_msg:
        draw_med_text(6, y, left_msg.upper(), PIP_GREEN)
    if right_msg:
        w = len(right_msg) * 10
        draw_med_text(240 - w - 6, y, right_msg.upper(), PIP_GREEN)

# ============================================================
# CORE HELPERS
# ============================================================

def pip_clear():
    LCD.fill(PIP_DARK)
    draw_scanlines()

def pip_title(msg):
    LCD.fill_rect(0, 48, 240, 20, PIP_BLACK)
    draw_med_text(16, 50, msg.upper(), PIP_GREEN)   # FIXED OFFSET
    draw_terminal_frame()

def draw_small_text(x, y, text, color):
    LCD.text(text, x, y, color)

def sanitize_text(s):
    out = ""
    for ch in s:
        if ch.upper() in MED_FONT:
            out += ch.upper()
        else:
            out += " "  # replace unknown with space
    return out

CONTENT_TOP = 72
CONTENT_BOTTOM = 220

# ============================================================
# STATUS BAR
# ============================================================

def draw_status_bar():
    LCD.fill_rect(0, 0, 240, 48, PIP_BLACK)

    t = utime.localtime()
    timestr = "{:02d}:{:02d}".format(t[3], t[4])
    datestr = "{:02d}/{:02d}".format(t[1], t[2])

    draw_med_text(8, 6, timestr, PIP_GREEN)
    draw_med_text(8, 24, datestr, PIP_GREEN)

    icon_circle_dot_small(150, 10, PIP_GREEN)
    icon_battery(190, 18, 75, PIP_GREEN)
    global UPDATE_STATE, UPDATE_STATE_TIME
    # Update icon (small square)
    # Update status icon
    state = UPDATE_STATE
    age = utime.time() - UPDATE_STATE_TIME

    # auto-clear after 5 minutes
    if age > 300:
        state = 0

    x = 190
    y = 6

    if state == 1:
    # TRYING: pulsing dot
        if (utime.ticks_ms() // 300) % 2 == 0:
            LCD.fill_rect(x+3, y+3, 4, 4, PIP_GREEN)
        else:
            LCD.rect(x+3, y+3, 4, 4, PIP_DIM)

    elif state == 2:
    # CONNECTED + UPDATING: solid square
        LCD.fill_rect(x, y, 8, 8, PIP_GREEN)
    elif state == 3:
    # SUCCESS: check-square
        LCD.rect(x, y, 8, 8, PIP_GREEN)
        LCD.pixel(x+2, y+4, PIP_GREEN)
        LCD.pixel(x+3, y+5, PIP_GREEN)
        LCD.pixel(x+4, y+3, PIP_GREEN)
        LCD.pixel(x+5, y+2, PIP_GREEN)

    elif state == 4:
    # FAIL: small X
        LCD.pixel(x+2, y+2, PIP_GREEN)
        LCD.pixel(x+5, y+5, PIP_GREEN)
        LCD.pixel(x+2, y+5, PIP_GREEN)
        LCD.pixel(x+5, y+2, PIP_GREEN)

# ============================================================
# BOOT: TERMINAL LOG + ANIMATION
# ============================================================

def boot_log():
    LCD.fill(PIP_BLACK)
    draw_scanlines()
    lines = [
        "[ OK ] INITIALIZING DISPLAY",
        "[ OK ] LOADING KERNEL MODULES",
        "[ OK ] MOUNTING FILESYSTEM",
        "[ OK ] STARTING TINYPIP OS"
    ]
    y = 40
    for line in lines:
        draw_med_text(10, y, line, PIP_GREEN)
        draw_noise(80)
        LCD.show()
        utime.sleep_ms(400)
        y += 18
    utime.sleep_ms(300)

def boot_animation():
    LCD.fill(PIP_BLACK)
    LCD.show()
    utime.sleep_ms(100)

    for i in range(3):
        LCD.fill(PIP_BLACK)
        LCD.rect(80, 41, 80, 80, PIP_DIM if i < 2 else PIP_GREEN)
        draw_med_text(40, 190, "VAULT-TEC SYSTEMS", PIP_GREEN)
        draw_scanlines()
        LCD.show()
        utime.sleep_ms(300)

    for i in range(4):
        LCD.fill(PIP_BLACK)
        LCD.rect(80, 41, 80, 80, PIP_GREEN)
        LCD.rect(92, 53, 56, 56, PIP_GREEN)
        LCD.rect(96, 57, 48, 48, PIP_GREEN)
        draw_med_text(90, 190, "ONLINE", PIP_GREEN if i % 2 == 0 else PIP_DIM)
        draw_scanlines()
        LCD.show()
        utime.sleep_ms(200)

    LCD.fill(PIP_DARK)
    draw_scanlines()
    LCD.show()

boot_log()
boot_animation()

# ============================================================
# MENU SYSTEM
# ============================================================

MENU = [
    "CLOCK",
    "STATUS",
    "ADD NOTE",
    "VIEW NOTES",
    "SYSTEM",
    "SETTINGS",
    "FILES",
    "STOPWATCH",
    "TIMER",
    "SNAKE",
    "WIFI SCANNER",
    "ADD WIFI",
    "BLUETOOTH SCANNER",
    "WEATHER",
    "GPS",
    "COMPASS",
    "TRACKER",
    "SET DATE",
    "SET TIME",
    "SHOOTER",
    "FLASHLIGHT"
]

menu_index = 0
menu_offset = 0
VISIBLE_ITEMS = 6

start_ticks = utime.ticks_ms()
brightness_level = 50  # 0–100

def apply_brightness():
    duty = int((brightness_level / 100) * 65535)
    pwm.duty_u16(duty)

def draw_menu():
    global menu_offset
    pip_clear()
    draw_status_bar()
    pip_title("TINYPIP OS")

    if menu_index < menu_offset:
        menu_offset = menu_index
    elif menu_index >= menu_offset + VISIBLE_ITEMS:
        menu_offset = menu_index - VISIBLE_ITEMS + 1

    blink = (utime.ticks_ms() // 400) % 2
    y = CONTENT_TOP
    row_height = 22

    for i in range(menu_offset, min(menu_offset + VISIBLE_ITEMS, len(MENU))):
        item = MENU[i]
        if i == menu_index:
            LCD.fill_rect(0, y - 2, 240, row_height, PIP_BLACK)
            if blink == 1:
                LCD.fill_rect(6, y, 6, row_height-4, PIP_GREEN)
            draw_med_text(40, y, item.upper(), PIP_GREEN)
        else:
            draw_med_text(40, y, item.upper(), PIP_GREEN)
        y += row_height

    draw_footer("A: SELECT", "B: BACK")
    draw_noise(120)
    LCD.show()

#MENU

def menu_loop():
    global menu_index
    global UPDATE_STATE, UPDATE_STATE_TIME   # ← REQUIRED

    while True:
        draw_menu()

        if pressed(up):
            menu_index = (menu_index - 1) % len(MENU)
            utime.sleep_ms(150)

        if pressed(down):
            menu_index = (menu_index + 1) % len(MENU)
            utime.sleep_ms(150)

        if pressed(keyA):
            utime.sleep_ms(200)
            return MENU[menu_index]

        # Y = UPDATE NOW  (NOW CORRECTLY INDENTED)
        if pressed(keyY):
            spinner = ["-", "\\", "|", "/"]

            # STATE: TRYING
            UPDATE_STATE = 1
            UPDATE_STATE_TIME = utime.time()

            for i in range(12):
                pip_clear()
                pip_title("UPDATING " + spinner[i % 4])
                LCD.show()
                utime.sleep_ms(100)

            ok = wifi_fallback_update()

            # STATE: SUCCESS / FAIL
            UPDATE_STATE = 3 if ok else 4
            UPDATE_STATE_TIME = utime.time()

            pip_clear()
            pip_title("UPDATED" if ok else "NO WIFI")
            LCD.show()
            utime.sleep_ms(1500)
            
# ============================================================
# NOTES HELPERS
# ============================================================

def save_note(text):
    try:
        with open("notes.txt", "a") as f:
            f.write(text + "\n")
    except:
        pass

# ============================================================
# MINIMAP HELPER (GPS + TRACKER)
# ============================================================

def draw_minimap(x, y, target_x=0.5, target_y=0.5, color=PIP_GREEN):
    w = 70
    h = 70

    LCD.rect(x, y, w, h, PIP_DIM)
    LCD.hline(x, y + h//2, w, PIP_DIM)
    LCD.vline(x + w//2, y, h, PIP_DIM)

    tx = max(0.0, min(1.0, target_x))
    ty = max(0.0, min(1.0, target_y))

    px = int(x + tx * (w-1))
    py = int(y + ty * (h-1))

    LCD.pixel(px, py, color)
    LCD.pixel(px+1, py, color)
    LCD.pixel(px, py+1, color)
    LCD.pixel(px+1, py+1, color)


# ============================================================
# Keyboard Input helper
# ============================================================

def keyboard_input(title="INPUT"):
    screen_flicker()

    keyboard = [
        "1234567890",
        "abcdefghij",
        "klmnopqrst",
        "uvwxyz _-.",
        "ABCDEFGHIJ",
        "KLMNOPQRST",
        "UVWXYZ"
    ]

    row = 0
    col = 0
    text = ""

    while True:
        pip_clear()
        draw_status_bar()
        pip_title(title)

        y = CONTENT_TOP
        for r, line in enumerate(keyboard):
            x = 10
            for c, ch in enumerate(line):
                # highlight selected key
                if r == row and c == col:
                    LCD.fill_rect(x - 2, y - 2, 16, 16, PIP_DIM)
                LCD.text(ch, x, y, PIP_GREEN)
                x += 14
            y += 20

        # typed text preview
        draw_med_text(10, 200, text, PIP_GREEN)

        draw_footer("A: SELECT", "B: BACK")
        LCD.show()

        # movement
        if pressed(left):
            col = max(0, col - 1)
            utime.sleep_ms(120)

        if pressed(right):
            col = min(len(keyboard[row]) - 1, col + 1)
            utime.sleep_ms(120)

        if pressed(up):
            row = max(0, row - 1)
            col = min(col, len(keyboard[row]) - 1)
            utime.sleep_ms(120)

        if pressed(down):
            row = min(len(keyboard) - 1, row + 1)
            col = min(col, len(keyboard[row]) - 1)
            utime.sleep_ms(120)

        # select key
        if pressed(keyA):
            key = keyboard[row][col]

            if key == "<":
                text = text[:-1]  # backspace
            elif key == " ":
                text += " "
            elif key == "O":  # OK
                return text
            else:
                text += key

            utime.sleep_ms(150)

        # cancel
        if pressed(keyB):
            return ""

        
# ============================================================
# APPS
# ============================================================

def app_clock():
    screen_flicker()
    while True:
        pip_clear()
        draw_status_bar()
        pip_title("CLOCK")

        t = utime.localtime()
        timestr = "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])
        draw_big_text(30, 120, timestr, PIP_GREEN)

        draw_footer("B: BACK", "")
        draw_noise(120)
        LCD.show()

        if pressed(keyB):
            utime.sleep_ms(200)
            return

        utime.sleep_ms(200)

# ==========================================
# STATUS app
# ===========================================

def app_status():
    screen_flicker()

    scroll_y = 0
    SCROLL_STEP = 14
    MAX_SCROLL = 120  # adjust if you add more lines

    start_time = utime.ticks_ms()

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("STATUS")

        y = CONTENT_TOP - scroll_y

        # --- DEVICE ---
        draw_med_text(10, y, "DEVICE", PIP_GREEN)
        y += 18
        draw_small_text(20, y, "Model: Pico 2 W", PIP_GREEN)
        y += 14
        draw_small_text(20, y, "OS: TinyPIP v1.8.0", PIP_GREEN)
        y += 20

        # --- SYSTEM ---
        draw_med_text(10, y, "SYSTEM", PIP_GREEN)
        y += 18

        # CPU MHz
        try:
            cpu = machine.freq() // 1000000
        except:
            cpu = 133
        draw_small_text(20, y, "CPU: {} MHz".format(cpu), PIP_GREEN)
        y += 14

        # Uptime
        uptime_ms = utime.ticks_ms() - start_time
        uptime_s = uptime_ms // 1000
        uptime_m = uptime_s // 60
        uptime_h = uptime_m // 60
        draw_small_text(20, y, "Uptime: {}h {}m".format(uptime_h, uptime_m % 60), PIP_GREEN)
        y += 14

        # RAM usage
        import gc
        free_ram = gc.mem_free()
        used_ram = gc.mem_alloc()
        draw_small_text(20, y, "RAM: {} used / {} free".format(used_ram, free_ram), PIP_GREEN)
        y += 20

        # --- NETWORK ---
        draw_med_text(10, y, "NETWORK", PIP_GREEN)
        y += 18

        wlan = network.WLAN(network.STA_IF)
        if wlan.active() and wlan.isconnected():
            ip = wlan.ifconfig()[0]
            draw_small_text(20, y, "WiFi: Connected", PIP_GREEN)
            y += 14
            draw_small_text(20, y, "IP: {}".format(ip), PIP_GREEN)
            y += 14
        else:
            draw_small_text(20, y, "WiFi: Offline", PIP_DIM)
            y += 20

        # --- BEACON STATUS ---
        draw_med_text(10, y, "BEACON", PIP_GREEN)
        y += 18

        beacon_found = False
        beacon_battery = None

        try:
            nets = wlan.scan()
        except:
            nets = []

        for n in nets:
            ssid = n[0].decode() if isinstance(n[0], bytes) else n[0]
            if ssid.startswith("BEACON"):
                beacon_found = True
                if "|" in ssid:
                    try:
                        beacon_battery = int(ssid.split("|")[1])
                    except:
                        beacon_battery = None
                break

        if beacon_found:
            draw_small_text(20, y, "Status: ONLINE", PIP_GREEN)
            y += 14
            if beacon_battery is not None:
                draw_small_text(20, y, "Battery: {}%".format(beacon_battery), PIP_GREEN)
                y += 14
        else:
            draw_small_text(20, y, "Status: OFFLINE", PIP_DIM)
            y += 20

        # --- STORAGE ---
        draw_med_text(10, y, "STORAGE", PIP_GREEN)
        y += 18

        try:
            fs = os.statvfs("/")
            total = (fs[0] * fs[2]) // 1024
            free = (fs[0] * fs[3]) // 1024
            used = total - free
            draw_small_text(20, y, "Used: {} KB".format(used), PIP_GREEN)
            y += 14
            draw_small_text(20, y, "Free: {} KB".format(free), PIP_GREEN)
            y += 14
        except:
            draw_small_text(20, y, "Storage: N/A", PIP_DIM)
            y += 14

        # FOOTER
        draw_footer("UP/DN: SCROLL", "B: BACK")
        draw_noise(120)
        LCD.show()

        # INPUT
        if pressed(up):
            scroll_y = max(0, scroll_y - SCROLL_STEP)
            utime.sleep_ms(120)

        if pressed(down):
            scroll_y = min(MAX_SCROLL, scroll_y + SCROLL_STEP)
            utime.sleep_ms(120)

        if pressed(keyB):
            utime.sleep_ms(200)
            return

        utime.sleep_ms(40)
        
#===========================================
        
def app_add_note():
    screen_flicker()
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,-!?"
    index = 0
    note = ""

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("ADD NOTE")

        draw_med_text(10, CONTENT_TOP,     "NOTE:", PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+18,  note[:18], PIP_GREEN)

        draw_med_text(10, CONTENT_TOP+48,  "CHAR: {}".format(chars[index]), PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+66,  "UP/DOWN: CHANGE", PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+84,  "A: ADD CHAR", PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+102, "X: SAVE", PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+120, "B: CANCEL", PIP_GREEN)

        draw_footer("A: ADD", "X: SAVE")
        draw_noise(120)
        LCD.show()

        if pressed(up):
            index = (index - 1) % len(chars)
            utime.sleep_ms(120)

        if pressed(down):
            index = (index + 1) % len(chars)
            utime.sleep_ms(120)

        if pressed(keyA):
            note += chars[index]
            utime.sleep_ms(120)

        if pressed(keyX):
            save_note(note)
            utime.sleep_ms(200)
            return

        if pressed(keyB):
            utime.sleep_ms(200)
            return

def app_view_notes():
    screen_flicker()
    pip_clear()
    draw_status_bar()
    pip_title("VIEW NOTES")

    try:
        with open("notes.txt") as f:
            lines = f.read().splitlines()
    except:
        lines = ["NO NOTES FOUND"]

    index = 0

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("VIEW NOTES")

        y = CONTENT_TOP
        for line in lines[index:index+6]:
            draw_med_text(10, y, line[:18], PIP_GREEN)
            y += 18

        draw_footer("UP/DOWN: SCROLL", "B: BACK")
        draw_noise(120)
        LCD.show()

        if pressed(up):
            index = max(0, index - 1)
            utime.sleep_ms(120)

        if pressed(down):
            if index < max(0, len(lines) - 6):
                index += 1
            utime.sleep_ms(120)

        if pressed(keyB):
            utime.sleep_ms(200)
            return
# =============================================================
# System app
# =============================================================

def app_system():
    screen_flicker()

    start_time = utime.ticks_ms()
    scroll_y = 0
    SCROLL_STEP = 14
    MAX_SCROLL = 120  # adjust if you add more lines

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("SYSTEM INFO")

        y = CONTENT_TOP - scroll_y

        # --- DEVICE SECTION ---
        draw_med_text(10, y, "DEVICE", PIP_GREEN)
        y += 18
        draw_small_text(20, y, "Model: Pico 2 W", PIP_GREEN)
        y += 14
        draw_small_text(20, y, "OS: TinyPIP v1.8.0", PIP_GREEN)
        y += 20

        # --- SYSTEM SECTION ---
        draw_med_text(10, y, "SYSTEM", PIP_GREEN)
        y += 18

        try:
            cpu = machine.freq() // 1000000
        except:
            cpu = 133
        draw_small_text(20, y, "CPU: {} MHz".format(cpu), PIP_GREEN)
        y += 14

        uptime_ms = utime.ticks_ms() - start_time
        uptime_s = uptime_ms // 1000
        uptime_m = uptime_s // 60
        uptime_h = uptime_m // 60
        draw_small_text(20, y, "Uptime: {}h {}m".format(uptime_h, uptime_m % 60), PIP_GREEN)
        y += 20

        # --- NETWORK SECTION ---
        draw_med_text(10, y, "NETWORK", PIP_GREEN)
        y += 18

        wlan = network.WLAN(network.STA_IF)
        if wlan.active() and wlan.isconnected():
            ip = wlan.ifconfig()[0]
            draw_small_text(20, y, "WiFi: Connected", PIP_GREEN)
            y += 14
            draw_small_text(20, y, "IP: {}".format(ip), PIP_GREEN)
            y += 14
        else:
            draw_small_text(20, y, "WiFi: Offline", PIP_DIM)
            y += 20

        # --- STORAGE SECTION ---
        draw_med_text(10, y, "STORAGE", PIP_GREEN)
        y += 18

        try:
            fs_stat = os.statvfs("/")
            total = (fs_stat[0] * fs_stat[2]) // 1024
            free = (fs_stat[0] * fs_stat[3]) // 1024
            used = total - free
            draw_small_text(20, y, "Used: {} KB".format(used), PIP_GREEN)
            y += 14
            draw_small_text(20, y, "Free: {} KB".format(free), PIP_GREEN)
            y += 14
        except:
            draw_small_text(20, y, "Storage: N/A", PIP_DIM)
            y += 14

        # FOOTER
        draw_footer("UP/DOWN: SCROLL", "B: BACK")
        draw_noise(120)
        LCD.show()

        # --- INPUT ---
        if pressed(up):
            scroll_y = max(0, scroll_y - SCROLL_STEP)
            utime.sleep_ms(120)

        if pressed(down):
            scroll_y = min(MAX_SCROLL, scroll_y + SCROLL_STEP)
            utime.sleep_ms(120)

        if pressed(keyB):
            utime.sleep_ms(200)
            return

        utime.sleep_ms(40)
        
        
# ==================================================
# Flashlight
# ==================================================

def app_flashlight():
    screen_flicker()

    # 0 = dim, 1 = medium, 2 = bright
    level = 1
    # 0 = white, 1 = green, 2 = red
    mode = 0

    def get_color():
        if mode == 0:  # white
            if level == 0:
                return colour(80, 80, 80)
            elif level == 1:
                return colour(160, 160, 160)
            else:
                return colour(255, 255, 255)
        elif mode == 1:  # green
            if level == 0:
                return colour(0, 60, 0)
            elif level == 1:
                return colour(0, 140, 0)
            else:
                return colour(0, 255, 0)
        else:  # red
            if level == 0:
                return colour(60, 0, 0)
            elif level == 1:
                return colour(140, 0, 0)
            else:
                return colour(255, 0, 0)

    while True:
        c = get_color()
        LCD.fill(c)

        draw_status_bar()
        pip_title("FLASHLIGHT")

        draw_med_text(10, CONTENT_TOP, "LEVEL: {}".format(level + 1), PIP_GREEN)
        mode_name = ["WHITE", "GREEN", "RED"][mode]
        draw_med_text(10, CONTENT_TOP + 18, "MODE: {}".format(mode_name), PIP_GREEN)

        draw_footer("A: MODE  UP/DN: BRIGHT", "B: BACK")
        LCD.show()

        if pressed(up):
            level = min(2, level + 1)
            utime.sleep_ms(150)

        if pressed(down):
            level = max(0, level - 1)
            utime.sleep_ms(150)

        if pressed(keyA):
            mode = (mode + 1) % 3
            utime.sleep_ms(150)

        if pressed(keyB):
            utime.sleep_ms(200)
            return

        utime.sleep_ms(40)
        
# ====================================================

def app_compass():
    screen_flicker()

    heading = 0  # degrees, 0 = North

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("COMPASS")

        # center of compass
        cx = 120
        cy = 140
        radius = 60

        # outer circle
        for angle in range(0, 360, 4):
            rad = math.radians(angle)
            px = int(cx + radius * math.cos(rad))
            py = int(cy + radius * math.sin(rad))
            if 0 <= px < 240 and 0 <= py < 240:
                LCD.pixel(px, py, PIP_GREEN)

        # cardinal marks
        LCD.text("N", cx - 3, cy - radius - 10, PIP_GREEN)
        LCD.text("S", cx - 3, cy + radius + 2, PIP_GREEN)
        LCD.text("W", cx - radius - 10, cy - 3, PIP_GREEN)
        LCD.text("E", cx + radius + 4, cy - 3, PIP_GREEN)

        # needle (red tip to North-ish)
        rad = math.radians(heading)
        nx = int(cx + (radius - 8) * math.sin(rad))
        ny = int(cy - (radius - 8) * math.cos(rad))
        LCD.line(cx, cy, nx, ny, colour(255, 60, 60))

        # tail (dim)
        tx = int(cx - (radius - 20) * math.sin(rad))
        ty = int(cy + (radius - 20) * math.cos(rad))
        LCD.line(cx, cy, tx, ty, PIP_DIM)

        # heading readout
        draw_med_text(70, CONTENT_TOP, "HEADING: {:03d}°".format(heading % 360), PIP_GREEN)
        draw_small_text(40, CONTENT_TOP + 20, "LEFT/RIGHT: ADJUST (VIRTUAL)", PIP_DIM)

        draw_footer("B: BACK", "")
        draw_noise(80)
        LCD.show()

        if pressed(left):
            heading = (heading - 5) % 360
            utime.sleep_ms(80)

        if pressed(right):
            heading = (heading + 5) % 360
            utime.sleep_ms(80)

        if pressed(keyB):
            utime.sleep_ms(200)
            return

        utime.sleep_ms(40)
        
        
# ==================================================

def app_settings():
    global brightness_level, COLOR_MODE
    screen_flicker()
    mode_index = 0
    modes = ["BRIGHTNESS", "COLOR MODE"]

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("SETTINGS")

        draw_med_text(10, CONTENT_TOP,     "UP/DOWN: SELECT OPTION", PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+18,  "A: CHANGE VALUE", PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+36,  "B: BACK", PIP_GREEN)

        y = CONTENT_TOP+60
        for i, m in enumerate(modes):
            if i == mode_index:
                LCD.fill_rect(0, y - 2, 240, 18, PIP_BLACK)
                LCD.fill_rect(6, y, 6, 14, PIP_GREEN)
            draw_med_text(40, y, m, PIP_GREEN)
            y += 18

        if modes[mode_index] == "BRIGHTNESS":
            draw_med_text(10, CONTENT_TOP+96, "LEVEL: {}%".format(brightness_level), PIP_GREEN)
        elif modes[mode_index] == "COLOR MODE":
            draw_med_text(10, CONTENT_TOP+96, "MODE: {}".format(COLOR_MODE), PIP_GREEN)

        draw_footer("A: CHANGE", "B: BACK")
        draw_noise(120)
        LCD.show()

        if pressed(up):
            mode_index = (mode_index - 1) % len(modes)
            utime.sleep_ms(150)

        if pressed(down):
            mode_index = (mode_index + 1) % len(modes)
            utime.sleep_ms(150)

        if pressed(keyA):
            if modes[mode_index] == "BRIGHTNESS":
                brightness_level += 10
                if brightness_level > 100:
                    brightness_level = 10
                apply_brightness()
            elif modes[mode_index] == "COLOR MODE":
                COLOR_MODE = "AMBER" if COLOR_MODE == "GREEN" else "GREEN"
                apply_theme()
            utime.sleep_ms(200)

        if pressed(keyB):
            utime.sleep_ms(200)
            return

        utime.sleep_ms(50)

def app_files():
    screen_flicker()
    pip_clear()
    draw_status_bar()
    pip_title("FILES")

    try:
        entries = os.listdir()
    except:
        entries = []

    if not entries:
        draw_med_text(10, CONTENT_TOP+10, "NO FILES FOUND", PIP_GREEN)
        draw_footer("B: BACK", "")
        draw_noise(120)
        LCD.show()
        while not pressed(keyB):
            utime.sleep_ms(50)
        return

    index = 0

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("FILES")

        y = CONTENT_TOP
        for name in entries[index:index+6]:
            draw_med_text(10, y, name[:18], PIP_GREEN)
            y += 18

        draw_footer("UP/DOWN: SCROLL", "B: BACK")
        draw_noise(120)
        LCD.show()

        if pressed(up):
            index = max(0, index - 1)
            utime.sleep_ms(120)

        if pressed(down):
            if index < max(0, len(entries) - 6):
                index += 1
            utime.sleep_ms(120)

        if pressed(keyB):
            utime.sleep_ms(200)
            return

def app_stopwatch():
    screen_flicker()
    running = False
    start_time = 0
    elapsed = 0

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("STOPWATCH")

        if running:
            elapsed = utime.ticks_diff(utime.ticks_ms(), start_time)

        total_s = elapsed // 1000
        mins = total_s // 60
        secs = total_s % 60

        timestr = "{:02d}:{:02d}".format(mins, secs)
        draw_big_text(40, 120, timestr, PIP_GREEN)

        draw_footer("A: START/STOP", "B: RESET/BACK")
        draw_noise(120)
        LCD.show()

        if pressed(keyA):
            if not running:
                start_time = utime.ticks_ms() - elapsed
                running = True
            else:
                running = False
            utime.sleep_ms(200)

        if pressed(keyB):
            if elapsed > 0:
                elapsed = 0
                running = False
                utime.sleep_ms(200)
            else:
                utime.sleep_ms(200)
                return

        utime.sleep_ms(50)

def app_timer():
    screen_flicker()
    minutes = 1
    running = False
    end_time = 0

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("TIMER")

        draw_med_text(10, CONTENT_TOP,     "UP/DOWN: SET MINUTES", PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+18,  "A: START/STOP", PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+36,  "B: BACK", PIP_GREEN)

        if not running:
            timestr = "{:02d}:00".format(minutes)
        else:
            remaining_ms = utime.ticks_diff(end_time, utime.ticks_ms())
            if remaining_ms <= 0:
                remaining_ms = 0
                running = False
            total_s = remaining_ms // 1000
            m = total_s // 60
            s = total_s % 60
            timestr = "{:02d}:{:02d}".format(m, s)

        draw_big_text(40, 130, timestr, PIP_GREEN)

        draw_footer("A: START/STOP", "B: BACK")
        draw_noise(120)
        LCD.show()

        if not running:
            if pressed(up):
                minutes = min(99, minutes + 1)
                utime.sleep_ms(150)
            if pressed(down):
                minutes = max(1, minutes - 1)
                utime.sleep_ms(150)

        if pressed(keyA):
            if not running:
                end_time = utime.ticks_ms() + minutes * 60 * 1000
                running = True
            else:
                running = False
            utime.sleep_ms(200)

        if pressed(keyB):
            utime.sleep_ms(200)
            return

        utime.sleep_ms(50)

def app_snake():
    screen_flicker()
    grid_size = 10
    cell = 14
    offset_x = 25
    offset_y = CONTENT_TOP

    snake = [(5, 5), (4, 5), (3, 5)]
    direction = (1, 0)
    food = (8, 5)
    alive = True
    last_move = utime.ticks_ms()

    def draw_grid():
        pip_clear()
        draw_status_bar()
        pip_title("SNAKE")
        LCD.rect(offset_x-2, offset_y-2, grid_size*cell+4, grid_size*cell+4, PIP_GREEN)
        for (sx, sy) in snake:
            LCD.fill_rect(offset_x + sx*cell, offset_y + sy*cell, cell-2, cell-2, PIP_GREEN)
        LCD.fill_rect(offset_x + food[0]*cell+3, offset_y + food[1]*cell+3, cell-6, cell-6, PIP_GREEN)
        draw_footer("B: BACK", "")
        draw_noise(120)
        LCD.show()

    def spawn_food():
        while True:
            fx = urandom.getrandbits(4) % grid_size
            fy = urandom.getrandbits(4) % grid_size
            if (fx, fy) not in snake:
                return (fx, fy)

    while True:
        if not alive:
            pip_clear()
            draw_status_bar()
            pip_title("SNAKE")
            draw_med_text(40, 120, "GAME OVER", PIP_GREEN)
            draw_footer("B: BACK", "")
            draw_noise(120)
            LCD.show()
            if pressed(keyB):
                utime.sleep_ms(200)
                return
            utime.sleep_ms(100)
            continue

        draw_grid()

        if pressed(up) and direction != (0, 1):
            direction = (0, -1)
        elif pressed(down) and direction != (0, -1):
            direction = (0, 1)
        elif pressed(left) and direction != (1, 0):
            direction = (-1, 0)
        elif pressed(right) and direction != (-1, 0):
            direction = (1, 0)

        if pressed(keyB):
            utime.sleep_ms(200)
            return

        if utime.ticks_diff(utime.ticks_ms(), last_move) > 220:
            last_move = utime.ticks_ms()
            head = snake[0]
            new_head = (head[0] + direction[0], head[1] + direction[1])

            if (new_head[0] < 0 or new_head[0] >= grid_size or
                new_head[1] < 0 or new_head[1] >= grid_size or
                new_head in snake):
                alive = False
                continue

            snake.insert(0, new_head)
            if new_head == food:
                food = spawn_food()
            else:
                snake.pop()

        utime.sleep_ms(20)

# ============================================================
# WIFI SCANNER + DETAILS
# ============================================================

def app_wifi_details(net):
    ssid, bssid, channel, rssi, auth, hidden = net

    freq = 2412
    distance = 10 ** ((27.55 - (20 * math.log10(freq)) + abs(rssi)) / 20)

    screen_flicker()
    while True:
        pip_clear()
        draw_status_bar()
        pip_title("WIFI INFO")

        ssid_str = ssid.decode() if isinstance(ssid, bytes) else ssid
        bssid_hex = ":".join(["{:02X}".format(b) for b in bssid])

        draw_med_text(10, CONTENT_TOP,     "SSID: " + ssid_str[:12], PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+18,  "BSSID: " + bssid_hex, PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+36,  "RSSI: {} dBm".format(rssi), PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+54,  "CHAN: {}".format(channel), PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+72,  "DIST: {:.1f} m".format(distance), PIP_GREEN)

        bar = max(0, min(100, 100 + rssi))
        LCD.fill_rect(10, CONTENT_TOP+96, bar, 10, PIP_GREEN)

        draw_footer("B: BACK", "")
        draw_noise(120)
        LCD.show()

        if pressed(keyB):
            utime.sleep_ms(200)
            return

def app_wifi_scanner():
    screen_flicker()
    wlan = network.WLAN(network.STA_IF)
    if not wlan.active():
        wlan.active(True)

    nets = []
    index = 0

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("WIFI SCANNER")

        try:
            nets = wlan.scan()
        except:
            nets = []

        if not nets:
            draw_med_text(10, CONTENT_TOP, "NO NETWORKS FOUND", PIP_GREEN)
        else:
            if index >= len(nets):
                index = len(nets) - 1
            y = CONTENT_TOP
            for i, n in enumerate(nets[index:index+6]):
                ssid = n[0].decode() if isinstance(n[0], bytes) else n[0]
                rssi = n[3]
                line = "{} ({})".format(ssid[:10], rssi)
                if i == 0:
                    LCD.fill_rect(0, y-2, 240, 18, PIP_BLACK)
                draw_med_text(10, y, line, PIP_GREEN)
                y += 18

        draw_footer("A: DETAILS", "B: BACK")
        draw_noise(120)
        LCD.show()

        if pressed(up):
            if index > 0:
                index -= 1
            utime.sleep_ms(150)

        if pressed(down):
            if nets and index < len(nets) - 1:
                index += 1
            utime.sleep_ms(150)

        if pressed(keyA) and nets:
            utime.sleep_ms(200)
            app_wifi_details(nets[index])

        if pressed(keyB):
            utime.sleep_ms(200)
            return

        utime.sleep_ms(200)

# ===========================================================
# ADD WIFI app
# ===========================================================

def app_add_wifi():
    screen_flicker()

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # --- SCAN ---
    pip_clear()
    draw_status_bar()
    pip_title("SCAN WIFI")
    draw_med_text(20, CONTENT_TOP, "Scanning...", PIP_GREEN)
    LCD.show()

    nets = wlan.scan()
    networks = []

    for n in nets:
        ssid = n[0].decode() if isinstance(n[0], bytes) else n[0]
        if len(ssid) > 0:
            networks.append(ssid)

    if not networks:
        pip_clear()
        draw_status_bar()
        pip_title("ADD WIFI")
        draw_med_text(20, CONTENT_TOP, "No networks found", PIP_RED)
        draw_footer("B: BACK", "")
        LCD.show()
        while not pressed(keyB):
            utime.sleep_ms(50)
        return

    index = 0

    # --- SELECT NETWORK ---
    while True:
        pip_clear()
        draw_status_bar()
        pip_title("ADD WIFI")

        y = CONTENT_TOP
        for i, ssid in enumerate(networks):
            color = PIP_GREEN if i == index else PIP_DIM
            draw_med_text(20, y, ssid, color)
            y += 20

        draw_footer("A: SELECT", "B: BACK")
        LCD.show()

        if pressed(up):
            index = (index - 1) % len(networks)
            utime.sleep_ms(120)

        if pressed(down):
            index = (index + 1) % len(networks)
            utime.sleep_ms(120)

        if pressed(keyA):
            ssid = networks[index]
            break

        if pressed(keyB):
            return

    # --- ENTER PASSWORD ---
    password = keyboard_input("PASSWORD")

# --- RESET WIFI STACK ---
    ap = network.WLAN(network.AP_IF)
    ap.active(False)

    wlan = network.WLAN(network.STA_IF)
    wlan.active(False)
    utime.sleep_ms(200)
    wlan.active(True)
    utime.sleep_ms(200)

# --- CONNECT ---
    wlan.connect(ssid, password)

    timeout = 0
    while not wlan.isconnected() and timeout < 150:
        utime.sleep_ms(100)
        timeout += 1
        
    for _ in range(120):  # 12 seconds
        if wlan.isconnected():
            break
        utime.sleep_ms(100)

    if not wlan.isconnected():
        pip_clear()
        draw_status_bar()
        pip_title("FAILED")
        draw_med_text(20, CONTENT_TOP, "Connection failed", PIP_RED)
        draw_footer("B: BACK", "")
        LCD.show()
        while not pressed(keyB):
            utime.sleep_ms(50)
        return

    # --- SAVE CREDENTIALS ---
    try:
        with open("wifi.json", "w") as f:
            f.write(json.dumps({"ssid": ssid, "password": password}))
    except:
        pass

    # --- AUTO UPDATE TIME ---
    try:
        ntptime.settime()
    except:
        pass

    # --- AUTO UPDATE WEATHER ---
    try:
        update_weather()
    except:
        pass

    # --- SUCCESS ---
    pip_clear()
    draw_status_bar()
    pip_title("CONNECTED")
    draw_med_text(20, CONTENT_TOP, "WiFi Connected!", PIP_GREEN)
    draw_med_text(20, CONTENT_TOP + 20, ssid, PIP_GREEN)
    draw_footer("B: BACK", "")
    LCD.show()

    while not pressed(keyB):
        utime.sleep_ms(50)


# ============================================================
# BLUETOOTH SCANNER (BASIC)
# ============================================================

def app_bluetooth_scanner():
    screen_flicker()
    if not HAS_BLE:
        pip_clear()
        draw_status_bar()
        pip_title("BLUETOOTH")
        draw_med_text(10, CONTENT_TOP+10, "BLE NOT AVAILABLE", PIP_GREEN)
        draw_footer("B: BACK", "")
        draw_noise(120)
        LCD.show()
        while not pressed(keyB):
            utime.sleep_ms(50)
        return

    ble = bluetooth.BLE()
    ble.active(True)
    devices = []

    def scan_cb(addr_type, addr, adv_type, rssi, adv_data):
        name = ""
        try:
            name = adv_data.decode(errors="ignore")
        except:
            name = ""
        devices.append((addr, rssi, name))

    # NOTE: MicroPython BLE API differs by port; this is a placeholder.
    # You may need to adapt to your firmware's BLE scan API.

    start = utime.ticks_ms()
    while utime.ticks_diff(utime.ticks_ms(), start) < 3000:
        utime.sleep_ms(100)

    index = 0

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("BLUETOOTH")

        if not devices:
            draw_med_text(10, CONTENT_TOP, "NO DEVICES FOUND", PIP_GREEN)
        else:
            if index >= len(devices):
                index = len(devices) - 1
            y = CONTENT_TOP
            for i, d in enumerate(devices[index:index+6]):
                addr, rssi, name = d
                addr_str = ":".join(["{:02X}".format(b) for b in addr])
                line = "{} {}".format(addr_str[-8:], rssi)
                if i == 0:
                    LCD.fill_rect(0, y-2, 240, 18, PIP_BLACK)
                draw_med_text(10, y, line[:18], PIP_GREEN)
                y += 18

        draw_footer("B: BACK", "")
        draw_noise(120)
        LCD.show()

        if pressed(up):
            if index > 0:
                index -= 1
            utime.sleep_ms(150)

        if pressed(down):
            if devices and index < len(devices) - 1:
                index += 1
            utime.sleep_ms(150)

        if pressed(keyB):
            utime.sleep_ms(200)
            ble.active(False)
            return

        utime.sleep_ms(200)

# ============================================================
# WEATHER APP
# ============================================================
def draw_icon(x, y, code, color):
    # All icons are 12×12 pixel blocks

    if code == "CLEAR":
        # Simple sun: square center + rays
        LCD.fill_rect(x+4, y+4, 4, 4, color)
        LCD.pixel(x+6, y+1, color)
        LCD.pixel(x+6, y+10, color)
        LCD.pixel(x+1, y+6, color)
        LCD.pixel(x+10, y+6, color)

    elif code == "CLOUDY":
        # Cloud shape using rectangles
        LCD.fill_rect(x+2, y+6, 8, 4, color)
        LCD.fill_rect(x+4, y+4, 6, 3, color)

    elif code == "RAIN":
        # Cloud + rain drops
        LCD.fill_rect(x+2, y+4, 8, 4, color)
        LCD.pixel(x+4, y+9, color)
        LCD.pixel(x+7, y+9, color)
        LCD.pixel(x+10, y+9, color)

    elif code == "PART":
        # Half sun + cloud
        LCD.fill_rect(x+2, y+6, 8, 4, color)   # cloud
        LCD.fill_rect(x+4, y+4, 3, 3, color)   # sun core
        LCD.pixel(x+5, y+2, color)             # sun ray

    else:
        # Unknown → X
        LCD.pixel(x+4, y+4, color)
        LCD.pixel(x+7, y+7, color)
        LCD.pixel(x+4, y+7, color)
        LCD.pixel(x+7, y+4, color)
# Weather Update
def get_weather_data():
    try:
        with open("weather.json") as f:
            data = json.loads(f.read())
            return data
    except:
        # fallback if file missing or corrupted
        return {
            "today": ("ERR", "--", "NO DATA"),
            "week": []
        }
# app
def app_weather():
    screen_flicker()
    page = 0  # 0 = today, 1 = week

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("WEATHER")

        data = get_weather_data()

        # -------------------------------
        # TODAY VIEW
        # -------------------------------
        if page == 0:
            day, temp, cond = data["today"]

            # Icon
            draw_icon(10, CONTENT_TOP, cond, PIP_GREEN)

            # Text
            draw_med_text(40, CONTENT_TOP, day, PIP_GREEN)
            draw_med_text(40, CONTENT_TOP+24, temp, PIP_GREEN)
            draw_med_text(40, CONTENT_TOP+48, cond, PIP_GREEN)

            draw_footer("A: WEEK", "B: BACK")

        # -------------------------------
        # WEEK VIEW (7‑day grid)
        # -------------------------------
        else:
            y = CONTENT_TOP
            for d, t, c in data["week"]:
                # Icon
                draw_icon(10, y, c, PIP_GREEN)

                # DAY TEMP COND
                draw_small_text(30, y, d, PIP_GREEN)
                draw_small_text(70, y, t, PIP_GREEN)
                draw_small_text(120, y, c, PIP_GREEN)

                y += 20

            draw_footer("A: TODAY", "B: BACK")

        draw_noise(120)
        LCD.show()

        # Controls
        if pressed(keyA):
            page = 1 - page
            utime.sleep_ms(200)

        if pressed(keyB):
            utime.sleep_ms(200)
            return
# Updater
import urequests
import json
import utime

# Your location (Flint area)
LAT = 43.0
LON = -83.7

# Map Open‑Meteo weather codes → TinyPIP condition strings
def map_code(code):
    if code in (0, 1):
        return "CLEAR"
    if code in (2,):
        return "PART"
    if code in (3,):
        return "CLOUDY"
    if code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return "RAIN"
    return "CLOUDY"

def update_weather():
    try:
        # Request daily + current weather
        url = (
            "https://api.open-meteo.com/v1/forecast?"
            f"latitude={LAT}&longitude={LON}"
            "&current_weather=true"
            "&daily=weathercode,temperature_2m_max"
            "&timezone=auto"
        )

        r = urequests.get(url)
        data = r.json()
        r.close()

        # -------------------------------
        # TODAY
        # -------------------------------
        temp_now = int(data["current_weather"]["temperature"])
        code_now = map_code(data["current_weather"]["weathercode"])

        today = (
            "TODAY",
            f"{temp_now}F",
            code_now
        )

        # -------------------------------
        # WEEK (7‑day forecast)
        # -------------------------------
        week = []
        days = ["MON","TUE","WED","THU","FRI","SAT","SUN"]

        temps = data["daily"]["temperature_2m_max"]
        codes = data["daily"]["weathercode"]

        for i in range(7):
            t = int(temps[i])
            c = map_code(codes[i])
            week.append((days[i], f"{t}F", c))

        # -------------------------------
        # FINAL STRUCTURE
        # -------------------------------
        final = {
            "today": today,
            "week": week
        }

        # Write to weather.json
        with open("weather.json", "w") as f:
            f.write(json.dumps(final))

        return True

    except Exception as e:
        print("WEATHER UPDATE ERROR:", e)
        return False
    
# ============================================================
# GPS (MOCK) APP
# ============================================================

def get_gps_data():
    return {
        "lat": 43.0123,
        "lon": -83.6870,
        "fix": True,
        "sats": 7,
        "map_x": 0.5,
        "map_y": 0.5
    }

def app_gps():
    screen_flicker()
    while True:
        pip_clear()
        draw_status_bar()
        pip_title("GPS")

        gps = get_gps_data()

        draw_med_text(10, CONTENT_TOP,     "LAT: {:.4f}".format(gps["lat"]), PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+24,  "LON: {:.4f}".format(gps["lon"]), PIP_GREEN)
        draw_med_text(10, CONTENT_TOP+48,  "SAT: {} FIX: {}".format(gps["sats"], gps["fix"]), PIP_GREEN)

        draw_minimap(150, CONTENT_TOP, gps["map_x"], gps["map_y"])

        draw_footer("B: BACK", "")
        draw_noise(120)
        LCD.show()

        if pressed(keyB):
            utime.sleep_ms(200)
            return

# ============================================================
# BEACON APP (DRAGON BALL STYLE)
# ============================================================

def app_tracker():
    screen_flicker()

    wlan = network.WLAN(network.STA_IF)
    if not wlan.active():
        wlan.active(True)

    pulse = 0  # radar pulse animation counter

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("BEACON TRACKER")

        # --- RSSI AVERAGING ---
        rssi_values = []
        ssid_found = None

        for _ in range(8):
            try:
                nets = wlan.scan()
            except:
                nets = []

            for n in nets:
                raw_ssid = n[0].decode() if isinstance(n[0], bytes) else n[0]
                if raw_ssid.startswith("BEACON"):
                    ssid_found = raw_ssid
                    rssi_values.append(n[3])
                    break

            utime.sleep_ms(30)

        found = ssid_found is not None and len(rssi_values) > 0

        # --- Parse battery from SSID ---
        battery = None
        if found and "|" in ssid_found:
            try:
                battery = int(ssid_found.split("|")[1])
            except:
                battery = None

        if found:
            avg_rssi = sum(rssi_values) / len(rssi_values)

            freq = 2412
            distance = 10 ** ((27.55 - (20 * math.log10(freq)) + abs(avg_rssi)) / 20)

            draw_med_text(10, CONTENT_TOP, "BEACON FOUND", PIP_GREEN)
            draw_med_text(10, CONTENT_TOP+18, "DIST: {:.1f} m".format(distance), PIP_GREEN)

            if battery is not None:
                draw_med_text(10, CONTENT_TOP+36, "BAT: {}%".format(battery), PIP_GREEN)

            bar = max(0, min(100, 100 + int(avg_rssi)))
            LCD.fill_rect(10, CONTENT_TOP+54, bar, 12, PIP_GREEN)

            tpos = max(0.0, min(1.0, (100 + avg_rssi) / 100.0))
        else:
            draw_med_text(10, CONTENT_TOP, "SEARCHING...", PIP_DIM)
            tpos = 0.5

        # --- MINIMAP LOWERED ---
        map_x = 150
        map_y = CONTENT_TOP + 70
        draw_minimap(map_x, map_y, tpos, 0.5)

        # --- RADAR PULSE RING ---
        pulse = (pulse + 1) % 30
        radius = pulse

        cx = map_x + 35
        cy = map_y + 35

        fade = max(20, 120 - radius * 4)
        pulse_color = colour(0, fade, 0)

        for angle in range(0, 360, 10):
            rad = math.radians(angle)
            px = int(cx + radius * math.cos(rad))
            py = int(cy + radius * math.sin(rad))
            if 0 <= px < 240 and 0 <= py < 240:
                LCD.pixel(px, py, pulse_color)

        # --- PULSING DOT ---
        dot_radius = 3 + (pulse // 6)
        dot_color = PIP_GREEN if found else PIP_DIM

        dot_x = int(map_x + tpos * 70)
        dot_y = int(map_y + 0.5 * 70)

        for angle in range(0, 360, 20):
            rad = math.radians(angle)
            px = int(dot_x + dot_radius * math.cos(rad))
            py = int(dot_y + dot_radius * math.sin(rad))
            if 0 <= px < 240 and 0 <= py < 240:
                LCD.pixel(px, py, dot_color)

        LCD.pixel(dot_x, dot_y, dot_color)

        draw_footer("B: BACK", "")
        draw_noise(120)
        LCD.show()

        if pressed(keyB):
            utime.sleep_ms(200)
            return

        utime.sleep_ms(40)
        
# ============================================================
# SET DATE / SET TIME APPS
# ============================================================

def app_set_date():
    screen_flicker()
    year, month, day, weekday, hour, minute, second, sub = rtc.datetime()
    cursor = 0  # 0=year,1=month,2=day

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("SET DATE")

        labels = ["YEAR", "MONTH", "DAY"]
        values = [year, month, day]

        for i, label in enumerate(labels):
            draw_med_text(10, CONTENT_TOP + i*24,
                          label + ":", PIP_GREEN if cursor == i else PIP_DIM)
            draw_med_text(130, CONTENT_TOP + i*24,
                          str(values[i]), PIP_GREEN)

        draw_footer("A: APPLY", "B: BACK")
        draw_noise(120)
        LCD.show()

        if pressed(up):
            if cursor == 0:
                year += 1
            elif cursor == 1:
                month = 1 if month >= 12 else month + 1
            elif cursor == 2:
                day = 1 if day >= 31 else day + 1
            utime.sleep_ms(150)

        if pressed(down):
            if cursor == 0:
                year -= 1
            elif cursor == 1:
                month = 12 if month <= 1 else month - 1
            elif cursor == 2:
                day = 31 if day <= 1 else day - 1
            utime.sleep_ms(150)

        if pressed(left):
            cursor = (cursor - 1) % 3
            utime.sleep_ms(150)

        if pressed(right):
            cursor = (cursor + 1) % 3
            utime.sleep_ms(150)

        if pressed(keyA):
            rtc.datetime((year, month, day, weekday, hour, minute, second, sub))
            utime.sleep_ms(200)
            return

        if pressed(keyB):
            utime.sleep_ms(200)
            return

def app_set_time():
    screen_flicker()
    year, month, day, weekday, hour, minute, second, sub = rtc.datetime()
    cursor = 0  # 0=hour,1=minute,2=second

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("SET TIME")

        labels = ["HOUR", "MINUTE", "SECOND"]
        values = [hour, minute, second]

        for i, label in enumerate(labels):
            draw_med_text(10, CONTENT_TOP + i*24,
                          label + ":", PIP_GREEN if cursor == i else PIP_DIM)
            draw_med_text(130, CONTENT_TOP + i*24,
                          "{:02d}".format(values[i]), PIP_GREEN)

        draw_footer("A: APPLY", "B: BACK")
        draw_noise(120)
        LCD.show()

        if pressed(up):
            if cursor == 0:
                hour = (hour + 1) % 24
            elif cursor == 1:
                minute = (minute + 1) % 60
            elif cursor == 2:
                second = (second + 1) % 60
            utime.sleep_ms(150)

        if pressed(down):
            if cursor == 0:
                hour = (hour - 1) % 24
            elif cursor == 1:
                minute = (minute - 1) % 60
            elif cursor == 2:
                second = (second - 1) % 60
            utime.sleep_ms(150)

        if pressed(left):
            cursor = (cursor - 1) % 3
            utime.sleep_ms(150)

        if pressed(right):
            cursor = (cursor + 1) % 3
            utime.sleep_ms(150)

        if pressed(keyA):
            rtc.datetime((year, month, day, weekday, hour, minute, second, sub))
            utime.sleep_ms(200)
            return

        if pressed(keyB):
            utime.sleep_ms(200)
            return
# ============================================================
# PIP Shooter game.
# ============================================================

def app_shooter():
    screen_flicker()

    # Player
    px = 120
    py = 210
    p_speed = 4

    # Bullets
    bullets = []

    # Enemies
    enemies = []
    enemy_timer = 0
    enemy_speed = 2

    score = 0
    lives = 3

    while True:
        pip_clear()
        draw_status_bar()
        pip_title("PIP-SHOOTER")

        # --- INPUT ---
        if pressed(left):
            px -= p_speed
        if pressed(right):
            px += p_speed
        if pressed(keyA):
            bullets.append([px, py - 10])

        # Clamp player
        px = max(10, min(230, px))

        # --- UPDATE BULLETS ---
        for b in bullets:
            b[1] -= 6
        bullets = [b for b in bullets if b[1] > 0]

        # --- SPAWN ENEMIES ---
        enemy_timer += 1
        if enemy_timer > 20:
            enemy_timer = 0
            enemies.append([random.randint(10, 230), 0])

        # --- UPDATE ENEMIES ---
        for e in enemies:
            e[1] += enemy_speed

        # --- COLLISIONS ---
        for b in bullets:
            for e in enemies:
                if abs(b[0] - e[0]) < 10 and abs(b[1] - e[1]) < 10:
                    score += 1
                    e[1] = 999  # remove enemy
                    b[1] = -999 # remove bullet

        enemies = [e for e in enemies if e[1] < 240]

        # --- ENEMY HITS BOTTOM ---
        for e in enemies:
            if e[1] > 200:
                lives -= 1
                e[1] = 999

        if lives <= 0:
            pip_clear()
            draw_status_bar()
            pip_title("GAME OVER")
            draw_med_text(40, 120, "SCORE: {}".format(score), PIP_GREEN)
            draw_footer("B: BACK", "")
            LCD.show()
            while not pressed(keyB):
                utime.sleep_ms(50)
            return

        # --- DRAW PLAYER ---
        LCD.fill_rect(px - 5, py - 5, 10, 10, PIP_GREEN)

        # --- DRAW BULLETS ---
        for b in bullets:
            LCD.fill_rect(b[0] - 1, b[1] - 4, 2, 4, colour(180, 255, 180))

        # --- DRAW ENEMIES ---
        for e in enemies:
            LCD.fill_rect(e[0] - 5, e[1] - 5, 10, 10, colour(255, 60, 60))

        # --- HUD ---
        draw_med_text(10, CONTENT_TOP, "SCORE: {}".format(score), PIP_GREEN)
        draw_med_text(150, CONTENT_TOP, "LIVES: {}".format(lives), PIP_GREEN)

        draw_footer("B: BACK", "")
        draw_noise(120)
        LCD.show()

        if pressed(keyB):
            utime.sleep_ms(200)
            return

        utime.sleep_ms(30)


# ============================================================
# MAIN LOOP
# ============================================================

while True:
    choice = menu_loop()

    if choice == "CLOCK":
        app_clock()
    elif choice == "STATUS":
        app_status()
    elif choice == "ADD NOTE":
        app_add_note()
    elif choice == "VIEW NOTES":
        app_view_notes()
    elif choice == "SYSTEM":
        app_system()
    elif choice == "SETTINGS":
        app_settings()
    elif choice == "FILES":
        app_files()
    elif choice == "STOPWATCH":
        app_stopwatch()
    elif choice == "TIMER":
        app_timer()
    elif choice == "SNAKE":
        app_snake()
    elif choice == "WIFI SCANNER":
        app_wifi_scanner()
    elif choice == "BLUETOOTH SCANNER":
        app_bluetooth_scanner()
    elif choice == "WEATHER":
        app_weather()
    elif choice == "GPS":
        app_gps()
    elif choice == "TRACKER":
        app_tracker()
    elif choice == "SET DATE":
        app_set_date()
    elif choice == "SET TIME":
        app_set_time()
    elif choice == "SHOOTER":
        app_shooter()
    elif choice == "FLASHLIGHT":
        app_flashlight()
    elif choice == "COMPASS":
        app_compass()
    elif choice == "ADD WIFI":
        app_add_wifi()