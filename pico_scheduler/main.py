import time
import ujson as json
from machine import Pin, PWM

STATE_FILE = "state.json"
LOOP_SLEEP_MS = 20
PWM_FREQ = 1000

events = []
report_every = 0
last_report_ms = 0
accum_ms = 0


def load_state():
    global events, report_every

    try:
        with open(STATE_FILE, "r") as f:
            raw = json.load(f)
    except Exception as e:
        print("load_state: failed to read state.json:", e)
        return False

    if not isinstance(raw, dict):
        print("load_state: top-level JSON must be an object")
        return False
    if "report_every" not in raw:
        print("load_state: missing top-level field: report_every")
        return False
    if "events" not in raw:
        print("load_state: missing top-level field: events")
        return False

    report_every_value = raw["report_every"]
    raw_events = raw["events"]

    try:
        report_every_value = int(report_every_value)
    except:
        print("load_state: report_every must be an integer")
        return False

    if report_every_value <= 0:
        print("load_state: report_every must be > 0")
        return False
    if not isinstance(raw_events, list):
        print("load_state: events must be a list")
        return False

    new_events = []

    i = 0
    n = len(raw_events)
    while i < n:
        src = raw_events[i]
        if not isinstance(src, dict):
            print("load_state: event", i, "must be an object")
            return False

        required = ["type", "ch", "current_t", "reschedule", "pattern"]
        j = 0
        while j < len(required):
            if required[j] not in src:
                print("load_state: event", i, "missing field:", required[j])
                return False
            j += 1

        event_type = src["type"]
        if event_type != "gpio" and event_type != "pwm":
            print("load_state: event", i, "type must be gpio or pwm")
            return False

        try:
            ch = int(src["ch"])
            current_t = int(src["current_t"])
            reschedule = 1 if int(src["reschedule"]) else 0
        except:
            print("load_state: event", i, "ch/current_t/reschedule must be integers")
            return False

        if ch < 0 or ch > 29:
            print("load_state: event", i, "ch must be in range 0..29")
            return False
        if current_t < 0:
            print("load_state: event", i, "current_t must be >= 0")
            return False

        pattern_src = src["pattern"]
        if not isinstance(pattern_src, list) or not pattern_src:
            print("load_state: event", i, "pattern must be a non-empty list")
            return False

        pattern = []
        total_t = 0
        j = 0
        m = len(pattern_src)
        while j < m:
            step = pattern_src[j]
            if not isinstance(step, dict):
                print("load_state: event", i, "pattern step", j, "must be an object")
                return False
            if "val" not in step:
                print("load_state: event", i, "pattern step", j, "missing field: val")
                return False
            if "dur" not in step:
                print("load_state: event", i, "pattern step", j, "missing field: dur")
                return False

            try:
                val = int(step["val"])
                dur = int(step["dur"])
            except:
                print("load_state: event", i, "pattern step", j, "val/dur must be integers")
                return False

            if dur <= 0:
                print("load_state: event", i, "pattern step", j, "dur must be > 0")
                return False

            if event_type == "gpio":
                if val != 0 and val != 1:
                    print("load_state: event", i, "pattern step", j, "gpio val must be 0 or 1")
                    return False
            else:
                if val < 0:
                    val = 0
                elif val > 65535:
                    val = 65535

            pattern.append({"val": val, "dur": dur})
            total_t += dur
            j += 1

        if reschedule:
            current_t = current_t % total_t
        elif current_t > total_t:
            current_t = total_t

        if event_type == "gpio":
            output = Pin(ch, Pin.OUT)
        else:
            output = PWM(Pin(ch))
            output.freq(PWM_FREQ)

        ev = {
            "type": event_type,
            "ch": ch,
            "current_t": current_t,
            "reschedule": reschedule,
            "pattern": pattern,
            "total_t": total_t,
            "output": output,
        }
        if "id" in src:
            ev["id"] = src["id"]

        new_events.append(ev)
        j += 1
        i += 1

    events = new_events
    report_every = report_every_value
    return True


def tick(dt):
    if dt <= 0:
        return

    i = 0
    n = len(events)
    while i < n:
        ev = events[i]
        if ev["reschedule"]:
            ev["current_t"] = (ev["current_t"] + dt) % ev["total_t"]
        else:
            ev["current_t"] += dt
            if ev["current_t"] > ev["total_t"]:
                ev["current_t"] = ev["total_t"]
        i += 1


def apply():
    i = 0
    n = len(events)
    while i < n:
        ev = events[i]
        t = ev["current_t"]
        elapsed = 0
        value = ev["pattern"][-1]["val"]

        j = 0
        m = len(ev["pattern"])
        while j < m:
            step = ev["pattern"][j]
            elapsed += step["dur"]
            if t < elapsed:
                value = step["val"]
                break
            j += 1

        if ev["type"] == "gpio":
            ev["output"].value(value)
        else:
            ev["output"].duty_u16(value)
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
    global last_report_ms, accum_ms

    if not load_state():
        return

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
