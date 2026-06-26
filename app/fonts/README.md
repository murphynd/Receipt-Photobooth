# Fonts for the Scuptee receipt

The "scuptee" receipt design ([receipt.py](../receipt.py)) draws its text with two
Google Fonts:

- **VT323-Regular.ttf** — the pixel/terminal body font (all text).
- **Bungee-Regular.ttf** — the big "SCUPTEE" wordmark.

Both files are committed here so the receipt renders identically on the Pi with
no download step. They are open-licensed (SIL Open Font License).

If a file is ever missing, the code falls back to a default monospace font and
prints a warning — the receipt still prints, just at lower fidelity.

To re-download the originals:

```bash
curl -L -o VT323-Regular.ttf  https://github.com/google/fonts/raw/main/ofl/vt323/VT323-Regular.ttf
curl -L -o Bungee-Regular.ttf https://github.com/google/fonts/raw/main/ofl/bungee/Bungee-Regular.ttf
```
