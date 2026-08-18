# tests/test_package.py
from __future__ import annotations


def test_package_importable():
    import toolchain

    assert toolchain.__version__ == "0.1.0"
