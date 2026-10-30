from __future__ import annotations

import re
from urllib.parse import urlsplit

import click

from ..helpers import emit, get_config, handle_errors, tool_slug
from ..models import APIError, UserInputError
from ..source import resolve_source
from ..status_vocab import STATUSES, label as status_label

_CLAIM_FIELDS = ("claim_id", "revision", "subject", "object", "status", "known_from")
_DECISION_FIELDS = ("claim_id", "revision", "date", "status", "method", "origin",
                    "role", "reason", "disposition", "cause", "decided_at")


def _public_row(row: dict, fields: tuple[str, ...]) -> dict:
    cid, revision = row.get("claim_id"), row.get("revision")
    if (not isinstance(cid, str) or not re.fullmatch(r"clm_[0-9a-f]{32}", cid)
            or type(revision) is not int or revision < 1):
        raise APIError("The history response has an invalid claim revision.")
    result = {key: row[key] for key in fields if key in row}
    for key, value in result.items():
        if key != "revision" and value is not None:
            if not isinstance(value, str) or any(ord(c) < 32 and c not in '\n\t' for c in value):
                raise APIError("The history response has an invalid public value.")
    if result.get("origin") is not None:
        try:
            origin = urlsplit(result["origin"])
            if (origin.scheme != "https" or not origin.hostname
                    or origin.username is not None or origin.password is not None):
                raise ValueError
        except ValueError:
            raise APIError("The history response has an invalid public origin.") from None
    if "status" in result:
        if result["status"] not in STATUSES:
            raise APIError("The history response has an invalid reader status.")
        # This new command has no legacy label; use the shared vocabulary.
        result["label"] = status_label(result["status"], result.get("known_from") or result.get("date"))
    result["marker"] = f"{cid}@{revision}"
    return result


def _claim(row: dict) -> dict:
    return _public_row(row, _CLAIM_FIELDS)


def _identity(row: dict, brand: str, slug: str | None = None) -> str | None:
    if ("brand" in row and row["brand"] != brand
            or "scope" in row and row["scope"] != f"brand:{brand}"):
        raise APIError("The claim history does not match the selected product.")
    subject_tool = None
    if "subject" in row:
        subject = row["subject"]
        if not isinstance(subject, str):
            raise APIError("The history response has an invalid release identity.")
        subject_tool, separator, version = subject.rpartition("@")
        if not separator or not subject_tool.strip() or not version.strip():
            raise APIError("The history response has an invalid release identity.")
    tool = row.get("tool", subject_tool)
    if ("tool" in row and (not isinstance(tool, str) or not tool.strip())
            or subject_tool is not None and tool != subject_tool):
        raise APIError("The history response has conflicting tool identities.")
    selected = tool_slug(tool) if tool is not None else None
    if (tool is not None and not selected
            or slug is not None and selected is not None and selected != slug):
        raise APIError("The claim history does not match the selected tool.")
    return selected


def _public_decisions(rows: list, claims: list[dict], brand: str, slug: str) -> list[dict]:
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise APIError("The history response has invalid decisions.")
    heads = {row["claim_id"]: row["revision"] for row in claims}
    validated = []
    for row in rows:
        _identity(row, brand, slug)
        public = _public_row(row, _DECISION_FIELDS)
        if public["claim_id"] in heads:
            if public["revision"] > heads[public["claim_id"]]:
                raise APIError("The history response has an inconsistent revision.")
            validated.append(public)
    return validated


