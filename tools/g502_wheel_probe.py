#!/usr/bin/env python3
"""
g502_wheel_probe.py - PASSIVE diagnostic for the G502 X scroll wheel.

It ONLY READS events from /dev/input. The mouse keeps working normally while it
runs.

It logs every REL_WHEEL / REL_WHEEL_HI_RES event with its timestamp, groups
movements into gestures and at the end prints
a summary looking for the typical signature of each cause:

  - Encoder bounce (hardware): direction reversals in less than 25 ms.
  - hidpp driver issues: hi-res movement that never produces a REL_WHEEL, or
    a REL_WHEEL that doesn't match the accumulated hi-res movement.
  - Resolution mode: hi-res values of ±15 (multiplier 8) or ±120.

Usage:
    python3 -I g502_wheel_probe.py [seconds] [file.csv]
Ctrl+C stops early and still prints the summary.
"""
import sys
import time
from collections import Counter

try:
    import evdev
    from evdev import ecodes as e
except ImportError:
    sys.exit("python3-evdev is missing")

DEVICE_NAME = "G502"
GESTURE_GAP = 0.25      # this will count seconds of pauses that separates one gesture from the next
BOUNCE_WINDOW = 0.025   # if a direction reversal is faster, then is a bounce probably



def find_device():
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
        except PermissionError:
            continue
        rel = dev.capabilities().get(e.EV_REL, [])
        if DEVICE_NAME in dev.name and e.REL_WHEEL in rel:
            return dev
        dev.close()
    sys.exit("No G502 with a scroll wheel found (are you really in the 'input' group?)")


def sign(v):
    return (v > 0) - (v < 0)


def main():
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    csv_path = sys.argv[2] if len(sys.argv) > 2 else None
    dev = find_device()
    print(f"Reading {dev.path} ({dev.name}) for {duration:.0f}s. Ctrl+C to stop.\n")
    print(f"{'t(s)':>8} {'dt(ms)':>7} {'hires':>6} {'wheel':>5}  notes")

    rows = []            # (t, dt, hires, wheel, note)
    frame_hires = 0
    frame_wheel = 0
    t0 = None
    last_t = None
    last_dir = 0
    last_dir_t = None
    acc_hires = 0        # hires accumulated since the last REL_WHEEL
    stats = Counter()
    hires_values = Counter()
    gestures = []
    cur = None

    end = time.monotonic() + duration
    try:
        while time.monotonic() < end:
            ev = dev.read_one()
            if ev is None:
                time.sleep(0.001)
                continue
            if ev.type == e.EV_REL and ev.code == e.REL_WHEEL_HI_RES:
                frame_hires += ev.value
            elif ev.type == e.EV_REL and ev.code == e.REL_WHEEL:
                frame_wheel += ev.value
            elif ev.type == e.EV_SYN and ev.code == e.SYN_REPORT:
                if frame_hires == 0 and frame_wheel == 0:
                    continue
                t = ev.timestamp()
                if t0 is None:
                    t0 = t
                dt = (t - last_t) if last_t is not None else 0.0
                notes = []

                if cur is None or dt > GESTURE_GAP:
                    cur = {"start": t, "hires": 0, "wheel": 0, "frames": 0, "reversals": 0}
                    gestures.append(cur)
                    acc_hires = 0

                d = sign(frame_hires or frame_wheel)
                if last_dir and d and d != last_dir:
                    stats["reversals"] += 1
                    cur["reversals"] += 1
                    if last_dir_t is not None and (t - last_dir_t) < BOUNCE_WINDOW:
                        stats["fast_bounces"] += 1
                        notes.append(f"BOUNCE? reversed in {(t - last_dir_t)*1000:.1f}ms")
                    else:
                        notes.append("direction change")
                    acc_hires = 0
                if d:
                    last_dir = d
                    last_dir_t = t

                if frame_hires:
                    hires_values[frame_hires] += 1
                    acc_hires += frame_hires
                if frame_wheel:
                    if frame_hires and abs(acc_hires) < 120 * abs(frame_wheel) - 60:
                        stats["early_wheel"] += 1
                        notes.append(f"WHEEL with only {acc_hires} hi-res accumulated")
                    acc_hires -= 120 * frame_wheel
                elif abs(acc_hires) >= 180:
                    stats["missing_wheel"] += 1
                    notes.append(f"{acc_hires} hi-res accumulated without WHEEL")
                if frame_hires == 0 and frame_wheel:
                    stats["wheel_without_hires"] += 1

                if dt and dt < 0.002 and frame_wheel:
                    stats["wheel_within_2ms"] += 1
                    notes.append("WHEEL very close to the previous one")

                cur["hires"] += frame_hires
                cur["wheel"] += frame_wheel
                cur["frames"] += 1
                stats["frames"] += 1

                note = "; ".join(notes)
                rows.append((t - t0, dt * 1000, frame_hires, frame_wheel, note))
                print(f"{t - t0:8.3f} {dt*1000:7.1f} {frame_hires:6d} {frame_wheel:5d}  {note}")
                last_t = t
                frame_hires = frame_wheel = 0
    except KeyboardInterrupt:
        pass
    finally:
        dev.close()

    print("\n================ SUMMARY ================")
    print(f"Wheel frames: {stats['frames']}")
    print(f"Hi-res values seen: {dict(hires_values.most_common(8))}")
    if hires_values:
        common = abs(hires_values.most_common(1)[0][0])
        mode = {15: "hi-res x8", 120: "low resolution (1 event per notch)"}.get(common, "unknown")
        print(f"  -> apparent mode: {mode}")
    for k in ("reversals", "fast_bounces", "missing_wheel", "early_wheel",
              "wheel_without_hires", "wheel_within_2ms"):
        print(f"{k:>22}: {stats[k]}")
    print(f"\nGestures ({len(gestures)}): hires_total / wheel_total / reversals")
    for i, g in enumerate(gestures, 1):
        print(f"  #{i:<3} {g['hires']:6d} / {g['wheel']:4d} / {g['reversals']}")

    if csv_path:
        with open(csv_path, "w") as f:
            f.write("t_s,dt_ms,hires,wheel,note\n")
            for r in rows:
                f.write(f"{r[0]:.4f},{r[1]:.2f},{r[2]},{r[3]},\"{r[4]}\"\n")
        print(f"\nLog saved to {csv_path}")


if __name__ == "__main__":
    main()
