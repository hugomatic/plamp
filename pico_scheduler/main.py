import os
import time
import ujson as json
from machine import Pin, PWM

# Minimal cyclic scheduler for Raspberry Pi Pico.
#
# Timing:
# - time.ticks_ms() drives the loop
# - elapsed milliseconds are accumulated
# - state advances in whole seconds only for deterministic integer sec updates
#
# Reload logic:
# - state.json is not read every loop
# - os.stat() is checked about every 2 seconds
# - if the stat tuple changes, state.json is reloaded and validated
# - invalid JSON or bad content is ignored and the previous in-memory state is kept
#
# Event semantics:
# - each event owns its own current second: sec
# - every tick: sec = (sec + dt) % per
# - output: on if sec < dur, else off
# - sec is always normalized into the cycle
#
# Example state.json:
# {
#   "report_every": 60,
#   "events": [
#     {"type":"gpio","ch":2,"on":1,"off":0,"sec":890,"dur":900,"per":2700},
#     {"type":"pwm","ch":15,"on":40000,"off":0,"sec":120,"dur":30,"per":300}
#   ]
# }

STATE_FILE = "state.json"
RELOAD_CHECK_MS = 2000
LOOP_SLEEP_MS = 20
DEFAULT_REPORT_EVERY = 60
DEFAULT_PWM_FREQ = 1000

# The only event state object.
events = []

report_every = DEFAULT_REPORT_EVERY
last_state_stat = None
last_reload_check_ms = 0
last_report_ms = 0
accum_ms = 0

gpio_out = {}
pwm_out = {}


def _safe_int(value, default=0):
    try:
        return int(value)
    except:
        return default


def _normalize_event(src):
    if not isinstance(src, dict):
        return None

    typ = src.get("type")
    if typ != "gpio" and typ != "pwm":
        return None

    ch = _safe_int(src.get("ch"), -1)
    if ch < 0 or ch > 29:
        return None

    per = _safe_int(src.get("per"), 0)
    if per <= 0:
        return None

    dur = _safe_int(src.get("dur"), 0)
    if dur < 0:
        dur = 0

    sec = _safe_int(src.get("sec"), 0) % per
    on = _safe_int(src.get("on"), 0)
    off = _safe_int(src.get("off"), 0)

    ev = {
        "type": typ,
        "ch": ch,
        "on": on,
        "off": off,
        "sec": sec,
        "dur": dur,
        "per": per,
    }

    if "id" in src:
        ev["id"] = src["id"]

    return ev


def _safe_stat(path):
    try:
        st = os.stat(path)
        return tuple(st)
    except:
        return None


def _normalize_report_every(value):
    value = _safe_int(value, DEFAULT_REPORT_EVERY)
    if value <= 0:
        return DEFAULT_REPORT_EVERY
    return value


def load_state():
    global report_every, last_state_stat

    new_report_every = report_every
    new_events = []

    try:
        with open(STATE_FILE, "r") as f:
            raw = json.load(f)
    except OSError:
        raw = {"report_every": report_every, "events": []}
    except:
        return False

    if not isinstance(raw, dict):
        return False

    raw_report_every = raw.get("report_every", report_every)
    raw_events = raw.get("events", [])
    if not isinstance(raw_events, list):
        return False

    new_report_every = _normalize_report_every(raw_report_every)

    for item in raw_events:
        ev = _normalize_event(item)
        if ev is not None:
            new_events.append(ev)

    events[:] = new_events
    report_every = new_report_every
    last_state_stat = _safe_stat(STATE_FILE)
    return True


def maybe_reload(now_ms):
    global last_reload_check_ms

    if time.ticks_diff(now_ms, last_reload_check_ms) < RELOAD_CHECK_MS:
        return

    last_reload_check_ms = now_ms
    current_stat = _safe_stat(STATE_FILE)
    if current_stat != last_state_stat:
        if load_state():
            apply()


def tick(dt):
    if dt <= 0:
        return

    n = len(events)
    i = 0
    while i < n:
        ev = events[i]
        per = ev["per"]
        ev["sec"] = (ev["sec"] + dt) % per
        i += 1


def _gpio_pin(ch):
    pin = gpio_out.get(ch)
    if pin is None:
        pin = Pin(ch, Pin.OUT)
        gpio_out[ch] = pin
    return pin


def _pwm_pin(ch):
    pwm = pwm_out.get(ch)
    if pwm is None:
        pwm = PWM(Pin(ch))
        pwm.freq(DEFAULT_PWM_FREQ)
        pwm_out[ch] = pwm
    return pwm


def apply():
    n = len(events)
    i = 0
    while i < n:
        ev = events[i]
        try:
            value = ev["on"] if ev["sec"] < ev["dur"] else ev["off"]
            if ev["type"] == "gpio":
                _gpio_pin(ev["ch"]).value(1 if value else 0)
            else:
                pwm = _pwm_pin(ev["ch"])
                pwm.duty_u16(value)
        except:
            pass
        i += 1


def report():
    print(json.dumps({"events": events}))


def main():
    global report_every, last_state_stat, last_reload_check_ms, last_report_ms, accum_ms

    report_every = DEFAULT_REPORT_EVERY
    last_state_stat = _safe_stat(STATE_FILE)
    load_state()
    apply()

    now_ms = time.ticks_ms()
    last_reload_check_ms = now_ms
    last_report_ms = now_ms
    last_tick_ms = now_ms
    accum_ms = 0

    while True:
        now_ms = time.ticks_ms()
        delta_ms = time.ticks_diff(now_ms, last_tick_ms)
        last_tick_ms = now_ms

        if delta_ms > 0:
            accum_ms += delta_ms
            dt = accum_ms // 1000
            if dt:
                accum_ms -= dt * 1000
                tick(dt)
                apply()

        maybe_reload(now_ms)

        if time.ticks_diff(now_ms, last_report_ms) >= report_every * 1000:
            last_report_ms = now_ms
            report()

        time.sleep_ms(LOOP_SLEEP_MS)


main()
