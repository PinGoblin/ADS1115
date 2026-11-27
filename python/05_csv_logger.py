#!/usr/bin/env python3
"""Example 5: log all four channels to a CSV file.

Each row holds an ISO timestamp, then CH0–CH3 in volts (16-sample averages). Open the file
in a spreadsheet to chart it. Press Ctrl+C to stop.

**Usage**

```bash
python3 05_csv_logger.py                 # every 5 s to ads_log.csv
python3 05_csv_logger.py 60 garden.csv   # every 60 s to garden.csv
```
"""
import csv
import os
import sys
import time
from datetime import datetime

from pingoblin_ads1115 import ADS1115, load_calibration, apply_calibration

interval = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
path = sys.argv[2] if len(sys.argv) > 2 else "ads_log.csv"

adc = ADS1115(fsr=4.096, rate=128)
cal = load_calibration()

new_file = not os.path.exists(path)
with open(path, "a", newline="") as f:
    writer = csv.writer(f)
    if new_file:
        writer.writerow(["timestamp", "ch0_V", "ch1_V", "ch2_V", "ch3_V"])
    print(f"Logging every {interval:g} s to {path} - Ctrl+C to stop")
    try:
        while True:
            start = time.monotonic()
            row = [datetime.now().isoformat(timespec="seconds")]
            for ch in range(4):
                row.append(f"{apply_calibration(adc.read_voltage(ch, samples=16), ch, cal):.5f}")
            writer.writerow(row)
            f.flush()
            print(", ".join(row))
            time.sleep(max(0.0, interval - (time.monotonic() - start)))
    except KeyboardInterrupt:
        pass
