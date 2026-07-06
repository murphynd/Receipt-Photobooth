# app/ — Raspberry Pi runtime

This folder is **self-contained**: it has everything the photobooth needs to run
and nothing it doesn't. To deploy, copy *only this folder* to the Pi.

## Contents

| File / dir              | Purpose                                            |
|-------------------------|----------------------------------------------------|
| `photobooth.py`         | entry point — the IDLE→…→COOLDOWN state machine    |
| `config.py`             | all tunable knobs (edit this on-site)              |
| `audio.py`              | voice clips + pre-capture countdown                |
| `hardware.py`           | PIR sensor, camera, trigger/capture (Pi-only deps) |
| `imaging.py`            | photo enhancement + dithering pipeline             |
| `printing.py`           | receipt rendering + printer backends               |
| `receipt.py`            | the "scuptee" graphic-receipt layout               |
| `requirements.txt`      | Python deps                                         |
| `fortunes.txt`          | one fortune per line                               |
| `kiz/`                  | intro, beckon, smile, countdown & bye voice clips  |
| `fonts/`                | VT323 + Bungee TrueType faces                      |
| `fortune_icons_svg/`    | the little fortune glyphs (optional, needs cairosvg)|

`photos/` is created here at runtime for captures and receipt previews.

## Deploy & run

```bash
# from your dev machine, copy just the runtime:
scp -r app pi@<host>:~/photobooth

# on the Pi:
cd ~/photobooth
pip3 install -r requirements.txt --break-system-packages
sudo apt install libusb-1.0-0 alsa-utils

# always run from inside this folder so relative asset paths resolve:
python3 photobooth.py
```

See the repo's top-level `CLAUDE.md` for printer wiring, CUPS gotchas, and the
USB/escpos setup notes.
