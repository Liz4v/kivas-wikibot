# wikifur-bot

Client-side maintenance bot for [pt.wikifur.com](https://pt.wikifur.com) and
[en.wikifur.com](https://en.wikifur.com), using the MediaWiki Action API via
[mwclient](https://mwclient.readthedocs.io/).

This is just for my own use and is public for transparency.

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
