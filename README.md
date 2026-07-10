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
uv run bot sync-events        # preview syncing pt's Próximos eventos from en's Upcoming events
uv run bot sync-events --apply --summary "why"  # save it for real
uv run bot serve-cf            # local endpoint for the CF-clearance browser extension (see below)
```
