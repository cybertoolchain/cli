# src/toolchain/colors.py
from __future__ import annotations

RGB = tuple[int, int, int]


def _hex(value: str) -> RGB:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


# generator-brand/brands/cyber/brand.yaml palette.<mode>.{teal,blue,amber,magenta}
# — the 4 accents every site theme defines. teal is the primary brand color
# (banner, menu headers); all four double as a JSON syntax-highlighting
# palette (keys/strings/numbers/literals). Adding a 5th site theme means
# adding its row here — everything else (VALID_MODES, banner, JSON
# highlighting) derives from this dict.
PALETTES: dict[str, dict[str, RGB]] = {
    "dark": {
        "teal": _hex("#34e2d4"),
        "blue": _hex("#4aa8ff"),
        "amber": _hex("#ffb454"),
        "magenta": _hex("#ff6ac1"),
    },
    "light": {
        "teal": _hex("#056f66"),
        "blue": _hex("#1f5fd0"),
        "amber": _hex("#8a5300"),
        "magenta": _hex("#b32573"),
    },
    "sepia": {
        "teal": _hex("#0f736a"),
        "blue": _hex("#1d6ba6"),
        "amber": _hex("#8a5a00"),
        "magenta": _hex("#a52168"),
    },
    "contrast": {
        "teal": _hex("#45f0de"),
        "blue": _hex("#8fd0ff"),
        "amber": _hex("#ffd34d"),
        "magenta": _hex("#ff9ede"),
    },
}
