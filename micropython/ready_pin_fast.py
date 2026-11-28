"""ESP32 MicroPython example: fast sampling with the RDY pin.

Instead of waiting a fixed time, the ADS1115 pulls RDY low the moment each conversion
finishes, and the ESP32 catches that edge with an interrupt. Samples CH0 at the 860 samples/s
data rate for 2 seconds and prints the statistics. Reading each result over I²C adds time, so
the achieved rate is lower at 100 kHz: Add 2.2–4.7 kΩ pull-ups from SDA and SCL to 3.3 V and
set `freq=400_000` to get closer to 860.

**Extra wiring (Required):** PinGoblin ADS1115 J1 pin 5 (RDY) to ESP32 GPIO4. The board
already has a 10 kΩ pull-up on RDY.

Run with `mpremote run ready_pin_fast.py`, or `micropython ready_pin_fast.py --mock` on a
computer with the MicroPython Unix port to try it without hardware.
"""
import sys
import time

from ads1115 import ADS1115, BusError, InputRangeError, MockI2C

MOCK = "--mock" in sys.argv
if MOCK:
    i2c = MockI2C()   # a simulated board, no hardware
else:
    from machine import I2C, Pin
    i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100_000)
adc = ADS1115(i2c, fsr=4.096, rate=860)

ready = False


def on_ready(pin):
    """Interrupt handler: flag that a conversion has finished."""
    global ready
    ready = True


def start():
    """Start the next conversion. A simulated board has no RDY wire, so it reports at once."""
    adc.start(0)
    if MOCK:
        on_ready(None)


try:
    adc.enable_ready_pin()
    if not MOCK:
        rdy = Pin(4, Pin.IN, Pin.PULL_UP)
        rdy.irq(trigger=Pin.IRQ_FALLING, handler=on_ready)

    samples = []
    over = 0
    deadline = time.ticks_add(time.ticks_ms(), 2000)
    start()
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if ready:
            ready = False
            try:
                samples.append(adc.result_voltage())
            except InputRangeError:
                over += 1
            start()
except BusError as exc:
    raise SystemExit(exc)

if over:
    print("%d readings beyond the ±4.096 V range: Use a larger fsr" % over)
n = len(samples)
if n:
    mean = sum(samples) / n
    print("%d samples in 2 s (%.0f per s)" % (n, n / 2))
    print("mean %.4f V  min %.4f V  max %.4f V" % (mean, min(samples), max(samples)))
elif not over:
    print("No ready pulses: Check the RDY wire from J1 pin 5 to GPIO4")
