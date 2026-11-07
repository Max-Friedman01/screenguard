from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Detection:
    label: str
    matched_text: str


EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)

UK_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?:\+44\s?\(?(?:0)?\)?|0)"
    r"(?:\d[\s().\-]?){9,10}"
    r"(?!\d)"
)

CARD_RE = re.compile(
    r"(?<!\d)(?:\d[\s\-]?){13,19}(?!\d)"
)

UK_POSTCODE_RE = re.compile(
    r"\b(?:"
    r"GIR\s?0AA|"
    r"[A-PR-UWYZ][0-9][0-9A-HJKPSTUW]?|"
    r"[A-PR-UWYZ][A-HK-Y][0-9][0-9ABEHMNPRV-Y]?"
    r")"
    r"\s?"
    r"[0-9][ABD-HJLNP-UW-Z]{2}"
    r"\b",
    re.IGNORECASE,
)

NI_NUMBER_RE = re.compile(
    r"\b"
    r"(?:QQ|(?!BG|GB|KN|NK|NT|TN|ZZ)[A-CEGHJ-PR-TW-Z]{2})"
    r"\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]"
    r"\b",
    re.IGNORECASE,
)

SORT_CODE_RE = re.compile(
    r"(?<!\d)\d{2}[\s\-]\d{2}[\s\-]\d{2}(?!\d)"
)

ACCOUNT_NUMBER_RE = re.compile(
    r"(?<!\d)\d{8}(?!\d)"
)


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)


def luhn_valid(value: str) -> bool:
    digits = digits_only(value)

    if not 13 <= len(digits) <= 19:
        return False

    if len(set(digits)) == 1:
        return False

    total = 0
    parity = len(digits) % 2

    for index, character in enumerate(digits):
        digit = int(character)

        if index % 2 == parity:
            digit *= 2

            if digit > 9:
                digit -= 9

        total += digit

    return total % 10 == 0



def find_sensitive_types(text: str) -> list[Detection]:
    detections: list[Detection] = []

    for match in EMAIL_RE.finditer(text):
        detections.append(
            Detection("email", match.group(0))
        )

    for match in UK_PHONE_RE.finditer(text):
        number = digits_only(match.group(0))

        if len(number) in {10, 11, 12}:
            detections.append(
                Detection("phone", match.group(0))
            )

    for match in CARD_RE.finditer(text):
        candidate = match.group(0)

        if luhn_valid(candidate):
            detections.append(
                Detection("card", candidate)
            )

    for match in UK_POSTCODE_RE.finditer(text):
        detections.append(
            Detection("postcode", match.group(0))
        )

    for match in NI_NUMBER_RE.finditer(text):
        detections.append(
            Detection("ni", match.group(0))
        )

    for match in SORT_CODE_RE.finditer(text):
        detections.append(
            Detection("bank", match.group(0))
        )

    for match in ACCOUNT_NUMBER_RE.finditer(text):
        detections.append(
            Detection("bank", match.group(0))
        )

    return deduplicate(detections)


def deduplicate(detections: list[Detection],
) -> list[Detection]:
    seen: set[tuple[str, str]] = set()
    result: list[Detection] = []

    for detection in detections:
        key = (
            detection.label,
            detection.matched_text.casefold(),
        )

        if key not in seen:
            seen.add(key)
            result.append(detection)

    return result
