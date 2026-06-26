# Handoff: Scuptee — 80mm Photobooth Receipt (Arcade Pixel)

## Overview

"Scuptee" is an interactive sculpture / physical photobooth. A visitor walks up, presses a
button, and the sculpture captures **one** photo of them and prints an 80mm thermal receipt as
a keepsake. The receipt header is the Scuptee logo + a line-drawn robot mascot (90s-toy
nostalgia), followed by the captured photo, a date/time stamp, an 80s/90s-style fortune with
lucky numbers and emojis, and a QR code linking to the artist's Instagram.

This document describes the **Arcade Pixel** variation, which is the approved design.

## About the Design Files

The files in this bundle are **design references created in HTML** — a prototype showing the
intended look and behavior, **not production code to ship directly**. The implementation task is
to **recreate this design in the target environment** that drives the sculpture's printer
(e.g. an ESC/POS thermal-printer driver, a Python/Node print service, a React kiosk screen, or
a raster-image generator that rasterizes to the printer). Use that environment's established
patterns and libraries. If no environment exists yet, choose the most appropriate stack for an
80mm thermal photobooth (a common approach: render an HTML/CSS template at 576px wide → rasterize
to a 1-bit bitmap → send to the printer via ESC/POS).

### Thermal-printing reality check

Real 80mm thermal printers are **monochrome (1-bit), no grayscale, no color**, typically **576
dots wide** at 203dpi (paper is 80mm but printable width is ~72mm). The prototype simulates this
with a warm off-white paper and pure near-black ink. When implementing:

- Convert the photo to **1-bit with dithering** (Floyd–Steinberg or ordered/Bayer) — the
  prototype's halftone-dot overlay approximates this look.
- All "grayscale + contrast" CSS filters in the prototype stand in for that dithering step.
- Keep everything black-on-white; the paper tone is for the on-screen render only.

## Fidelity

**High-fidelity (hifi).** Final layout, typography, spacing, copy, and composition. Recreate it
faithfully, adapting only what physical thermal printing requires (1-bit dithering, 576px raster
width, no drop-shadows/anti-aliasing on the actual print).

## Screens / Views

### Receipt (single view)

- **Purpose**: Printed keepsake handed to the visitor after one photo capture.
- **Print medium**: 80mm thermal paper. Printable content width **~72mm / 576 dots**. Length is
  variable (continuous roll) — the design is a single vertical column, content-height driven.
- **On-screen prototype width**: 360px CSS (scale to 576px for print raster; ratio 1.6×).
- **Layout**: single centered column, vertical stack, no horizontal sub-grids except the
  itemized rows (space-between flex) and the emoji row (centered flex). Outer card padding
  **26px 26px 30px** (prototype px). Top & bottom edges are **zig-zag torn perforations**
  (decorative; omit or simplify for actual print).

Sections top → bottom:

1. **Header lockup** — robot mascot SVG (58×74) on the left + wordmark block on the right,
   centered as a group, `gap: 12px`.
   - Wordmark "SCUPTEE": font **Bungee**, 38px, line-height .85, letter-spacing -1px.
   - Tagline "■ INSERT MEMORY ■": font **VT323**, 18px, letter-spacing 5px, margin-top 4px.
2. **Dashed rule** — a 6px-tall repeating dash band (see Design Tokens → "dash band").
3. **Photo block** — `position:relative; padding:14px`. Four L-shaped **crop marks** in the
   corners (16×16px, 2px solid ink). Inside: the photo at **aspect-ratio 4/5**, `overflow:hidden`.
   - Photo treatment: `filter: grayscale(1) contrast(1.14) brightness(1.02)` + a halftone dot
     overlay (`radial-gradient(#000 30%, transparent 32%)`, `background-size:3px 3px`,
     `mix-blend-mode:multiply`, `opacity:.16`). → In production this is the **1-bit dither**.
   - Top-left "● REC" badge: VT323 16px, white text with `mix-blend-mode:difference`, 7px dot.
   - In the prototype the photo is a drag-and-drop `<image-slot>`. In production this is the
     **live captured frame** from the sculpture's camera.
4. **Timestamp** — "● MM/DD/YY HH:MM" (24-hour), VT323 18px, letter-spacing 2px, centered.
   Generated at print time from the capture moment.
5. **Dash band.**
6. **Fortune block** (centered):
   - Heading "=== YOUR FORTUNE ===", VT323 22px, letter-spacing 3px.
   - Fortune line, VT323 21px, line-height 1.25, margin 10px 4px 14px, `text-wrap:pretty`.
     Prototype copy: _"Your inner kid just called — it says more bubblegum, less worrying.
     Stay totally fresh."_ → Should be **randomly selected** from a fortune pool (see State).
   - Lucky line "LUCKY ▸ 03 11 19 27 44", VT323 20px, letter-spacing 3px. → **Randomized** 5
     two-digit numbers.
   - Emoji row: 🌈 🪀 🎮 💾 🛼 — flex, centered, `gap:12px`, font-size 22px, slight
     grayscale+contrast filter. → Pick **5 random** from a nostalgic emoji pool. these emojis live int the fortune_icon_svg folder. each is a different svg NOTE: emoji do
     not print on a 1-bit thermal printer; for real printing, substitute small **1-bit icon
     bitmaps** or drop them.
