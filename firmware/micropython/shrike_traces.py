import time
import shrike
from machine import Pin, SPI


CMD_STATUS = 0x01
CMD_ARM = 0x02
CMD_CLEAR = 0x03
CMD_READ_LOW = 0x10
CMD_READ_HIGH = 0x20
CMD_TRIGGER_PTR = 0x30
CMD_DEVICE_ID = 0x7E
CMD_VERSION = 0x7F


class ShrikeTraces:
    def __init__(self, baudrate=1_000_000):
        self.reset_pin = Pin(14, Pin.OUT, value=1)
        self.cs = Pin(1, Pin.OUT, value=1)
        self.spi = SPI(
            0,
            baudrate=baudrate,
            polarity=0,
            phase=0,
            bits=8,
            sck=Pin(2),
            mosi=Pin(3),
            miso=Pin(0),
        )

    def reset(self):
        self.reset_pin.value(0)
        time.sleep_ms(100)
        self.reset_pin.value(1)
        time.sleep_ms(100)

    def flash(self, filename="SHRIKE_TRACES_V02.bin"):
        shrike.flash(filename)
        self.reset()

    def exchange(self, value):
        rx = bytearray(1)
        self.cs.value(0)
        self.spi.write_readinto(bytes((value & 0xFF,)), rx)
        self.cs.value(1)
        return rx[0]

    def request(self, command):
        self.exchange(command)
        time.sleep_us(20)
        return self.exchange(0x00)

    def identify(self):
        return self.request(CMD_DEVICE_ID), self.request(CMD_VERSION)

    def status(self):
        raw = self.request(CMD_STATUS)
        return {
            "raw": raw,
            "done": bool(raw & 0x01),
            "triggered": bool(raw & 0x02),
            "primed": bool(raw & 0x04),
            "capturing": bool(raw & 0x08),
            "protocol_major": raw >> 4,
        }

    def clear(self):
        return self.request(CMD_CLEAR)

    def arm(self):
        return self.request(CMD_ARM)

    def wait_done(self, timeout_ms=1000):
        start_ms = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_ms) < timeout_ms:
            current = self.status()
            if current["done"]:
                return current
            time.sleep_ms(1)
        raise RuntimeError("shrike-traces capture timeout")

    def read_sample(self, index):
        if not 0 <= index < 16:
            raise ValueError("sample index must be 0..15")
        low = self.request(CMD_READ_LOW | index)
        high = self.request(CMD_READ_HIGH | index)
        return low | (high << 8)

    def read_trace(self):
        return [self.read_sample(index) for index in range(16)]

    def trigger_pointer(self):
        return self.request(CMD_TRIGGER_PTR) & 0x0F


def decode_counter_sample(index, word):
    return {
        "index": index,
        "word": word,
        "count": word & 0xFF,
        "state": (word >> 8) & 0x03,
        "running": bool(word & (1 << 10)),
        "done": bool(word & (1 << 11)),
        "start": bool(word & (1 << 12)),
        "terminal": bool(word & (1 << 13)),
        "primed": bool(word & (1 << 14)),
        "triggered": bool(word & (1 << 15)),
    }


def decode_logic4_sample(index, word):
    a = word & 1
    b = (word >> 1) & 1
    c = (word >> 2) & 1
    d = (word >> 3) & 1
    ab = (word >> 4) & 1
    cd = (word >> 5) & 1
    y = (word >> 6) & 1
    return {
        "index": index,
        "word": word,
        "a": a,
        "b": b,
        "c": c,
        "d": d,
        "ab": ab,
        "cd": cd,
        "y": y,
        "stimulus": (word >> 7) & 0x0F,
        "primed": bool(word & (1 << 14)),
        "triggered": bool(word & (1 << 15)),
        "equation_ok": (ab == (a & b)) and
                       (cd == (c & d)) and
                       (y == ((a & b) | (c & d))),
    }


def capture(bitstream="SHRIKE_TRACES_V02.bin", flash=True, profile="counter"):
    scope = ShrikeTraces()
    if flash:
        scope.flash(bitstream)
    else:
        scope.reset()

    device_id, version = scope.identify()
    if device_id != 0x53 or version != 0x02:
        raise RuntimeError(
            "unexpected FPGA identity: id=0x%02x version=0x%02x"
            % (device_id, version)
        )

    if scope.clear() != 0xA3:
        raise RuntimeError("CLEAR command was not acknowledged")
    if scope.arm() != 0xA2:
        raise RuntimeError("ARM command was not acknowledged")

    final_status = scope.wait_done()
    trace = scope.read_trace()

    print("shrike-traces id=0x%02x version=%d status=0x%02x trigger_ptr=%d" % (
        device_id,
        version,
        final_status["raw"],
        scope.trigger_pointer(),
    ))
    if profile == "logic4":
        print("idx  word  a b c d  ab cd y  vector prim trig ok")
        for index, word in enumerate(trace):
            row = decode_logic4_sample(index, word)
            print("%3d  %04x  %d %d %d %d   %d  %d %d    %2d    %d    %d  %d" % (
                row["index"], row["word"], row["a"], row["b"],
                row["c"], row["d"], row["ab"], row["cd"], row["y"],
                row["stimulus"], row["primed"], row["triggered"],
                row["equation_ok"],
            ))
    elif profile == "counter":
        print("idx  word  count state run done start term prim trig")
        for index, word in enumerate(trace):
            row = decode_counter_sample(index, word)
            print("%3d  %04x  %5d %5d %3d %4d %5d %4d %4d %4d" % (
                row["index"], row["word"], row["count"], row["state"],
                row["running"], row["done"], row["start"],
                row["terminal"], row["primed"], row["triggered"],
            ))
    else:
        raise ValueError("profile must be 'counter' or 'logic4'")
    return trace
