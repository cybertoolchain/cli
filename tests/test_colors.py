# tests/test_colors.py
from __future__ import annotations

from toolchain.colors import PALETTES


def test_all_four_modes_present():
    assert set(PALETTES) == {"dark", "light", "sepia", "contrast"}


def test_each_mode_has_all_four_accents():
    for mode, palette in PALETTES.items():
        assert set(palette) == {"teal", "blue", "amber", "magenta"}, mode


def test_dark_teal_matches_brand_yaml():
    assert PALETTES["dark"]["teal"] == (0x34, 0xE2, 0xD4)


def test_contrast_teal_matches_brand_yaml():
    assert PALETTES["contrast"]["teal"] == (0x45, 0xF0, 0xDE)
