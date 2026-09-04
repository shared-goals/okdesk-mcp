# Okdesk MCP Development Guide

## Principles

- Keep the server small and focused: KISS, DRY, and YAGNI.
- The MCP server is a thin, read-only Okdesk REST wrapper. Business reports and
  alert criteria belong in the calling Hermes skill, not in this project.
- Never log, commit, or put `OKDESK_API_TOKEN` into fixtures, tests, or documentation.
- Preserve raw Okdesk response fields unless a validated API contract requires normalization.

## Development Workflow

- Use Make targets whenever available; run `make` or `make help` to list them.
- Run `make install` after dependency changes or on a new checkout.
- Run `make test` after each implementation change.
- Run `make format` before sharing changes.
- Run `make run` to serve the MCP over stdio; use `hermes mcp test okdesk` for
  end-to-end discovery after registering the server.

## Testing

- Write or update unit tests before changing client or tool behavior.
- Use `httpx.MockTransport`; unit tests must not call a live Okdesk account.
- Keep live validation read-only and do not print tickets or credentials in terminal output.