# ScreenGuard

Screen sharing that can't leak your private details. A local AI (Tether's QVAC, running on your own laptop) reads every frame of your screen and covers personal data (emails, card numbers, phone numbers, bank details, postcodes, National Insurance numbers) **before** anything leaves the machine. The masked screen then goes straight to your viewers peer-to-peer over Holesail, with no Zoom-style server in the middle.

Built at GreatUniHack 2026 for the Tether "Be Your Own Datacenter" challenge.

## How the data flows

```
SHARER LAPTOP (all AI inference happens here, nothing leaves unmasked)
  Screen capture (mss)
    -> our own preview window blacked out (no mirror effect)
    -> QVAC OCR, on local hardware            <- inference: local only, no cloud
    -> detectors: regex + Luhn checksum
    -> fail-closed guard: anything changed since the last checked frame
       is covered "checking..." until QVAC has read it
    -> solid labelled masks (OpenCV)
    -> MJPEG on 127.0.0.1:8080 (masked frames only; no raw endpoint exists)
         |
         |  Holesail: encrypted peer-to-peer tunnel, no relay server
         v
VIEWER LAPTOP
  Holesail client -> browser shows the masked stream
```

**Fail-closed rule:** a pixel is shown only if it is identical to the last frame the AI finished checking. If the AI is slow, paused or crashes, changed areas stay covered. There is no timeout that ever releases unchecked content.

## Setup (Windows, both laptops)

Needs Python 3.10+ (3.12 recommended), Node.js LTS (for Holesail), Git.

```powershell
git clone <this repo>
cd screenguard
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
npm i -g holesail
```

`requirements.txt` pulls the self-contained QVAC wheel (bundled runtime, no separate install) from Tether's GitHub release. The first run downloads the QVAC models.

## Run

**Sharer:**
```powershell
python -m app.main
```
A small preview window shows exactly what viewers see. Keys work from any window:

| Key | Action |
| --- | --- |
| F8 | Pause / resume the AI (new content stays covered: shows fail-closed) |
| F9 | Panic: blank the stream / restore |
| q | Quit (in the preview window) |

Options: `--fake` (fake analyser for testing), `--image <png>` (static image instead of the screen), `--monitor N`, `--port`, `--fps`, `--no-preview`.

**Share it peer-to-peer (sharer):**
```powershell
holesail --live 8080
```
Copy the `hs://...` connection key it prints.

**Viewer laptop:**
```powershell
holesail hs://<key-from-sharer>
```
Open the local address it prints in a browser (see `holesail --help` to pick the local port).

**Or share via Zoom/Teams:** share the "ScreenGuard preview" window instead of your screen.

## Testing

```powershell
python tests/make_screens.py        # synthetic screenshots with fake personal data
python tests/check_detections.py    # scores ai/analyze.py: hits, misses, false alarms
```

Demo material in `demo/`: fake inbox and bank pages (fictional data), and `notify.ps1`, which fires a Windows notification from "Mum".

## Project layout

```
shared.py   Box: the frozen interface between the AI and the app
ai/         QVAC OCR + detectors -> analyze_frame(img) -> list[Box]
app/        capture, fail-closed guard, masks, MJPEG server, main loop
demo/       demo pages and notification script
tests/      synthetic test screens + detection scorer
```

## No cloud AI

All inference runs through QVAC on the sharer's laptop. No code in this repository calls any cloud AI API.
