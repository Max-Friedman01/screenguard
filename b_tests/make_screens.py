"""Generate synthetic test screenshots with known fake personal data.

Usage (from the repo root, venv active):
    python b_tests/make_screens.py

Writes PNGs into screens/ next to this script, plus screens/expected.json, which lists
for each image the strings that SHOULD be masked (and decoys that should NOT).
All data is fake: phone numbers are from Ofcom's reserved drama ranges,
card numbers are standard test numbers, NI number uses the invalid QQ prefix.
"""
import json
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), "screens")
os.makedirs(OUT, exist_ok=True)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)  # Pillow >= 10.1


# Each screen: background, text colour, list of (x, y, size, text, label or None)
# label = what the detector should call it; None = harmless text or a decoy.
SCREENS = {
    "01_inbox_light.png": ("#ffffff", "#1d1f23", [
        (40, 30, 30, "Postbox - Inbox", None),
        (40, 110, 22, "From: housing@uni-example.ac.uk", "email"),
        (40, 150, 22, "To: max.fraser@example.com", "email"),
        (40, 220, 22, "Address: Flat 4, 21 Oxford Road, Manchester M13 9PL", "postcode"),
        (40, 260, 22, "Mobile: 07700 900456", "phone"),
        (40, 300, 22, "Emergency contact: 020 7946 0321", "phone"),
        (40, 370, 22, "Refund to account 12345678, sort code 12-34-56", "bank"),
        (40, 440, 22, "Order reference (not a card): 4111 1111 1111 1112", None),
        (40, 510, 22, "See you at the seminar on Tuesday at 3pm.", None),
    ]),
    "02_bank_light.png": ("#eef3f1", "#14211c", [
        (40, 30, 32, "Northfield Bank", None),
        (40, 110, 26, "Balance: £1,284.37", None),
        (40, 170, 24, "Sort code 12-34-56   Account number 12345678", "bank"),
        (40, 230, 30, "4111 1111 1111 1111", "card"),
        (40, 290, 22, "Card payment 5555 5555 5555 4444 Tesco Express", "card"),
        (40, 340, 22, "National Insurance: QQ 12 34 56 C", "ni"),
        (40, 390, 22, "Payroll ref 4111 1111 1111 1112", None),
    ]),
    "03_dark_mode_chat.png": ("#1e1f22", "#e6e6e6", [
        (40, 40, 24, "# group-project", None),
        (40, 110, 20, "Priya: my number is 07700 900123 if Teams dies", "phone"),
        (40, 160, 20, "Priya: or email priya.sharma92@example.com", "email"),
        (40, 210, 20, "Sam: lol ok. slides by Friday?", None),
        (40, 260, 20, "Priya: send the deposit to 98-76-54 87654321", "bank"),
    ]),
    "04_small_text_notification.png": ("#f3f3f3", "#202020", [
        (40, 40, 18, "Documents  >  coursework  >  final_report_v3.docx", None),
        # mimic a toast in the bottom-right corner, smaller text
        (1380, 900, 16, "Mum", None),
        (1380, 925, 15, "Your new card came: 4111 1111 1111 1111", "card"),
        (1380, 948, 15, "Ring me on 07700 900123 x", "phone"),
    ]),
}

# Strings the detectors should match, per label, for automatic checking.
MATCH_TEXT = {
    "email": ["housing@uni-example.ac.uk", "max.fraser@example.com", "priya.sharma92@example.com"],
    "postcode": ["M13 9PL"],
    "phone": ["07700 900456", "020 7946 0321", "07700 900123"],
    "bank": ["12-34-56", "12345678", "98-76-54", "87654321"],
    "card": ["4111 1111 1111 1111", "5555 5555 5555 4444"],
    "ni": ["QQ 12 34 56 C"],
}
DECOYS = ["4111 1111 1111 1112"]  # fails Luhn: must NOT be masked as a card

expected = {}
for name, (bg, fg, lines) in SCREENS.items():
    img = Image.new("RGB", (1920, 1080), bg)
    d = ImageDraw.Draw(img)
    should_mask, decoys = [], []
    for x, y, size, text, label in lines:
        d.text((x, y), text, font=font(size), fill=fg)
        if label:
            for s in MATCH_TEXT[label]:
                if s in text:
                    should_mask.append({"label": label, "text": s})
        for s in DECOYS:
            if s in text:
                decoys.append(s)
    img.save(os.path.join(OUT, name))
    expected[name] = {"should_mask": should_mask, "decoys": decoys}
    print("wrote", name, "-", len(should_mask), "items to mask")

with open(os.path.join(OUT, "expected.json"), "w", encoding="utf-8") as f:
    json.dump(expected, f, indent=2)
print("wrote expected.json")
