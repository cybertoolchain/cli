# Typed corrections

`toolchain flag` reports a published fact for review on either brand. It needs the
exact `claim_id`, `claim_rev` (at least one) and `claim_hash` shown by a supported
published fact surface; pass `claim_hash` as `--observed-hash`. Never infer a
revision from the tool name or replace a missing revision with zero.

```sh
toolchain --site cyber flag --claim-id "$CLAIM_ID" --claim-rev "$CLAIM_REV" \
  --observed-hash "$CLAIM_HASH" --tool example --kind wrong --predicate mcp \
  --proposal '{"value":"provides_server","url":"https://example.com/docs/mcp"}'
```

Set `TOOLCHAIN_API_KEY` to your account API key before calling the command. Use
`--site ai` for an AI Toolchain fact. A key needs Researcher or Business access on
the selected brand. This does not change the CLI's existing read API selection.

`--kind` accepts wrong, missing, outdated or unclear. `--predicate` accepts mcp,
api, capability, feature or price. `--proposal` takes that predicate's JSON shape,
validated again by the server against the exact published fact. Optional `--note`
is limited to 500 characters; `--evidence-url` is a public URL. Do not put personal
details, credentials or private customer information in notes, proposal text or
URLs.

The key only admits and limits the request. It is not an account session: the
stored report carries no account or key identity, counts in the same anonymous
bucket as other unlinked reports, and keeps day-level dates. It does not appear
in the account's My Requests. `received` with `persisted: true` means the report
was stored for review; it is not proof of a published correction.

The client checks the versioned capability endpoint before writing. A missing,
older, disabled or mismatched capability refuses the operation without a POST;
it never falls back to legacy feedback. Writes are never cached or automatically
retried, and redirects are not followed. The client hashes the exact JSON body
bytes for the configured CloudFront origin signature. A generic edge refusal is
not reported as a subscription problem; that explanation requires a matching
versioned, brand-specific application error. A timeout after a POST means delivery is
unknown, not that nothing was stored. Server error bodies and credentials are
never printed by this write client, including with `--debug`.

A random ownership capability exists in memory for the request. Internal callers
can reuse it for an idempotent retry; the CLI does not print or save it, and this
release has no CLI edit, withdrawal or deletion command. Attachment uploads use
that same in-memory capability to prove ownership separately from API-key
admission. Losing the capability cannot be repaired by presenting the API key.

## Attachments

Repeat `--attachment FILE` (or `-a FILE`) on `toolchain flag` to attach selected
local evidence, for example `--attachment screenshot.png --attachment notes.txt`.
Supported files are PNG, JPEG, WebP, GIF, PDF, plain text and Markdown: up to three
regular files, 8 MiB each and 16 MiB total. Symlinks and unsupported extensions are
refused before the report is sent. The server also caps reservations at 64 MiB per
IP per day; pending uploads count against the limits.

The report is stored first. The client then checks fresh attachment availability
and requests a fixed, one-shot upload URL using the private ownership capability.
File bytes go only to the selected brand's private quarantine bucket, with the
signed content type and length, a 15-minute expiry and a conditional PUT. API
keys and the ownership capability are never forwarded to that upload URL. The
CLI does not inspect or render file contents, cache files, or print or save the
ownership capability. The offline scanner identifies the actual type and
converts accepted files to inert PNG or plain text; originals are erased. Files
and renditions are never published or sent to a model. MCP remains URL-only and
does not accept binary uploads.

Attachments require separately approved live scanner qualification and deployment
configuration. The committed local engine acceptance does not enable uploads.
An unavailable scanner, server refusal or failed file upload leaves the report
received; the error says the report was received and explains that attachments
were unavailable, refused or unconfirmed. Do not resubmit the report merely to
retry a file: this CLI has no separate attachment retry command, and its private
ownership capability is not retained after the invocation. A successful upload
means waiting for the safety check, not that the file was accepted as clean.

## Separate activation and release

The backend and hosted MCP deploy independently of this CLI package. Backend
`CTK_AGENT_FEEDBACK_ENABLED=1` remains off by default; MCP's existing queue switch
is separate. Prepare and verify the billing consumer before enabling typed MCP
sends. No permission expansion is needed for MCP: it continues to send only to
its existing queue. Both brands' configured subscriber endpoint is the shared
`https://api.cybertoolchain.io`; the selected brand is explicit and verified in
every capability and persistence receipt.

Before activation, verify the approved backend package, public canonical claim
artifacts, storage/checkpoint readiness, existing front-door header forwarding,
rate limits, and both-brand receipts. Local tests are not deployment receipts.
This change does not release the CLI package, enable the flags or submit real
reports.
