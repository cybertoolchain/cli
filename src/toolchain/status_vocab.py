# src/toolchain/status_vocab.py
"""The six-status reader vocabulary, the CLI's copy (generator master plan P2.2, ES-2).

`status_vocab.json` is a byte-identical copy of the generator's `tct/src/status_vocab.json`,
which is the only place the words are spelled; the generator's parity test and
`tests/test_status_vocab.py` here both pin its digest, so a drifted copy fails a build.

Dark: nothing the CLI prints changes until `TCT_STATUS_VOCAB=v2` is set. `label()` always
speaks the vocabulary; `reader_text()` hands back the old string while the flag is off.
`unknown` ("We haven’t looked yet") is never folded into `absent` ("No documented match").
"""
from __future__ import annotations

import json
import os
import re
from importlib import resources

_DOC = json.loads(resources.files(__package__).joinpath("status_vocab.json").read_text())

STATUSES = tuple(_DOC["labels"])
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?Z?)?")


def enabled() -> bool:
    return os.environ.get(_DOC["flag"]["python"], "") == _DOC["flag"]["on"]


def label(status: str, known_from: str | None = None) -> str:
    """The reader's words for one status; `known_from` is an ISO date or timestamp."""
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, not {status!r}")
    template = _DOC["labels"][status]
    if "{day}" not in template:
        return template
    month = int(known_from[5:7]) if known_from and _DATE.fullmatch(known_from) else 0
    if not 1 <= month <= 12:
        return _DOC["undated"][status]
    day = _DOC["day"].format(d=int(known_from[8:10]), mon=_DOC["months"][month - 1])
    return template.format(day=day)


def reader_text(legacy: str, status: str, known_from: str | None = None) -> str:
    """Today's string while the flag is off, the vocabulary's once it is on."""
    return label(status, known_from) if enabled() else legacy
