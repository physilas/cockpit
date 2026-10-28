"""Read-only AppleSMC temperature access, including CPU/GPU core hotspots.

Only key-info/read-bytes/read-index operations are used; no fan/power writes.
ABI references: AppleSMC interfaces used by exelban/stats (SMC/smc.swift).
"""
import ctypes as ct
import math
import struct

from .thermal import SensorUnavailable


class SmcTemperatures:
    def __init__(self):
        self.io = ct.CDLL('/System/Library/Frameworks/IOKit.framework/IOKit')
        system = ct.CDLL('/usr/lib/libSystem.B.dylib')

        def bind(name, args, result):
            fn = getattr(self.io, name)
            fn.argtypes, fn.restype = args, result
            return fn

        uint, pointer = ct.c_uint32, ct.c_void_p
        matching = bind('IOServiceMatching', [ct.c_char_p], pointer)
        service_get = bind('IOServiceGetMatchingService', [uint, pointer], uint)
        opening = bind('IOServiceOpen', [uint, uint, uint, ct.POINTER(uint)], ct.c_int)
        release = bind('IOObjectRelease', [uint], ct.c_int)
        self.closing = bind('IOServiceClose', [uint], ct.c_int)
        self.call = bind('IOConnectCallStructMethod', [uint, uint, pointer, ct.c_size_t,
                                                       pointer, ct.POINTER(ct.c_size_t)], ct.c_int)
        self.connection = uint()
        service = service_get(0, matching(b'AppleSMC'))
        if not service:
            raise SensorUnavailable('AppleSMC service is unavailable.')
        try:
            status = opening(service, uint.in_dll(system, 'mach_task_self_'), 0, ct.byref(self.connection))
        finally:
            release(service)
        if status:
            raise SensorUnavailable(f'AppleSMC connection failed: {status:#x}')
        self.layout = (80, 42, 44, 48)
        self.cache = {}
        # Apple Silicon systems may use the padded 84-byte layout.
        for layout in ((80, 42, 44, 48), (84, 44, 48, 52)):
            self.layout = layout
            if self._read('#KEY') is not None:
                break
        else:
            self.close()
            raise SensorUnavailable('No supported AppleSMC read ABI.')
        count = int(self._read('#KEY'))
        self.keys = []
        for index in range(min(count, 10000)):
            data = self._request(8, number=index)
            if data:
                key = int.from_bytes(data[:4], 'little').to_bytes(4, 'big').decode('ascii', 'replace')
                if key.startswith(('Tp', 'Te', 'Tg', 'TC', 'Ts')):
                    value = self._read(key)
                    if value is not None and 0 < value < 150:
                        self.keys.append(key)
        if not self.keys:
            self.close()
            raise SensorUnavailable('No live AppleSMC CPU/SoC temperature keys.')

    def close(self):
        if self.connection.value:
            self.closing(self.connection)
            self.connection.value = 0

    def _request(self, operation, key='', number=0, data_size=0):
        size, op_offset, number_offset, _ = self.layout
        source, target = ct.create_string_buffer(size), ct.create_string_buffer(size)
        if key:
            struct.pack_into('<I', source, 0, int.from_bytes(key.encode(), 'big'))
        struct.pack_into('<I', source, 28, data_size)
        source[op_offset] = bytes([operation])
        struct.pack_into('<I', source, number_offset, number)
        output_size = ct.c_size_t(size)
        status = self.call(self.connection, 2, source, size, target, ct.byref(output_size))
        result_offset = op_offset - 2
        if status or target.raw[result_offset]:
            return None
        return target.raw

    def _read(self, key):
        info = self.cache.get(key)
        if info is None:
            data = self._request(9, key)
            if data is None:
                return None
            length, kind = struct.unpack_from('<II', data, 28)
            if not 0 < length <= 32:
                return None
            info = length, kind.to_bytes(4, 'big').decode('ascii', 'replace')
            self.cache[key] = info
        data = self._request(5, key, data_size=info[0])
        if data is None:
            return None
        offset = self.layout[3]
        raw = data[offset:offset + info[0]]
        if info == (4, 'flt '):
            value = struct.unpack('<f', raw)[0]
        elif info == (2, 'sp78'):
            value = int.from_bytes(raw, 'big', signed=True) / 256.
        elif info[1].startswith('ui'):
            value = float(int.from_bytes(raw, 'big'))
        else:
            return None
        return value if math.isfinite(value) else None

    def read(self):
        result = {}
        for key in self.keys:
            value = self._read(key)
            if value is not None and 0 < value < 150:
                result[f'SMC {key}'] = value
        if not result:
            raise SensorUnavailable('AppleSMC temperature readings were lost.')
        return result


if __name__ == '__main__':
    import json
    sensor = SmcTemperatures()
    try:
        values = sensor.read()
        print(json.dumps(dict(max_celsius=max(values.values()), sensors=values), indent=2))
    finally:
        sensor.close()
