"""
ESP32 MicroPython example - fast sampling with the RDY pin.

Instead of waiting a fixed time, the ADS1115 pulls RDY low the moment
each conversion is finished. The ESP32 catches that edge with an interrupt.

Extra wiring: breakout J1 pin 5 (RDY) -> ESP32 GPIO4.
(The board already has a 10 k pull-up on RDY.)

Samples CH0 at 860 samples/s for 2 seconds and prints the statistics.
Run with:  mpremote run ready_pin_fast.py
"""
import time
from machine import I2C, Pin

from ads1115 import ADS1115

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400_000)
adc = ADS1115(i2c, fsr=4.096, rate=860)
adc.enable_ready_pin()

ready = False


def on_ready(pin):
    global ready
    ready = True


rdy = Pin(4, Pin.IN, Pin.PULL_UP)
rdy.irq(trigger=Pin.IRQ_FALLING, handler=on_ready)

samples = []
deadline = time.ticks_add(time.ticks_ms(), 2000)
adc.start(0)
while time.ticks_diff(deadline, time.ticks_ms()) > 0:
    if ready:
        ready = False
        samples.append(adc.result_voltage())
        adc.start(0)

n = len(samples)
if n:
    mean = sum(samples) / n
    print("%d samples in 2 s (%.0f per s)" % (n, n / 2))
    print("mean %.4f V  min %.4f V  max %.4f V" % (mean, min(samples), max(samples)))
else:
    print("No ready pulses - check the RDY wire to GPIO4")
