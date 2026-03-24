import os
import time
import ujson as json
from machine import Pin, PWM

# Minimal pattern scheduler for Raspberry Pi Pico.
#
# Timing:
# - time.ticks_ms() drives the loop
# - elapsed milliseconds are accumulated
# - state advances in whole seconds only for deterministic integer current_t updates
#
# Reload logic:
# - state.json is not read every loop
# - os.stat() is checked about every 2 seconds
# - if the stat tuple changes, state.json is reloaded and validated
# - invalid JSON or bad content is ignored and the previous in-memory state is kept
#
# Event semantics:
# - each event has a pattern: [{"val": X, "dur": N}, ...]
# - current_t is the current second inside that pattern
# - if reschedule is truthy: current_t wraps at total duration
# - otherwise current_t advances until the end and then the last value is held
#
# Example state.json:
# {
#   "report_every": 10,
#   "events": [
#     {
#       "type": "gpio",
#       "ch": 25,
#       "current_t": 3,
#       "reschedule": 1,
#       "pattern": [
#         {"val": 1, "dur": 10},
#         {"val": 0, "dur": 20}
#       ]
#     }
#   ]
# }

STATE_FILE = "state.json"
RELOAD_CHECK_MS = 2000
LOOP_SLEEP_MS = 20
DEFAULT_REPORT_EVERY = 60
DEFAULT_PWM_FREQ = 1000

# The only runtime state object.
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


def _safe_bool_int(value):
    try:
        return 1 if int(value) else 0
    except:
        return 0


def _safe_stat(path):
    try:
        return tuple(os.stat(path))
    except:
        return None


def _normalize_report_every(value):
    value = _safe_int(value, DEFAULT_REPORT_EVERY)
    if value <= 0:
        return DEFAULT_REPORT_EVERY
    return value


def _normalize_pattern(pattern_src, event_type):
    if not isinstance(pattern_src, list):
        return None

    pattern = []
    total_t = 0
    i = 0
    n = len(pattern_src)
    while i < n:
        step = pattern_src[i]
        if not isinstance(step, dict):
            i += 1
            continue

        dur = _safe_int(step.get("dur"), 0)
        if dur <= 0:
            i += 1
            continue

        val = _safe_int(step.get("val"), 0)
        if event_type == "gpio":
            val = 1 if val else 0
        else:
            if val < 0:
                val = 0
            elif val > 65535:
                val = 65535

        pattern.append({"val": val, "dur": dur})
        total_t += dur
        i += 1

    if total_t <= 0:
        return None

    return pattern, total_t


def _normalize_event(src):
    if not isinstance(src, dict):
        return None

    event_type = src.get("type")
    if event_type != "gpio" and event_type != "pwm":
        return None

    ch = _safe_int(src.get("ch"), -1)
    if ch < 0 or ch > 29:
        return None

    pattern_info = _normalize_pattern(src.get("pattern", []), event_type)
    if pattern_info is None:
        return None
    pattern, total_t = pattern_info

    reschedule = _safe_bool_int(src.get("reschedule", 1))
    current_t = _safe_int(src.get("current_t"), 0)
    if current_t < 0:
        current_t = 0

    if reschedule:
        current_t = current_t % total_t
    elif current_t > total_t:
        current_t = total_t

    ev = {
        "type": event_type,
        "ch": ch,
        "current_t": current_t,
        "reschedule": reschedule,
        "pattern": pattern,
    }

    if "id" in src:
        ev["id"] = src["id"]

    return ev


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

    i = 0
    n = len(raw_events)
    while i < n:
        ev = _normalize_event(raw_events[i])
        if ev is not None:
            new_events.append(ev)
        i += 1

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

    i = 0
    n = len(events)
    while i < n:
        ev = events[i]
        total_t = 0
        j = 0
        pattern = ev["pattern"]
        m = len(pattern)
        while j < m:
            total_t += pattern[j]["dur"]
            j += 1

        if ev["reschedule"]:
            ev["current_t"] = (ev["current_t"] + dt) % total_t
        else:
            ev["current_t"] += dt
            if ev["current_t"] > total_t:
                ev["current_t"] = total_t
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


def _current_value(ev):
    t = ev["current_t"]
    elapsed = 0
    pattern = ev["pattern"]
    i = 0
    n = len(pattern)
    while i < n:
        step = pattern[i]
        elapsed += step["dur"]
        if t < elapsed:
            return step["val"]
        i += 1
    return pattern[-1]["val"]


def apply():
    i = 0
    n = len(events)
    while i < n:
        ev = events[i]
        try:
            value = _current_value(ev)
            if ev["type"] == "gpio":
                _gpio_pin(ev["ch"]).value(1 if value else 0)
            else:
                _pwm_pin(ev["ch"]).duty_u16(value)
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
