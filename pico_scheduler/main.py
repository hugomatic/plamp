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
# Load logic:
# - state.json is read once at boot
# - schedule changes are applied by copying a new state.json and resetting the board
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
LOOP_SLEEP_MS = 20

# The only runtime state object.
events = []

report_every = 0
last_report_ms = 0
accum_ms = 0


def _safe_int(value):
    try:
        return int(value)
    except:
        return None


def _safe_bool_int(value):
    try:
        return 1 if int(value) else 0
    except:
        return None


def _normalize_report_every(value):
    value = _safe_int(value)
    if value is None or value <= 0:
        return None
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

        if "dur" not in step or "val" not in step:
            i += 1
            continue

        dur = _safe_int(step.get("dur"))
        if dur is None or dur <= 0:
            i += 1
            continue

        val = _safe_int(step.get("val"))
        if val is None:
            i += 1
            continue

        if event_type == "gpio":
            if val != 0 and val != 1:
                i += 1
                continue
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

    required = ["type", "ch", "current_t", "reschedule", "pattern"]
    i = 0
    while i < len(required):
        if required[i] not in src:
            return None
        i += 1

    ch = _safe_int(src.get("ch"))
    if ch is None or ch < 0 or ch > 29:
        return None

    pattern_info = _normalize_pattern(src.get("pattern", []), event_type)
    if pattern_info is None:
        return None
    pattern, total_t = pattern_info

    reschedule = _safe_bool_int(src.get("reschedule"))
    current_t = _safe_int(src.get("current_t"))
    if reschedule is None or current_t is None or current_t < 0:
        current_t = 0

    if reschedule:
        current_t = current_t % total_t
    elif current_t > total_t:
        current_t = total_t

    if event_type == "gpio":
        output = Pin(ch, Pin.OUT)
    else:
        output = PWM(Pin(ch))
        output.freq(1000)

    ev = {
        "type": event_type,
        "ch": ch,
        "current_t": current_t,
        "reschedule": reschedule,
        "pattern": pattern,
        "output": output,
    }

    if "id" in src:
        ev["id"] = src["id"]

    return ev


def load_state():
    global report_every

    new_events = []

    try:
        with open(STATE_FILE, "r") as f:
            raw = json.load(f)
    except:
        return False

    if not isinstance(raw, dict):
        return False
    if "report_every" not in raw or "events" not in raw:
        return False

    raw_report_every = raw.get("report_every")
    raw_events = raw.get("events")
    if not isinstance(raw_events, list):
        return False

    new_report_every = _normalize_report_every(raw_report_every)
    if new_report_every is None:
        return False

    i = 0
    n = len(raw_events)
    while i < n:
        ev = _normalize_event(raw_events[i])
        if ev is None:
            return False
        new_events.append(ev)
        i += 1

    events[:] = new_events
    report_every = new_report_every
    return True


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
                ev["output"].value(1 if value else 0)
            else:
                ev["output"].duty_u16(value)
        except:
            pass
        i += 1


def report():
    out = []
    i = 0
    n = len(events)
    while i < n:
        ev = events[i]
        item = {
            "type": ev["type"],
            "ch": ev["ch"],
            "current_t": ev["current_t"],
            "reschedule": ev["reschedule"],
            "pattern": ev["pattern"],
        }
        if "id" in ev:
            item["id"] = ev["id"]
        out.append(item)
        i += 1
    print(json.dumps({"events": out}))


def main():
    global report_every, last_report_ms, accum_ms

    report_every = 0
    load_state()
    apply()

    now_ms = time.ticks_ms()
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

        if time.ticks_diff(now_ms, last_report_ms) >= report_every * 1000:
            last_report_ms = now_ms
            report()

        time.sleep_ms(LOOP_SLEEP_MS)


main()
