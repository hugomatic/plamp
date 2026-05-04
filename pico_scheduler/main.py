import time
import ujson as json
from machine import Pin, PWM

STATE_FILE = "state.json"
LOOP_SLEEP_MS = 20
PWM_FREQ = 1000

devices = []
report_every = 0
last_report_ms = 0
accum_ms = 0


def error(message):
    print(json.dumps({"kind": "error", "content": message}))
    return False


def report():
    out = []
    for ev in devices:
        item = {
            "type": ev["type"],
            "pin": ev["pin"],
            "elapsed_t": ev["elapsed_t"],
            "cycle_t": ev["elapsed_t"] % ev["total_t"] if ev["reschedule"] else ev["elapsed_t"],
            "reschedule": ev["reschedule"],
            "pattern": ev["pattern"],
        }
        item["current_value"] = ev["last_value"]
        if "id" in ev:
            item["id"] = ev["id"]
        out.append(item)
    print(json.dumps({"kind": "report", "content": {"devices": out}}))


def startup():
    print(json.dumps({"kind": "startup", "content": {"ok": True, "device_count": len(devices), "report_every": report_every}}))


def load_state():
    global devices, report_every

    try:
        with open(STATE_FILE, "r") as f:
            raw = json.load(f)
    except Exception as e:
        return error("failed to read state.json: %s" % e)

    if not isinstance(raw, dict):
        return error("top-level JSON must be an object")
    if "report_every" not in raw:
        return error("missing top-level field: report_every")
    if "devices" not in raw:
        return error("missing top-level field: devices")

    report_every_value = raw["report_every"]
    raw_devices = raw["devices"]

    try:
        report_every_value = int(report_every_value)
    except:
        return error("report_every must be an integer")

    if report_every_value <= 0:
        return error("report_every must be > 0")
    if not isinstance(raw_devices, list):
        return error("devices must be a list")

    new_devices = []

    for i, src in enumerate(raw_devices):
        if not isinstance(src, dict):
            return error("device %d must be an object" % i)

        required = ["type", "pin", "current_t", "reschedule", "pattern"]
        for name in required:
            if name not in src:
                return error("device %d missing field: %s" % (i, name))

        event_type = src["type"]
        if event_type != "gpio" and event_type != "pwm":
            return error("device %d type must be gpio or pwm" % i)

        try:
            pin = int(src["pin"])
            current_t = int(src["current_t"])
            reschedule = 1 if int(src["reschedule"]) else 0
        except:
            return error("device %d pin/current_t/reschedule must be integers" % i)

        if pin < 0 or pin > 29:
            return error("device %d pin must be in range 0..29" % i)
        if current_t < 0:
            return error("device %d current_t must be >= 0" % i)

        pattern_src = src["pattern"]
        if not isinstance(pattern_src, list) or not pattern_src:
            return error("device %d pattern must be a non-empty list" % i)

        pattern = []
        total_t = 0
        for j, step in enumerate(pattern_src):
            if not isinstance(step, dict):
                return error("device %d pattern step %d must be an object" % (i, j))
            if "val" not in step:
                return error("device %d pattern step %d missing field: val" % (i, j))
            if "dur" not in step:
                return error("device %d pattern step %d missing field: dur" % (i, j))

            try:
                val = int(step["val"])
                dur = int(step["dur"])
            except:
                return error("device %d pattern step %d val/dur must be integers" % (i, j))

            if dur <= 0:
                return error("device %d pattern step %d dur must be > 0" % (i, j))

            if event_type == "gpio":
                if val != 0 and val != 1:
                    return error("device %d pattern step %d gpio val must be 0 or 1" % (i, j))
            else:
                if val < 0:
                    val = 0
                elif val > 65535:
                    val = 65535

            pattern.append({"val": val, "dur": dur})
            total_t += dur

        if not reschedule and current_t > total_t:
            current_t = total_t

        if event_type == "gpio":
            output = Pin(pin, Pin.OUT)
        else:
            output = PWM(Pin(pin))
            output.freq(PWM_FREQ)

        ev = {
            "type": event_type,
            "pin": pin,
            "elapsed_t": current_t,
            "reschedule": reschedule,
            "pattern": pattern,
            "total_t": total_t,
            "output": output,
            "last_value": None,
        }
        if "id" in src:
            ev["id"] = src["id"]

        new_devices.append(ev)

    devices = new_devices
    report_every = report_every_value
    return True


def tick(dt):
    if dt <= 0:
        return

    for ev in devices:
        ev["elapsed_t"] += dt
        if not ev["reschedule"] and ev["elapsed_t"] > ev["total_t"]:
            ev["elapsed_t"] = ev["total_t"]


def apply():
    changed = False

    for ev in devices:
        t = ev["elapsed_t"] % ev["total_t"] if ev["reschedule"] else ev["elapsed_t"]
        elapsed = 0
        value = ev["pattern"][-1]["val"]

        for step in ev["pattern"]:
            elapsed += step["dur"]
            if t < elapsed:
                value = step["val"]
                break

        if ev["type"] == "gpio":
            ev["output"].value(value)
        else:
            ev["output"].duty_u16(value)

        if ev["last_value"] != value:
            ev["last_value"] = value
            changed = True

    return changed



def main():
    global last_report_ms, accum_ms

    if not load_state():
        return

    apply()
    startup()
    report()

    now_ms = time.ticks_ms()
    last_report_ms = now_ms
    last_tick_ms = now_ms
    accum_ms = 0

    while True:
        now_ms = time.ticks_ms()
        delta_ms = time.ticks_diff(now_ms, last_tick_ms)
        last_tick_ms = now_ms

        changed = False
        time_to_report = time.ticks_diff(now_ms, last_report_ms) >= report_every * 1000

        if delta_ms > 0:
            accum_ms += delta_ms
            dt = accum_ms // 1000
            if dt:
                accum_ms -= dt * 1000
                tick(dt)
                changed = apply()

        if changed or time_to_report:
            last_report_ms = now_ms
            report()

        time.sleep_ms(LOOP_SLEEP_MS)


if __name__ == "__main__":
    main()
