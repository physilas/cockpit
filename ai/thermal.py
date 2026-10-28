"""Read Apple Silicon HID temperatures without sudo or third party packages.

Private read-only IOKit API; unavailable sensors raise rather than report 0 C.
The macOS sandbox may hide sensors: run the managed job outside it if needed.
"""
import ctypes as ct
import json
import math
import plistlib
import sys


class SensorUnavailable(RuntimeError):
    pass


class MacTemperatures:
    def __init__(self):
        if sys.platform != 'darwin':
            raise SensorUnavailable('Apple HID temperature sensors require macOS.')
        self.cf = ct.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        self.io = ct.CDLL('/System/Library/Frameworks/IOKit.framework/IOKit')
        pointer, integer = ct.c_void_p, ct.c_long

        def bind(lib, name, args, result):
            fn = getattr(lib, name)
            fn.argtypes, fn.restype = args, result
            return fn

        self.release = bind(self.cf, 'CFRelease', [pointer], None)
        data_create = bind(self.cf, 'CFDataCreate', [pointer, pointer, integer], pointer)
        parse = bind(self.cf, 'CFPropertyListCreateWithData', [pointer, pointer, integer, pointer, pointer], pointer)
        create = bind(self.io, 'IOHIDEventSystemClientCreate', [pointer], pointer)
        matching = bind(self.io, 'IOHIDEventSystemClientSetMatching', [pointer, pointer], None)
        self.services = bind(self.io, 'IOHIDEventSystemClientCopyServices', [pointer], pointer)
        self.count = bind(self.cf, 'CFArrayGetCount', [pointer], integer)
        self.item = bind(self.cf, 'CFArrayGetValueAtIndex', [pointer, integer], pointer)
        string = bind(self.cf, 'CFStringCreateWithCString', [pointer, ct.c_char_p, ct.c_uint], pointer)
        self.property = bind(self.io, 'IOHIDServiceClientCopyProperty', [pointer, pointer], pointer)
        self.to_string = bind(self.cf, 'CFStringGetCString', [pointer, pointer, integer, ct.c_uint], ct.c_bool)
        self.event = bind(self.io, 'IOHIDServiceClientCopyEvent', [pointer, integer, integer, integer], pointer)
        self.value = bind(self.io, 'IOHIDEventGetFloatValue', [pointer, ct.c_uint], ct.c_double)
        self.client = create(None)
        self.key = string(None, b'Product', 0x08000100)
        raw = plistlib.dumps({'PrimaryUsagePage': 0xff00, 'PrimaryUsage': 5})
        data = data_create(None, ct.create_string_buffer(raw), len(raw))
        match = parse(None, data, 0, None, None)
        try:
            if not self.client or not self.key or not match:
                raise SensorUnavailable('Cannot create the temperature sensor client.')
            matching(self.client, match)
        finally:
            if match:
                self.release(match)
            self.release(data)

    def close(self):
        for name in ('key', 'client'):
            obj = getattr(self, name, None)
            if obj:
                self.release(obj)
                setattr(self, name, None)

    def read(self):
        if not self.client:
            raise SensorUnavailable('Temperature sensor client is closed.')
        services = self.services(self.client)
        readings = {}
        try:
            for index in range(self.count(services) if services else 0):
                service = self.item(services, index)
                name = self.property(service, self.key)
                event = self.event(service, 15, 0, 0)
                try:
                    buffer = ct.create_string_buffer(256)
                    if name and event and self.to_string(name, buffer, len(buffer), 0x08000100):
                        temperature = self.value(event, 15 << 16)
                        if math.isfinite(temperature) and 0 < temperature < 150:
                            readings[buffer.value.decode('utf-8')] = temperature
                finally:
                    if name:
                        self.release(name)
                    if event:
                        self.release(event)
        finally:
            if services:
                self.release(services)
        if not readings:
            raise SensorUnavailable('No temperature readings; the sandbox may hide HID sensors.')
        return readings


class ThermalGate:
    """Hysteresis with headroom: pause at 72 C, resume at 67 C for a 75 C limit.

    This regulates only the owned job. Other apps and sensor sampling latency
    mean that it cannot guarantee an absolute system-wide temperature ceiling.
    """
    def __init__(self, limit=75., headroom=3., hysteresis=5.):
        if any(not math.isfinite(v) or v <= 0 for v in (limit, headroom, hysteresis)) or limit <= headroom + hysteresis:
            raise ValueError('Use a finite positive limit, headroom and hysteresis.')
        self.pause_at = limit - headroom
        self.resume_at = self.pause_at - hysteresis
        self.paused = False

    def update(self, readings):
        if not readings or any(not math.isfinite(v) or not 0 < v < 150 for v in readings.values()):
            raise SensorUnavailable('Missing or invalid temperature readings.')
        maximum = max(readings.values())
        self.paused = maximum > self.resume_at if self.paused else maximum >= self.pause_at
        return self.paused


class ComputerTemperatures:
    """Prefer actual CPU/GPU SMC hotspots; supplement with HID sensors."""
    def __init__(self):
        from .smc_temperature import SmcTemperatures
        self.sources = []
        errors = []
        for factory in (SmcTemperatures, MacTemperatures):
            sensor = None
            try:
                sensor = factory()
                sensor.read()
                self.sources.append(sensor)
            except (SensorUnavailable, OSError, AttributeError) as exc:
                if sensor:
                    sensor.close()
                errors.append(str(exc))
        if not self.sources:
            raise SensorUnavailable('; '.join(errors))

    def read(self):
        readings = {}
        for sensor in self.sources:
            readings.update(sensor.read())
        return readings

    def close(self):
        for sensor in self.sources:
            sensor.close()


def main():
    sensor = ComputerTemperatures()
    try:
        readings = sensor.read()
        print(json.dumps({'max_celsius': max(readings.values()), 'sensors': readings}, indent=2))
    finally:
        sensor.close()


if __name__ == '__main__':
    main()
