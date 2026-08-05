import re
import secrets


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "event"


def make_unique_suffix(length: int = 5) -> str:
    return secrets.token_hex(length // 2 + 1)[:length]
