import re

PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"\+?\d[\d\s\-().]{7,}\d"),
    "id": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}

CARD_RE = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")


def scan(text: str) -> list[str]:
    found = [name for name, pat in PII_PATTERNS.items() if pat.search(text)]
    if _has_card(text):
        found.append("card")
    return found


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n = n * 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _has_card(text: str) -> bool:
    for match in CARD_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            return True
    return False
