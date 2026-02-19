#!/usr/bin/env python3
"""Conch Shell Phone — a time-based audio art installation."""

import os
import sys
import time
import random
import signal
import logging
import subprocess
import atexit
from logging.handlers import RotatingFileHandler

# Resolve paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
STATE_FILE = os.path.join(BASE_DIR, "track_state.txt")
LOG_FILE = os.path.join(BASE_DIR, "conch.log")

# GPIO pin (BCM numbering)
BUTTON_PIN = 17

# Polling interval (seconds)
POLL_INTERVAL = 0.1

TRACK_CONFIG = [
    {"file": "01.mp3", "silence_min": 15, "silence_max": 20},
    {"file": "02.mp3", "silence_min": 20, "silence_max": 25},
    {"file": "03.mp3", "silence_min": 18, "silence_max": 22},
    {"file": "04.mp3", "silence_min": 16, "silence_max": 21},
    {"file": "05.mp3", "silence_min": 19, "silence_max": 24},
    {"file": "06.mp3", "silence_min": 15, "silence_max": 20},
    {"file": "07.mp3", "silence_min": 22, "silence_max": 25},
    {"file": "08.mp3", "silence_min": 17, "silence_max": 22},
    {"file": "09.mp3", "silence_min": 20, "silence_max": 25},
    {"file": "10.mp3", "silence_min": 16, "silence_max": 21},
    {"file": "11.mp3", "silence_min": 18, "silence_max": 23},
    {"file": "12.mp3", "silence_min": 15, "silence_max": 20},
    {"file": "13.mp3", "silence_min": 21, "silence_max": 25},
    {"file": "14.mp3", "silence_min": 17, "silence_max": 22},
    {"file": "15.mp3", "silence_min": 19, "silence_max": 24},
    {"file": "16.mp3", "silence_min": 16, "silence_max": 21},
    {"file": "17.mp3", "silence_min": 20, "silence_max": 25},
    {"file": "18.mp3", "silence_min": 15, "silence_max": 20},
    {"file": "19.mp3", "silence_min": 18, "silence_max": 23},
    {"file": "20.mp3", "silence_min": 22, "silence_max": 25},
    {"file": "21.mp3", "silence_min": 17, "silence_max": 22},
    {"file": "22.mp3", "silence_min": 19, "silence_max": 24},
    {"file": "23.mp3", "silence_min": 15, "silence_max": 20},
    {"file": "24.mp3", "silence_min": 16, "silence_max": 21},
    {"file": "25.mp3", "silence_min": 20, "silence_max": 25},
    {"file": "26.mp3", "silence_min": 18, "silence_max": 23},
    {"file": "27.mp3", "silence_min": 21, "silence_max": 25},
    {"file": "28.mp3", "silence_min": 17, "silence_max": 22},
    {"file": "29.mp3", "silence_min": 15, "silence_max": 20},
    {"file": "30.mp3", "silence_min": 19, "silence_max": 24},
]


def setup_logging():
    logger = logging.getLogger("conch")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=2)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                           datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    return logger


def load_track_index():
    try:
        with open(STATE_FILE, "r") as f:
            index = int(f.read().strip())
            if 0 <= index < len(TRACK_CONFIG):
                return index
    except (FileNotFoundError, ValueError):
        pass
    return 0


def save_track_index(index):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write(str(index))
    os.replace(tmp, STATE_FILE)


button_pressed = False


def on_button_press(channel):
    global button_pressed
    button_pressed = True


def setup_gpio():
    import RPi.GPIO as GPIO
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING,
                          callback=on_button_press, bouncetime=300)


def cleanup_gpio():
    try:
        import RPi.GPIO as GPIO
        GPIO.cleanup()
    except Exception:
        pass