def _free_history(doc: dict, brand: str, slug: str) -> tuple[list[dict], list[dict]]:
    rows, history_rows = doc.get("claims"), doc.get("history")
    if not isinstance(rows, dict) or not isinstance(history_rows, dict):
        raise APIError("The history response has invalid claims or history.")
    claims, decisions = [], []
    for cid, row in rows.items():
        if not isinstance(row, dict) or "claim_id" in row and row["claim_id"] != cid:
            raise APIError("The history response has invalid claims.")
        public = _claim({**row, "claim_id": cid})
        if "withheld" in row:
            if (set(row) != {"revision", "status", "withheld"}
                    or row["withheld"] != "evidence_revoked" or row["status"] != "unknown"
                    or history_rows.get(cid) != []):
                raise APIError("The history response has an invalid withheld claim.")
            continue
        if (not {"subject", "status", "object"} <= row.keys()
                or not isinstance(row["object"], str) or not row["object"].strip()):
            raise APIError("The history response has an incomplete claim.")
        selected = _identity(row, brand)
        if selected != slug:
            continue
        revisions = history_rows.get(cid)
        if not isinstance(revisions, list) or not revisions:
            raise APIError("The history response is missing the selected claim's history.")
        previous = 0
        for revision in revisions:
            if (not isinstance(revision, dict) or type(revision.get("revision")) is not int
                    or not previous < revision["revision"] <= row["revision"]
                    or "claim_id" in revision and revision["claim_id"] != cid):
                raise APIError("The history response has an inconsistent revision.")
            previous = revision["revision"]
        if (previous != row["revision"]
                or any(row[key] != revisions[-1].get(other) for key, other in
                       (("status", "status"), ("object", "object"), ("known_from", "date")) if key in row)):
            raise APIError("The history response does not match the current claim.")
        claims.append(public)
        decisions.extend({**revision, "claim_id": cid} for revision in revisions)
    return claims, _public_decisions(decisions, claims, brand, slug)


@click.command("history")
@click.argument("slug")
@click.pass_context
@handle_errors
def history(ctx: click.Context, slug: str) -> None:
    """A tool's breaking-change claims and correction history, with revision markers."""
    config = get_config(ctx)
    slug = tool_slug(slug)
    if not slug:
        raise UserInputError("Give a tool name or slug.")
    source = resolve_source(config)
    if config.api_key:
        doc = source.fetch(f"tools/{slug}/history")
        if not isinstance(doc, dict):
            raise APIError("The history response is not an object.")
        if ("brand" in doc and doc["brand"] != config.site_key
                or "tool" in doc and (not isinstance(doc["tool"], str) or tool_slug(doc["tool"]) != slug)):
            raise APIError("The claim history does not match the selected product and tool.")
        result = {"tool": slug, "brand": config.site_key}
        # An older server without markers stays distinguishable from a
        # measured empty claim set. Never manufacture a successful readback.
        if "claims" in doc:
            rows = doc["claims"]
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise APIError("The history response has invalid claims.")
            for row in rows:
                _identity(row, config.site_key, slug)
            result["claims"] = [_claim(row) for row in rows]
            result["decisions"] = _public_decisions(doc.get("decisions", []), result["claims"], config.site_key, slug)
    else:
        doc = source.fetch(f"claims/{config.site_key}.json")
        if not isinstance(doc, dict) or doc.get("brand") != config.site_key:
            raise APIError("The claim history does not match the selected product.")
        claims, decisions = _free_history(doc, config.site_key, slug)
        result = {"tool": slug, "brand": config.site_key, "claims": claims,
                  "decisions": decisions}
    if config.output == "json":
        emit(result, config)
    elif "claims" not in result:
        if config.output == "table":
            click.echo("Claim revision markers are not available from this server.")
        else:
            emit([{"state": "no_marker", "tool": slug, "brand": config.site_key}], config)
    elif not result["claims"]:
        if config.output == "table":
            click.echo("No breaking-change claims in the published ledger for this tool.")
        else:
            emit([{"state": "no_claims", "tool": slug, "brand": config.site_key}], config)
    elif config.output == "table":
        emit(result["claims"], config)
        if result.get("decisions"):
            click.echo("\nCorrection history")
            emit(result["decisions"], config)
    else:
        emit([{**row, "record_type": "claim"} for row in result["claims"]] +
             [{**row, "record_type": "decision", "marker": f"{row['claim_id']}@{row['revision']}"}
              for row in result.get("decisions", [])], config)
