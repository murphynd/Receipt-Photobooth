# Deploying the Photobooth as a gallery service

Make the booth run unattended (auto-start on boot, auto-restart on crash, logs
to the journal) and let you watch it remotely from your laptop without touching
the install. Copy-paste from a terminal on the Pi (`kalekat@raspberrypi`).

The repo is assumed to live at `~/Desktop/receipt-photobooth`. If you moved it,
edit the three paths in `deploy/photobooth.service` to match before installing.

---

## 0. Pre-flight — confirm the facts the unit assumes

Run these on the Pi and check the output against the notes:

```bash
cat /etc/os-release | head -2      # Bullseye (11) or Bookworm (12)?
which python3                      # expect /usr/bin/python3
id -u kalekat                      # expect 1000 (used in XDG_RUNTIME_DIR)
id -nG kalekat                     # must include: gpio video audio plugdev lp
```

- **`which python3` is not `/usr/bin/python3`** (e.g. you use a virtualenv):
  set `ExecStart=` in the unit to that interpreter's full path, e.g.
  `ExecStart=/home/kalekat/Desktop/receipt-photobooth/.venv/bin/python photobooth.py`.
- **`id -u kalekat` is not 1000:** update `XDG_RUNTIME_DIR=/run/user/<uid>` in the unit.
- **Missing a group** (e.g. `gpio`, `video`, `audio`, `lp`): add it, then reboot:
  ```bash
  sudo usermod -aG gpio,video,audio,plugdev,lp kalekat
  ```
- **Bullseye vs Bookworm:** the unit works on both. picamera2 is the camera
  stack on both; just make sure the camera works by hand first (`libcamera-hello`
  on Bookworm / `libcamera-still` on Bullseye).

Quick sanity check that it runs by hand in service (button) mode before installing:

```bash
cd ~/Desktop/receipt-photobooth/app
PHOTOBOOTH_INPUT_MODE=button python3 photobooth.py
# press the GPIO-27 button -> should capture + print, then Ctrl+C
```

---

## 1. Install and start the service

```bash
sudo cp ~/Desktop/receipt-photobooth/deploy/photobooth.service /etc/systemd/system/photobooth.service
sudo systemctl daemon-reload
sudo systemctl enable --now photobooth     # start now + on every boot
systemctl status photobooth                # should read: active (running)
```

If you edit the unit later: `sudo systemctl daemon-reload && sudo systemctl restart photobooth`.

Common controls:

```bash
sudo systemctl restart photobooth
sudo systemctl stop photobooth
sudo systemctl disable photobooth          # stop auto-starting at boot
```

> **CUPS note:** the printer backend is `cups` (pipes ESC/POS to `lp -d POS80_raw`).
> Per `CLAUDE.md`, if you switch to the raw `usb` backend instead, first disable
> the CUPS queues (`sudo cupsdisable Printer_POS-80 POS80_raw`) so escpos can grab
> the USB device, and add the `99-pos80.rules` udev rule so the service user can
> open it without sudo.

---

## 2. Logging — the event story

Logging now runs through Python's `logging` (see `app/log.py`); every booth
event is one clean line, and systemd's journald captures stdout. Follow it live:

```bash
journalctl -u photobooth -f                 # live tail (this is the main view)
journalctl -u photobooth -n 100 --no-pager  # last 100 lines
journalctl -u photobooth --since "10 min ago"
journalctl -u photobooth -p warning         # only warnings/errors
```

A normal visit reads like this:

```
photobooth ready (trigger=button, printer=cups); waiting for motion
camera: initialized (PIR on GPIO 17, trigger=button)
PIR: motion detected
beckon: playing clip
armed: waiting for button press (up to 20s)
trigger: button pressed
capture: saved photo_20260629_140312.jpg (148 KB)
print: receipt sent (cups queue POS80_raw)
cooldown: 3.0s; waiting for area to clear
re-armed; waiting for motion
```

Failures are loud and labelled: `print: FAILED via cups (...)`, `trigger: none
within timeout`, or a full traceback under `cycle error; recovering and
re-arming` (one bad cycle no longer kills the service). Bump detail with
`PHOTOBOOTH_LOG_LEVEL=DEBUG` in the unit if needed.

Want the journal to survive reboots (default on most Pi OS images, but to be sure):

```bash
sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald
```

---

## 3. Remote access

### SSH (confirm it's on)

