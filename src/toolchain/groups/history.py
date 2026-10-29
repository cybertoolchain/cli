from __future__ import annotations

import re

import click

from ..helpers import emit, get_config, handle_errors, tool_slug
from ..models import APIError, UserInputError
from ..source import resolve_source

_CLAIM_FIELDS = ("claim_id", "revision", "subject", "object", "status", "known_from")
_DECISION_FIELDS = ("claim_id", "revision", "date", "status", "method", "origin",
                    "role", "reason", "disposition", "cause", "decided_at")


def _public_row(row: dict, fields: tuple[str, ...]) -> dict:
    cid, revision = row.get("claim_id"), row.get("revision")
    if (not isinstance(cid, str) or not re.fullmatch(r"c-[A-Za-z0-9_-]+", cid)
            or type(revision) is not int or revision < 1):
        raise APIError("The history response has an invalid claim revision.")
    result = {key: row[key] for key in fields if key in row}
    for key, value in result.items():
        if key != "revision" and value is not None:
            if not isinstance(value, str) or any(ord(c) < 32 and c not in '\n\t' for c in value):
                raise APIError("The history response has an invalid public value.")
    result["marker"] = f"{cid}@{revision}"
    return result


def _claim(row: dict) -> dict:
    return _public_row(row, _CLAIM_FIELDS)


def _public_decisions(rows: list, claim_ids: set[str]) -> list[dict]:
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise APIError("The history response has invalid decisions.")
    validated = [_public_row(row, _DECISION_FIELDS) for row in rows]
    return [row for row in validated if row["claim_id"] in claim_ids]


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
            if any("subject" in row and (not isinstance(row["subject"], str)
                       or tool_slug(row["subject"].rsplit("@", 1)[0]) != slug) for row in rows):
                raise APIError("The claim history does not match the selected tool.")
            result["claims"] = [_claim(row) for row in rows]
            ids = {row["claim_id"] for row in result["claims"]}
            result["decisions"] = _public_decisions(doc.get("decisions", []), ids)
    else:
        doc = source.fetch(f"claims/{config.site_key}.json")
        if not isinstance(doc, dict) or doc.get("brand") != config.site_key:
            raise APIError("The claim history does not match the selected product.")
        rows = doc.get("claims")
        if not isinstance(rows, dict):
            raise APIError("The history response has invalid claims.")
        claims = []
        for cid, row in rows.items():
            if not isinstance(row, dict):
                raise APIError("The history response has invalid claims.")
            # The original release identity is Tool@version, including
            # release titles; use the same slug rule as every tool command.
            subject = row.get("subject", "")
            tool = row.get("tool") or (subject.rsplit("@", 1)[0] if isinstance(subject, str) else "")
            if tool_slug(tool) == slug:
                claims.append(_claim({**row, "claim_id": cid}))
        ids = {row["claim_id"] for row in claims}
        history_rows = doc.get("history", {})
        if not isinstance(history_rows, dict):
            raise APIError("The history response has invalid decisions.")
        decisions = []
        for cid in ids:
            revisions = history_rows.get(cid, [])
            if not isinstance(revisions, list) or any(not isinstance(row, dict) for row in revisions):
                raise APIError("The history response has invalid decisions.")
            decisions.extend({**row, "claim_id": cid} for row in revisions)
        result = {"tool": slug, "brand": config.site_key, "claims": claims,
                  "decisions": _public_decisions(decisions, ids)}
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
