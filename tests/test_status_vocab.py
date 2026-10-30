# tests/test_status_vocab.py
from __future__ import annotations

import hashlib
import re
from importlib import resources

import pytest

from toolchain import status_vocab

#: The generator's tct/tests/test_status_vocab_parity.py pins this same digest.
#: Change the vocabulary there first, copy the file here, update both.
PINNED_DIGEST = "19cc6c60fbbceb6e2a7fa706ae62de899b6544bb0d9efaf293dbad04ee75fd2e"


def test_copy_matches_the_generator_canonical_file():
    raw = resources.files("toolchain").joinpath("status_vocab.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PINNED_DIGEST


def test_six_statuses_in_order():
    assert status_vocab.STATUSES == ("supported", "suggested", "contested", "stale", "absent", "unknown")


@pytest.mark.parametrize("status,when,text", [
    ("supported", "2026-10-17T03:00:00.000000Z", "Checked 17 Oct"),
    ("supported", None, "Checked"),
    ("suggested", None, "Our best guess"),
    ("contested", None, "Under review"),
    ("stale", "2026-10-03", "Checked 3 Oct, page changed since"),
    ("stale", "junk", "Checked, page changed since"),
    ("absent", None, "No documented match"),
    ("unknown", None, "We haven’t looked yet"),
])
def test_labels(status, when, text):
    assert status_vocab.label(status, when) == text


def test_a_status_outside_the_six_is_refused():
    with pytest.raises(ValueError):
        status_vocab.label("maybe")


def test_no_label_names_a_us_time_zone():
    labels = [status_vocab.label(s, "2026-10-17") for s in status_vocab.STATUSES]
    assert not [t for t in labels if re.search(r"\b(E[SD]?T|C[SD]?T|M[SD]?T|P[SD]?T|Eastern|Pacific)\b", t)]


def test_dark_by_default(monkeypatch):
    monkeypatch.delenv("TCT_STATUS_VOCAB", raising=False)
    assert status_vocab.reader_text("old words", "unknown") == "old words"
    monkeypatch.setenv("TCT_STATUS_VOCAB", "v2")
    assert status_vocab.reader_text("old words", "unknown") == "We haven’t looked yet"
