# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A client-side maintenance bot for [pt.wikifur.com](https://pt.wikifur.com) and
[en.wikifur.com](https://en.wikifur.com) (Portuguese/English WikiFur), talking to the
MediaWiki Action API via [mwclient](https://mwclient.readthedocs.io/). It's a personal
tool, public for transparency — there is no server-side component; everything runs
through the `bot` CLI against the live wikis.

## Commands

```sh
uv sync                       # install deps into .venv
uv run bot check               # connectivity + MediaWiki version (no login)
uv run bot whoami               # verify bot login and rights
uv run bot recent -n 20         # watch recent changes
uv run bot double-redirects      # preview double-redirect fixes (dry run)
uv run bot double-redirects --apply
uv run bot page "Some Title"     # show a page's wikitext + basic info
uv run bot page "Some Title" --raw
uv run bot edit "Some Title" --text "new wikitext" --summary "why"          # dry-run diff
uv run bot edit "Some Title" --file new.wikitext --summary "why" --apply    # save for real
uv run bot check --lang en       # any command, against en.wikifur.com instead of pt (default)
ruff check .                     # lint (line-length 120, see pyproject.toml)
```

There is no test suite yet.

## Architecture

Two files hold all the logic:

- `wikifur_bot/client.py` — connection/auth. Builds the `requests.Session` (user-agent +
  `cf_clearance` cookie) and returns a logged-in (or anonymous) `mwclient.Site` via `connect(lang, login)`.
- `wikifur_bot/cli.py` — argparse CLI with one `cmd_*` function per subcommand, dispatched
  through a `handlers` dict in `main()`.

**Multi-wiki:** every command takes `--lang`/`-l` (default from `DEFAULT_LANG` in `.env`).
Hosts are hardcoded as `{lang}.wikifur.com` with script path `/w/`. Credentials are looked
up per language as `{LANG}_BOT_USERNAME` / `{LANG}_BOT_PASSWORD` env vars. Both wikis
predate `Special:BotPasswords` (pt runs MediaWiki 1.23.16), so login uses a dedicated bot
account's normal legacy credentials, not an app password.

**Cloudflare:** both wikis sit behind a Cloudflare JS challenge that 403s every
non-browser HTTP client (curl, `requests`, mwclient) until it's worked around. The
workaround is a `cf_clearance` cookie copied from a real browser session
(`CF_CLEARANCE` in `.env`), paired with a `USER_AGENT_SPOOF` that must match that
browser's UA **character-for-character** — the cookie is bound to the UA (and IP) that
solved the challenge. The cookie is set on the parent `.wikifur.com` domain, so one
`CF_CLEARANCE` covers every language subdomain, but it expires and needs periodic
refreshing from the browser. `cli.py`'s `main()` catches exceptions and prints a
Cloudflare-specific hint whenever the error looks like a block (403 / "Just a moment" /
"cloudflare" in the message).

**Write-command convention:** every mutating subcommand defaults to a dry run that prints
a unified diff (or a `PLAN`/`FIX` line for `double-redirects`) and only writes when
`--apply` is passed; `edit --apply` additionally requires `--summary`. New write tasks
(category renames, template migrations, etc.) should follow this same
preview-by-default-then-`--apply` shape when added to `cli.py`.

**Double-redirect fixing** (`cmd_double_redirects`): pulls `Special:DoubleRedirects` via
`list=querypage`, then `_resolve_chain` walks each redirect (regex-parsing the first
`[[wikilink]]` in the wikitext, capped at `MAX_HOPS`) to find the final non-redirect
target, preserving any `#fragment` from the last hop. Edit summaries are localized per
language via `DOUBLE_REDIRECT_SUMMARY`, falling back to English for unlisted languages.

## Environment

Configuration lives in `.env` (gitignored; see `.env.example` for the template):
`DEFAULT_LANG`, `{LANG}_BOT_USERNAME`/`{LANG}_BOT_PASSWORD` per wiki language,
`USER_AGENT_SPOOF`, `CF_CLEARANCE`.
