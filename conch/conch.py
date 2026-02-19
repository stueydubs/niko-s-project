#!/usr/bin/env python3
"""Conch Shell Phone — a time-based audio art installation."""
# Wiring: Momentary NO switch between GPIO 17 (physical pin 11) and GND (physical pin 9).
# No external resistor needed — internal pull-up is enabled in software.

import os
import sys
import time
import shutil
import select
import signal
import random
import logging
import threading
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
    tmp = STATE_FILE + ".tmp"
    if os.path.exists(tmp):
        try:
            os.remove(tmp)
        except OSError:
            pass
    try:
        with open(STATE_FILE, "r") as f:
            index = int(f.read().strip())
            if 0 <= index < len(TRACK_CONFIG):
                return index
    except (FileNotFoundError, ValueError, OSError):
        pass
    return 0


def save_track_index(index):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write(str(index))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE_FILE)


def validate_audio_files(log):
    if shutil.which("cvlc") is None:
        log.error("cvlc not found — install VLC (sudo apt install vlc-nox)")
        sys.exit(1)
    ring_file = os.path.join(AUDIO_DIR, "ring.mp3")
    if not os.path.isfile(ring_file):
        log.error("MISSING: %s", ring_file)
        sys.exit(1)
    for entry in TRACK_CONFIG:
        track_file = os.path.join(AUDIO_DIR, entry["file"])
        if not os.path.isfile(track_file):
            log.warning("MISSING: %s (will be skipped if reached)", track_file)


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


def _keyboard_thread():
    global button_pressed
    while True:
        try:
            line = input()
            if line.strip() == "" or " " in line or line.strip().lower() == "space":
                button_pressed = True
        except EOFError:
            break


def setup_keyboard():
    if sys.stdin.isatty():
        # Real terminal: use raw mode for instant spacebar detection
        try:
            import tty, termios
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            return old_settings
        except Exception:
            pass
    # Fallback (Thonny, etc): use background thread reading input()
    t = threading.Thread(target=_keyboard_thread, daemon=True)
    t.start()
    return "thread"


def check_keyboard():
    global button_pressed
    if not sys.stdin.isatty():
        return
    ready, _, _ = select.select([sys.stdin], [], [], 0)
    if ready:
        ch = sys.stdin.read(1)
        if ch == " ":
            button_pressed = True
        elif ch == "\x03":  # Ctrl+C
            raise KeyboardInterrupt


def cleanup_keyboard(old_settings):
    if old_settings is not None and old_settings != "thread":
        import termios
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def start_ring(log):
    ring_file = os.path.join(AUDIO_DIR, "ring.mp3")
    log.info("Starting ring loop")
    return subprocess.Popen(
        ["cvlc", "--input-repeat=-1", ring_file],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def stop_ring(proc, log):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.info("Ring stopped")


def start_track(track_index, log):
    track_file = os.path.join(AUDIO_DIR, TRACK_CONFIG[track_index]["file"])
    log.info("Playing track %s", TRACK_CONFIG[track_index]["file"])
    return subprocess.Popen(
        ["cvlc", "--play-and-exit", track_file],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def main():
    global button_pressed

    log = setup_logging()
    log.info("Conch starting up")

    def handle_sigterm(signum, frame):
        log.info("Received SIGTERM, shutting down")
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        setup_gpio()
    except Exception:
        log.warning("GPIO not available, using keyboard input only")

    old_term = setup_keyboard()
    if old_term == "thread":
        log.info("Keyboard input enabled (press Enter to simulate button)")
    elif old_term is not None:
        log.info("Keyboard input enabled (spacebar = button press)")

    atexit.register(cleanup_gpio)

    validate_audio_files(log)

    track_index = load_track_index()
    log.info("Loaded track index: %d (%s)", track_index, TRACK_CONFIG[track_index]["file"])

    state = "silent"
    silence_end = 0
    ring_proc = None
    track_proc = None

    # Enter initial silence
    config = TRACK_CONFIG[track_index]
    silence_sec = random.uniform(config["silence_min"], config["silence_max"]) * 60
    silence_end = time.time() + silence_sec
    log.info("Entering SILENT state (%.1f minutes)", silence_sec / 60)

    try:
        while True:
            if state == "silent":
                button_pressed = False  # ignore presses during silence
                if time.time() >= silence_end:
                    state = "ringing"
                    ring_proc = start_ring(log)
                    log.info("Entering RINGING state, next track: %s",
                             TRACK_CONFIG[track_index]["file"])

            elif state == "ringing":
                if ring_proc and ring_proc.poll() is not None:
                    log.warning("Ring process died unexpectedly, restarting ring")
                    ring_proc = start_ring(log)
                if button_pressed:
                    button_pressed = False
                    log.info("Button pressed during RINGING")
                    stop_ring(ring_proc, log)
                    ring_proc = None
                    state = "playing"
                    track_proc = start_track(track_index, log)
                    log.info("Entering PLAYING state")

            elif state == "playing":
                button_pressed = False  # ignore presses during playback
                exit_code = track_proc.poll() if track_proc else None
                if exit_code is not None:
                    if exit_code != 0:
                        log.warning("Track %s exited with code %d (playback may have failed)",
                                    TRACK_CONFIG[track_index]["file"], exit_code)
                    else:
                        log.info("Track %s finished", TRACK_CONFIG[track_index]["file"])
                    track_proc = None
                    track_index = (track_index + 1) % len(TRACK_CONFIG)
                    try:
                        save_track_index(track_index)
                    except OSError:
                        log.error("Failed to save track index %d", track_index)
                    log.info("Advanced to track index %d (%s)",
                             track_index, TRACK_CONFIG[track_index]["file"])
                    config = TRACK_CONFIG[track_index]
                    silence_sec = random.uniform(config["silence_min"],
                                                 config["silence_max"]) * 60
                    silence_end = time.time() + silence_sec
                    state = "silent"
                    log.info("Entering SILENT state (%.1f minutes)", silence_sec / 60)

            check_keyboard()
            time.sleep(POLL_INTERVAL)
    finally:
        stop_ring(ring_proc, log)
        if track_proc and track_proc.poll() is None:
            track_proc.terminate()
            try:
                track_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                track_proc.kill()
        cleanup_keyboard(old_term)
        cleanup_gpio()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger("conch").info("Shutdown requested")
    except Exception as e:
        logging.getLogger("conch").exception("Fatal error: %s", e)
        sys.exit(1)
