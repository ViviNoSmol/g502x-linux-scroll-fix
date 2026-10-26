# Logitech G502 X scroll wheel fix for Linux

A libinput quirk that stops the **Logitech G502 X PLUS** scroll wheel from
jittering, "sticking" or scrolling back (whatever you call it tbh) on Linux. After the fix, the wheel
behaves like it does more on Windows.

## The problem

On Linux, the `hid-logitech-hidpp` kernel driver switches the G502 X into
high-resolution scroll mode. In this mode the mouse reports every notch as
8 small steps (8 × 15 = 120 units) instead of one.

The wheel has a little physical play inside each notch, and it bounces slightly
when it settles into a notch. In high-resolution mode, those tiny movements are
reported too. Any app and DE on linux will read it, in theory sounds good, but in reality just causes issues like...

- small scrolls when you barely touch the wheel
- the page jumping back a little right after you scroll,
- scrolling that feels like it "sticks" or repeats.

And after LOTS of testing (and literally getting another g502x) is NOT a Hardware issue, specially because on Windows doesn't happen, both without and with G Hub. 

## The fix!

The quirk tells libinput to ignore `REL_WHEEL_HI_RES` / `REL_HWHEEL_HI_RES`
FOR THIS MOUSE ONLY!!. So it uses the regular `REL_WHEEL` event, one event
per notch.

The kernel only counts a notch when the wheel has moved more than half of it,
and resets that count when the direction changes. That filters out the play
and the rebounds.

What it does **NOT** touch: the kernel driver, battery reporting, buttons, DPI,
Solaar/Piper, or any other device.

The trade off? you lose pixel smooth scrolling for this mouse. Every notch is a
full scroll step like on Windows, and believe me when I say this, YOU AREN'T MISSING ON MUCH.
This is 100% better than literally disabling the whole Logitech hid module and basically destroying almost every function your mouse can have.

## Installation

```bash
git clone https://github.com/ViviNoSmol/g502x-linux-scroll-fix.git && cd g502x-linux-scroll-fix
sudo mkdir -p /etc/libinput
sudo cp local-overrides.quirks /etc/libinput/local-overrides.quirks
```

Then log out and back in (or reboot) so libinput re-reads the device.

## Verify

There are two ways of verifying

**ONE** Its to basically test it in any app or website, it can be Discord, YouTube, Twitter, really anything, just go and scroll and see if there isn't any issue, same with games.

**SECOND** Option is this one, but with more steps and technically more advanced.
First, find your mouse's event node:
```bash
libinput list-devices | grep -A1 -i g502
```
Then turn the wheel one notch at a time (replace `event5` with yours):
```bash
libinput debug-events --device /dev/input/event5
```
With the fix, each notch prints one line with `vert 15.00/120.0*`. Lines
with small values (like `vert 1.88/15.0`) should be gone.

If everything is alright, the fix worked!

## Uninstall

```bash
sudo rm /etc/libinput/local-overrides.quirks
```

Then log out and back in.

## Supported devices

| Device | Connection | USB ID (evdev) | Status |
|---|---|---|---|
| G502 X PLUS | LIGHTSPEED receiver (`046d:c547`) | `046d:4099` | ✅ Tested |
| G502 X LIGHTSPEED | LIGHTSPEED receiver | ? | ❓ Help wanted |
| G502 X (wired) | USB | `046d:c099` | ❓ Help wanted |

To find your IDs:

```bash
cat /sys/class/input/eventN/device/id/{vendor,product}
```

If it works for another model, please open an issue or PR with the IDs, I would REALLY appreciate it.

## Diagnostic tool
[`tools/g502_wheel_probe.py`](tools/g502_wheel_probe.py) passively reads
wheel events and prints a summary of clean notches, micro-movements, rebounds and full-notch events. It needs
`python3-evdev` and membership in the `input` group:
```bash
python3 tools/g502_wheel_probe.py 60 capture.csv
```
Note: it reads events *before* libinput, so it shows the raw high-resolution
data even with the quirk installed. Please use `libinput debug-events` method to check the
fix. This step should be made if something went wrong or if you wanna check is a hardware issue.

## Tested on

- Nobara Linux 44 (Fedora-based), kernel 7.2.11
- libinput 1.31.3
- KDE Plasma 6 (Wayland)

## Related reports

- [Kernel bugzilla #221246](https://bugzilla.kernel.org/show_bug.cgi?id=221246) — Logitech wheel regression in `hid-logitech-hidpp` since 6.19
- [CachyOS forum: Logitech wireless mice scroll wheel issues in kernel 7.0](https://discuss.cachyos.org/t/logitech-wireless-mice-scroll-wheel-issues-in-kernel-7-0/28425)
- [CachyOS forum: Logitech scrollwheel issues after Linux 6.19](https://discuss.cachyos.org/t/logitech-mouse-scrollwheel-issues-after-recent-linux-6-19-update/23110)
- [CachyOS forum: Mouse scroll wheel issues – ratchet](https://discuss.cachyos.org/t/mouse-scroll-wheel-issues-ratchet/27947)
- [Arch forums: high resolution scrolling with a G502](https://bbs.archlinux.org/viewtopic.php?id=296537)
