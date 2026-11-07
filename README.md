# ScreenGuard

ScreenGuard checks screenshots locally before they are shared. QVAC performs OCR on the sharer's machine; deterministic Python detectors identify sensitive values; opaque masks are applied before the frame reaches MJPEG or Holesail.

## Person A setup

Use Python 3.13 or newer and Node.js 22 or newer.

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install @qvac/sdk@0.19.1
```

The JavaScript SDK is the QVAC inference boundary. The Python layer does not call a cloud OCR service and does not use the broken Python `bare-rpc` transport.

## Verify local QVAC OCR

Run the standalone sidecar against the prepared screenshot:

```powershell
node .\qvac_sidecar\test_ocr.mjs .\tests\screens\privacy-test.png
```

Diagnostics go to stderr. The JSON on stdout contains `status`, OCR text, bounding boxes, and confidence values.

Run the complete Person A pipeline:

```powershell
python .\test_analyze.py .\tests\screens\privacy-test.png
```

The analyzer saves the NumPy image to a temporary PNG, invokes local QVAC OCR, converts QVAC coordinates into `OCRBlock` values, merges adjacent same-line blocks, and applies the email, UK phone, payment-card, postcode, National Insurance, sort-code, and account-number detectors. OCR failures raise an exception so the application can fail closed.

Generate a masked demonstration image:

```powershell
python .\draw_results.py `
  .\tests\screens\privacy-test.png `
  .\tests\screens\privacy-test-qvac-masked.png
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest .\tests\test_detectors.py -v
```

The standard test card `4111 1111 1111 1111` is synthetic test data. The original screenshot is never sent to the network by the analysis layer; only the final masked image belongs in the sharing path.

## Data path

```text
screen capture -> local QVAC OCR -> Python detectors -> opaque masks -> MJPEG -> Holesail viewer
```

The viewer receives only checked, masked frames. An analysis exception is not treated as an empty detection result.