7. **Dash band.**
8. **Itemized block** — VT323 19px, line-height 1.55. Rows are `display:flex;
justify-content:space-between`:
   - `1x PHOTO CAPTURE` … `1 PLAY`
   - `1x GOOD VIBES` … `INCL.`
   - `1x FORTUNE` … `INCL.`
   - thin dotted divider (2px dash band)
   - `TOTAL` … `FREE :)` at VT323 23px
9. **Dash band.**
10. **QR block** (centered): QR code 116×116px → links to the **artist's Instagram**. Caption
    "▓ FOLLOW THE ARTIST ▓" (VT323 19px) + handle "@scuptee.studio" (VT323 24px). **The handle is
    a placeholder** — replace with the real artist handle and encode the matching profile URL.
11. **Dash band.**
12. **Footer**: "PLAYER 1 — KEEP THIS COPY" (VT323 22px, letter-spacing 3px) + "▶ PRESS THE
    BUTTON TO PLAY AGAIN" (VT323 18px, color #5c574d).

## Interactions & Behavior

The receipt itself is static printed output — there are no on-screen interactions on the
artifact. The surrounding flow:

- Visitor presses the physical button → camera captures **one** frame → fortune/lucky numbers/
  emojis are randomized → timestamp set to now → template rendered → rasterized to 1-bit →
  sent to the thermal printer → paper cut.
- QR is scannable post-print and opens the artist's Instagram.

## State Management

Per print job, generate:

- `photo`: the single captured camera frame (then dithered to 1-bit).
- `timestamp`: capture time, formatted `MM/DD/YY HH:MM` (24-hour, zero-padded).
- `fortune`: one string chosen at random from a curated 80s/90s-voice fortune pool.
- `luckyNumbers`: 5 distinct two-digit numbers (01–49 reads well), space-joined.
- `emojis`: 5 chosen from fortune icon svg folder.
- `qrUrl`: the artist Instagram profile URL (static config, not per-job).
  No persistence required beyond optional logging of how many prints have run.

## Design Tokens

**Colors** (on-screen prototype — for print, collapse to pure black on white):

- Ink / primary: `#221f1a`
- Paper background (card): `#f7f5ee`
- Stage / page background: `#e4e1d8`
- Muted ink (footer/secondary): `#5c574d`
- Photo placeholder fill: `#e9e6dc`

**Typography**:

- Display wordmark: **Bungee** (Google Fonts), 400.
- Everything else: **VT323** (Google Fonts), 400. Sizes used: 16, 18, 19, 20, 21, 22, 23, 24,
  38(Bungee) px. (For 576px print raster, multiply by ~1.6.)
- Note: VT323 / Bungee are screen webfonts. On a real printer you'd render the HTML to a raster
  with these fonts loaded, then print the bitmap — the printer's built-in font is not used.

**Spacing**: card padding 26/26/30px; section gaps via 16px-margin dash bands; small internal
gaps 4–14px.

**Dash band** (the repeating section divider):
`height:6px; background: repeating-linear-gradient(90deg, #221f1a 0 8px, transparent 8px 14px);`
Thin variant (itemized divider): `height:2px; ...0 6px, transparent 6px 10px`.

**Crop marks**: 16×16px corner Ls, 2px solid `#221f1a`.

**Perforated edges**: 8px-tall zig-zag SVG tiles top & bottom (decorative; see the `style-before`
/ `style-after` on the card). Optional for print.

**Photo dither overlay**: `radial-gradient(#000 30%, transparent 32%)` at `3px 3px`,
`mix-blend-mode:multiply`, opacity .16, over `grayscale(1) contrast(1.14) brightness(1.02)`.

## Assets

- **Robot mascot**: inline SVG, hand-built in the markup (viewBox 0 0 120 150, stroke #221f1a).
  No external file — copy the `<svg>` from the header lockup. Reusable as the brand mark.
- **QR code**: generated programmatically in the prototype as a _decorative placeholder_ (random
  module pattern, not a real scannable code). **In production, generate a real QR** encoding the
  artist's Instagram URL with a proper QR library.
- **Photo**: supplied live by the sculpture's camera (prototype uses a drop-in `<image-slot>`).
- **Fonts**: Bungee + VT323 from Google Fonts.

## Files

- `Scuptee Receipt Arcade.dc.html` — the approved Arcade Pixel design (this is the reference).
- `image-slot.js` — the drag-and-drop photo placeholder used by the prototype (dev convenience;
  replace with the live camera frame in production).
- `support.js` — runtime that renders the `.dc.html` prototype in a browser. **Prototype tooling
  only — not part of the production implementation.**
- `fortune_icons_svg` — folder full of svgs of icons.

To preview the prototype: open `Scuptee Receipt Arcade.dc.html` in a browser (it loads the two
sibling JS files and the Google Fonts). The logic class at the bottom of that file shows exactly
how the timestamp and QR are generated.
