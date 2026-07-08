"""Command-line interface for the WikiFur maintenance bot.

Usage (all commands take --lang, e.g. --lang en; default from DEFAULT_LANG):
    uv run bot check                        # connectivity + site info, no login
    uv run bot whoami                       # login and show identity
    uv run bot recent [-n N]                # last N recent changes (default 10)
    uv run bot double-redirects [--apply]   # preview/fix double redirects
"""

from __future__ import annotations

import argparse
import re
import sys
import time

from wikifur_bot.client import DEFAULT_LANG, connect


def cmd_check(args: argparse.Namespace) -> None:
    site = connect(args.lang, login=False)
    info = site.site
    print(f"Connected to {info.get('sitename')} ({site.host})")
    print(f"  MediaWiki: {info.get('generator')}")
    print(f"  Language:  {info.get('lang')}")
    print(f"  Base URL:  {info.get('base')}")


def cmd_whoami(args: argparse.Namespace) -> None:
    site = connect(args.lang, login=True)
    result = site.api("query", meta="userinfo", uiprop="groups|rights")
    ui = result["query"]["userinfo"]
    print(f"Logged in as: {ui['name']} (id {ui['id']})")
    print(f"  Groups: {', '.join(ui.get('groups', []))}")
    has_bot = "bot" in ui.get("rights", [])
    print(f"  Bot right: {'yes' if has_bot else 'no (edits will show in RC unflagged)'}")


def cmd_recent(args: argparse.Namespace) -> None:
    site = connect(args.lang, login=False)
    changes = site.recentchanges(prop="title|timestamp|user|comment", max_items=args.limit)
    for change in changes:
        when = time.strftime("%Y-%m-%d %H:%M", change["timestamp"])
        print(f"{when}  {change.get('user', '?'):<20} {change.get('title', '')}  ({change.get('comment', '')})")


# In a page the API flags as a redirect, the target is the first wikilink.
REDIRECT_LINK = re.compile(r"\[\[([^\[\]]+)\]\]")
MAX_HOPS = 10

# Keyed by wiki language; languages not listed fall back to English.
DOUBLE_REDIRECT_SUMMARY = {
    "pt": "Bot: corrigindo redirecionamento duplo para [[{target}]]",
    "en": "Bot: fixing double redirect to [[{target}]]",
}


def _parse_target(text: str) -> tuple[re.Match | None, str, str]:
    """Return (link match, target title, fragment) of a redirect's wikitext."""
    m = REDIRECT_LINK.search(text)
    if not m:
        return None, "", ""
    inner = m.group(1).split("|")[0]
    title, _, fragment = inner.partition("#")
    return m, title.strip(), fragment.strip()


def _resolve_chain(site, title: str) -> tuple[list[str], str, str]:
    """Follow redirects from `title` to the final non-redirect page.

    Returns (chain of titles, final fragment, problem). `problem` is a
    human-readable reason to skip this page, or "" if the chain is clean.
    """
    chain = [title]
    fragment = ""
    seen = {site.pages[title].name}
    current = title
    for _ in range(MAX_HOPS):
        page = site.pages[current]
        if not page.redirect:
            if not page.exists:
                return chain, fragment, f"final target [[{current}]] does not exist"
            return chain, fragment, ""
        m, target, frag = _parse_target(page.text())
        if m is None:
            return chain, fragment, f"cannot parse redirect text of [[{current}]]"
        if frag:
            fragment = frag
        normalized = site.pages[target].name
        if normalized in seen:
            return chain + [target], fragment, "redirect loop"
        seen.add(normalized)
        chain.append(target)
        current = target
    return chain, fragment, f"chain longer than {MAX_HOPS} hops"


def cmd_double_redirects(args: argparse.Namespace) -> None:
    site = connect(args.lang, login=args.apply)
    result = site.api("query", list="querypage", qppage="DoubleRedirects", qplimit="max")
    rows = result["query"]["querypage"]["results"]
    if not rows:
        print("No double redirects. \\o/")
        return

    fixed = skipped = 0
    for row in rows:
        title = row["title"]
        page = site.pages[title]
        if not page.redirect:
            print(f"SKIP  {title}: no longer a redirect (stale report)")
            skipped += 1
            continue

        chain, fragment, problem = _resolve_chain(site, title)
        if problem:
            print(f"SKIP  {title}: {problem}  ({' -> '.join(chain)})")
            skipped += 1
            continue

        final = chain[-1]
        if len(chain) <= 2:
            print(f"SKIP  {title}: already single-hop (stale report)")
            skipped += 1
            continue

        new_target = f"{final}#{fragment}" if fragment else final
        print(f"{'FIX ' if args.apply else 'PLAN'}  {' -> '.join(chain)}")
        print(f"      => #REDIRECT [[{new_target}]]")
        if args.apply:
            text = page.text()
            m, _, _ = _parse_target(text)
            new_text = text[: m.start(1)] + new_target + text[m.end(1) :]
            summary = DOUBLE_REDIRECT_SUMMARY.get(args.lang, DOUBLE_REDIRECT_SUMMARY["en"]).format(target=new_target)
            page.save(new_text, summary=summary, bot=True)
            time.sleep(2)
        fixed += 1

    verb = "fixed" if args.apply else "to fix"
    print(f"\n{fixed} {verb}, {skipped} skipped.")
    if not args.apply and fixed:
        print("Dry run — rerun with --apply to save the edits.")


def main() -> None:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--lang",
        "-l",
        default=DEFAULT_LANG,
        metavar="LANG",
        help=f"WikiFur language subdomain to operate on (default: {DEFAULT_LANG})",
    )

    parser = argparse.ArgumentParser(prog="bot", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", parents=[common], help="connectivity + site info (no login)")
    sub.add_parser("whoami", parents=[common], help="log in and show bot identity/rights")

    p_recent = sub.add_parser("recent", parents=[common], help="show recent changes")
    p_recent.add_argument("-n", "--limit", type=int, default=10)

    p_dr = sub.add_parser("double-redirects", parents=[common], help="preview/fix double redirects")
    p_dr.add_argument("--apply", action="store_true", help="save the edits (default: dry run)")

    args = parser.parse_args()
    handlers = {
        "check": cmd_check,
        "whoami": cmd_whoami,
        "recent": cmd_recent,
        "double-redirects": cmd_double_redirects,
    }
    try:
        handlers[args.command](args)
    except Exception as exc:  # surface Cloudflare blocks with a hint
        text = str(exc)
        if "403" in text or "Just a moment" in text or "cloudflare" in text.lower():
            sys.exit(
                f"Blocked by Cloudflare ({exc}).\n"
                "Refresh CF_CLEARANCE in .env from your browser (see README), and "
                "make sure USER_AGENT_SPOOF matches that browser exactly."
            )
        raise


if __name__ == "__main__":
    main()