```bash
sudo systemctl enable --now ssh
sudo systemctl status ssh        # active (running)
```

If it was off: `sudo raspi-config` -> Interface Options -> SSH -> enable
(or `sudo touch /boot/ssh` and reboot). From your laptop: `ssh kalekat@raspberrypi`.

### Tailscale (works from anywhere, no port forwarding)

Gallery Wi-Fi is uncertain, so Tailscale gives you a stable private address that
follows the Pi onto any network:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --hostname=furby-photobooth
# follow the printed URL once to authenticate the Pi to your tailnet
tailscale ip -4          # the 100.x.y.z address
```

Install Tailscale on your laptop, sign in to the same account, then from
anywhere:

```bash
ssh kalekat@furby-photobooth          # MagicDNS name, or use the 100.x.y.z IP
ssh kalekat@furby-photobooth 'journalctl -u photobooth -f'   # tail without a full login
```

Optional: `sudo tailscale set --ssh` to use Tailscale SSH (no key management),
and the Pi keeps `furby-photobooth` as its name on the tailnet regardless of the
gallery's DHCP.

---

## 4. Stable address

With Tailscale, `furby-photobooth` (MagicDNS) is already your stable handle —
preferred for the gallery since it ignores the local network entirely.

For a stable address on the gallery LAN too, the cleanest is a **DHCP
reservation** on the gallery router (pin the Pi's MAC — `ip link show wlan0` /
`eth0` — to a fixed IP). If you can't touch the router, set a static IP on the
Pi (Bookworm uses NetworkManager):

```bash
# Bookworm (NetworkManager) — adjust con name (nmcli con show) and addresses:
sudo nmcli con mod "preconfigured" ipv4.addresses 192.168.1.50/24 \
  ipv4.gateway 192.168.1.1 ipv4.dns 192.168.1.1 ipv4.method manual
sudo nmcli con up "preconfigured"
```

On Bullseye (dhcpcd) add to `/etc/dhcpcd.conf` instead:

```
interface wlan0
static ip_address=192.168.1.50/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1
```

You can also reach it by hostname on most home/gallery LANs via mDNS:
`ssh kalekat@raspberrypi.local`.

---

## 5. Dry run — confirm the whole story scrolls by

From your laptop:

```bash
ssh kalekat@furby-photobooth          # or raspberrypi.local / the static IP
journalctl -u photobooth -f           # leave this tailing
```

Then at the booth, wave at the PIR and press the button. You should watch the
sequence from §2 scroll past in real time: `PIR: motion detected` -> `beckon` ->
`armed` -> `trigger: button pressed` -> `capture: saved ...` -> `print: receipt
sent ...` -> `re-armed`. A receipt should print. That confirms end-to-end:
remote tail, live events, and the hardware path — without touching the running
install.

Reboot test (gallery-grade): `sudo reboot`, wait, then `systemctl status
photobooth` should be `active (running)` again on its own.

---

## 6. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `active (running)` but nothing happens on motion | Button not wired to GPIO 27, or the unit isn't in button mode — confirm `Environment=PHOTOBOOTH_INPUT_MODE=button` and check `id -nG kalekat` includes `gpio`. |
| Camera errors at start (`cannot allocate`, libcamera) | Another process holds the camera, or `kalekat` lacks the `video` group. Stop any preview app; `sudo usermod -aG video kalekat` then reboot. |
| No beckon / countdown audio | System service can't reach the user audio session. Confirm `XDG_RUNTIME_DIR=/run/user/<uid>` matches `id -u kalekat`, and `kalekat` is in `audio`. Audio is non-critical — capture+print still work. If it stays stubborn, run as a **user service** instead: `systemctl --user enable --now photobooth` + `sudo loginctl enable-linger kalekat`. |
| `print: FAILED via cups` | `lp`/CUPS not running, or queue name wrong. `systemctl status cups`, `lpstat -p`, confirm `CUPS_PRINTER_NAME` in `config.py` matches a real queue. |
| Printer "Resource busy" (if you switch to `usb` backend) | CUPS is holding the USB device. `sudo cupsdisable Printer_POS-80 POS80_raw` (see `CLAUDE.md` gotcha #1). |
| Restarts in a loop | `journalctl -u photobooth -n 50` for the traceback. Hard init failures (camera/import) crash before the per-cycle guard; fix the root cause shown. |
