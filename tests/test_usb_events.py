import unittest

from plamp.usb_events import UsbSerialEvent, start_usb_serial_observer, usb_serial_event


class FakeMonitor:
    def __init__(self):
        self.filters = []

    def filter_by(self, *, subsystem):
        self.filters.append(subsystem)


class FakeObserver:
    def __init__(self, monitor, *, callback, name):
        self.monitor = monitor
        self.callback = callback
        self.name = name
        self.started = False

    def start(self):
        self.started = True


class FakeDevice:
    def __init__(self, properties):
        self.properties = properties


class UsbEventsTests(unittest.TestCase):
    def test_normalizes_usb_tty_add_and_remove(self):
        properties = {"ID_SERIAL_SHORT": "PICO-A", "DEVNAME": "/dev/ttyACM0"}

        self.assertEqual(usb_serial_event("add", properties), UsbSerialEvent("add", "PICO-A", "/dev/ttyACM0"))
        self.assertEqual(usb_serial_event("remove", properties), UsbSerialEvent("remove", "PICO-A", "/dev/ttyACM0"))

    def test_ignores_irrelevant_or_unidentified_tty_events(self):
        self.assertIsNone(usb_serial_event("change", {"ID_SERIAL_SHORT": "PICO-A"}))
        self.assertIsNone(usb_serial_event("add", {"DEVNAME": "/dev/tty0"}))

    def test_observer_filters_tty_and_delivers_normalized_events(self):
        monitor = FakeMonitor()
        events = []

        observer = start_usb_serial_observer(
            events.append,
            context_factory=lambda: object(),
            monitor_factory=lambda context: monitor,
            observer_factory=FakeObserver,
        )
        observer.callback(
            "remove",
            FakeDevice({"ID_SERIAL_SHORT": "PICO-A", "DEVNAME": "/dev/ttyACM1"}),
        )
        observer.callback("change", FakeDevice({"ID_SERIAL_SHORT": "PICO-A"}))

        self.assertEqual(monitor.filters, ["tty"])
        self.assertEqual(observer.name, "plamp-usb-monitor")
        self.assertTrue(observer.started)
        self.assertEqual(events, [UsbSerialEvent("remove", "PICO-A", "/dev/ttyACM1")])


if __name__ == "__main__":
    unittest.main()
