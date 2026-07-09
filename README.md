# wikifur-bot

Client-side maintenance bot for [pt.wikifur.com](https://pt.wikifur.com) and
[en.wikifur.com](https://en.wikifur.com), using the MediaWiki Action API via
[mwclient](https://mwclient.readthedocs.io/). No server access required — it
acts as a regular (bot-flagged) user account.

Wikis live at `{lang}.wikifur.com/w/` (hardcoded). Every command takes
`--lang` (e.g. `--lang en`), defaulting to `DEFAULT_LANG` from `.env`.
Credentials are per language (`PT_BOT_USERNAME`, `EN_BOT_USERNAME`, …);
the Cloudflare cookie and User-Agent are shared, since the cookie is set
on the parent `.wikifur.com` domain. Both wikis currently run the same
MediaWiki version, but don't assume that stays true — `check` prints each
wiki's version.

## Setup

1. **Install deps:** `uv sync`
2. **Bot account:** the wikis run MediaWiki **1.23.16**, which predates
   `Special:BotPasswords` (1.27), so create a dedicated account for the bot
   (e.g. `LizBot`) via `Especial:Criar_conta` and use its normal credentials
   — mwclient logs in through the legacy `action=login` handshake. Never put
   your main admin password in `.env`. When adding new API calls, mind the
   1.23 limits: no `meta=tokens` (1.24+), no `formatversion=2` (1.25+);
   mwclient's built-ins handle this automatically.
3. **Config:** `cp .env.example .env` and fill it in (see the Cloudflare note below).
4. **Bot flag (recommended):** ask a bureaucrat to add the account to the `bot`
   group so maintenance edits don't flood Recent Changes.

## Cloudflare

Both wikis run behind a Cloudflare JS challenge that 403s all API clients.
Two ways forward:

- **Proper fix:** ask whoever runs WikiFur's Cloudflare account to add a WAF
  *skip* rule for `*/api.php` (or for the bot's User-Agent / your IP). This is
  the standard thing wikis behind Cloudflare do to keep bots and apps working.
- **Workaround:** copy your browser's `cf_clearance` cookie into `CF_CLEARANCE`
  and its exact User-Agent (`navigator.userAgent` in the DevTools console) into
  `USER_AGENT_SPOOF`. One cookie covers all language subdomains, but it expires
  and must be re-copied when the bot starts getting 403s again.

## Usage

```sh
uv run bot check              # connectivity + MediaWiki version (no login)
uv run bot whoami             # verify bot login and rights
uv run bot recent -n 20       # watch recent changes
uv run bot double-redirects   # list double redirects
uv run bot page "Some Title"  # show a page's wikitext + basic info
uv run bot page "Some Title" --raw  # wikitext only, no metadata header
uv run bot edit "Some Title" --text "new wikitext" --summary "why"   # preview a diff (dry run)
uv run bot edit "Some Title" --file new.wikitext --summary "why" --apply  # save it for real
uv run bot check --lang en    # any command, against en.wikifur.com
```

`edit` reads the new text from `--text`, `--file`, or stdin (in that order of
precedence), always shows a unified diff against the current text, and only
saves when `--apply` is given — `--summary` is then required.

Write tasks (fixing redirects, category renames, template migrations, …) get
added as new subcommands in `wikifur_bot/cli.py` — keep them read-only-preview
by default and add a `--apply` flag for the real run.
