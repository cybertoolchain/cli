"""Request-time source-check age, using the canonical UTC badge contract."""
from __future__ import annotations
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
_DOC=json.loads(Path(__file__).with_name('status_vocab.json').read_text())
_STALE_AFTER=timedelta(days=_DOC['words']['gates']['stale_after_days'])
_RAN_WITHIN=timedelta(days=_DOC['words']['gates']['ran_within_days'])
_ISO = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})"
    r"(?:T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]{1,9}))?(Z|[+-][0-9]{2}:[0-9]{2})?)?"
)


def _parse(value) -> datetime | None:
    """A strict ISO 8601 reader that gives the same answer as the site twin, or None."""
    if not isinstance(value, str):
        return None
    m = _ISO.fullmatch(value)
    if not m:
        return None
    year, month, day, hour, minute, second, frac, zone = m.groups()
    micro = int((frac or "")[:3].ljust(3, "0")) * 1000  # milliseconds, like the site
    try:
        when = datetime(
            int(year), int(month), int(day), int(hour or 0), int(minute or 0), int(second or 0),
            micro, tzinfo=timezone.utc,
        )
        if zone and zone != "Z":
            off_h, off_m = int(zone[1:3]), int(zone[4:6])
            if off_h > 23 or off_m > 59:
                return None
            shift = timedelta(hours=off_h, minutes=off_m)
            when = when - shift if zone[0] == "+" else when + shift
    except (ValueError, OverflowError):
        return None
    return when


def _utc(now: datetime) -> datetime:
    return now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)


def badge_word(checked_at: datetime | str | None, *, now: datetime) -> str:
    """Name the age of a successful check, using UTC days and no cached word."""
    checked = _utc(checked_at) if isinstance(checked_at, datetime) else _parse(checked_at)
    now = _utc(now)
    labels = _DOC["freshness"]
    if checked is None or checked > now:
        return labels["unknown"]
    days = (now.date() - checked.date()).days
    key = "today" if days == 0 else "yesterday" if days == 1 else "week" if now - checked <= _STALE_AFTER else "old"
    return labels[key]



def age_freshness(value, *, now=None):
    now = _utc(now or datetime.now(timezone.utc))
    if not isinstance(value,dict) or type(value.get('pages')) is not int or type(value.get('pages_checked')) is not int or value['pages']<1 or value['pages']!=value.get('pages_checked'):
        return None
    checked=_parse(value.get('checked_at'))
    if checked is None or checked>now:
        return None
    return {'word':badge_word(checked,now=now),'checked_at':checked.isoformat(),'pages':value['pages'],'pages_checked':value['pages_checked']}

def fresh_run(evidence, *, now):
    """The date of the newest passed run in public rows, if it's still inside the run window."""
    ran=[]
    for row in evidence or []:
        test=row.get('test') if isinstance(row,dict) else None
        if isinstance(test,dict) and test.get('outcome')=='passed':
            at=_parse(test.get('executed_at'))
            if at is not None and at<=now and now-at<=_RAN_WITHIN:ran.append((at,test['executed_at']))
    return max(ran)[1] if ran else None


def _run_mark(claims, *, now):
    ran=[at for at in (fresh_run(row.get('evidence'),now=now) for row in claims) if at]
    return {'word':_DOC['words']['run_mark'],'executed_at':max(ran,key=_parse)} if ran else None


def age_payload(payload, *, now=None):
    now=_utc(now or datetime.now(timezone.utc))
    result=dict(payload)
    if isinstance(result.get('tools'),list):result['tools']=[age_payload(row,now=now) if isinstance(row,dict) else row for row in result['tools']]
    if 'freshness' in result: result['freshness']=age_freshness(result['freshness'],now=now)
    if isinstance(result.get('claims'),dict):
        claims={}
        labels=_DOC['words']['labels']
        for key,row in result['claims'].items():
            checked=_parse(row.get('checked_at'))
            if checked and checked>now:checked=None
            word=row['word']
            if checked and now-checked>_STALE_AFTER and word not in [labels[k] for k in ('corrected','under_review','disagree','not_checked')]:word=labels['stale']
            if word==labels['ran_it'] and fresh_run(row.get('evidence'),now=now) is None:word=labels['saw_it']
            claims[key]={**row,'word':word,'checked_at':checked.isoformat() if checked else None,'detail':badge_word(checked,now=now)+(' · '+_DOC['freshness']['changed'] if row.get('page_changed') else '')}
        result['claims']=claims
        if 'run_mark' in result:result['run_mark']=_run_mark(claims.values(),now=now)
    return result
