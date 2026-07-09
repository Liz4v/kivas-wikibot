import argparse
import difflib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from wikifur_bot.client import connect

# en.wikifur.com's Template:Upcoming events is the actively-maintained source;
# pt's Predefinição:Próximos eventos mirrors it but also carries Brazil-only
# events, interleaved by pt editors at their correct chronological spot. A
# straight overwrite from en would clobber those, so this does a 3-way merge
# instead: base = en's own text as of the last successful sync (recorded in
# STATE_PATH), mine = target as-is, theirs = the current source, translated.
# `git merge-file` then merges en's changes (base -> theirs) into the target
# while keeping mine's local insertions in place. Diffing base->theirs stays
# entirely on the en side (same language, same document lineage), so it's a
# small, well-behaved delta no matter how stale the target has gotten — only
# the very first sync (no recorded base yet) falls back to an approximate,
# noisier base.
SYNC_SOURCE_LANG = "en"
SYNC_TEMPLATE_TITLES = {
    "en": "Template:Upcoming events",
    "pt": "Predefinição:Próximos eventos",
}
# pt always uses lowercase month abbreviations, even where the spelling matches en's
# (Jan/Mar/Jun/Jul) — only the case changes for those.
SYNC_MONTH_EN_TO_PT_LOWER = {
    "Jan": "jan",
    "Feb": "fev",
    "Mar": "mar",
    "Apr": "abr",
    "May": "mai",
    "Jun": "jun",
    "Jul": "jul",
    "Aug": "ago",
    "Sep": "set",
    "Oct": "out",
    "Nov": "nov",
    "Dec": "dez",
}
_SYNC_MONTHS_ALT = "|".join(SYNC_MONTH_EN_TO_PT_LOWER)
# Undated placeholders like "Sep 2026?" have no day to reorder around, so they just get
# the month lowercased/translated in place.
SYNC_MONTH_RE = re.compile(rf"\b({_SYNC_MONTHS_ALT})\b(?=\s*[\d?])")
# For dated entries (with an actual day number), pt convention puts the day first,
# lowercased month, e.g. "Feb 5-8" -> "5 a 8 fev", "Jul 29-Aug 2" -> "29 jul a 2 ago".
# Matches a flagdiv's leading date, requiring it to run right up to the `:` that
# separates the date from the event title — that's what keeps this from misfiring on
# incidental month/day mentions elsewhere (e.g. inside the archived-events comment).
SYNC_DATE_RE = re.compile(rf"\b({_SYNC_MONTHS_ALT})\s+(\d{{1,2}})(?:-(?:({_SYNC_MONTHS_ALT})\s+)?(\d{{1,2}}))?(?=:)")
SYNC_TABLE_START = "{| width=100%"


def _reformat_date(m: re.Match) -> str:
    mon1, day1, mon2, day2 = m.groups()
    mon1_pt = SYNC_MONTH_EN_TO_PT_LOWER[mon1]
    if day2 is None:
        return f"{day1} {mon1_pt}"
    if mon2 is None:
        return f"{day1} a {day2} {mon1_pt}"
    return f"{day1} {mon1_pt} a {day2} {SYNC_MONTH_EN_TO_PT_LOWER[mon2]}"


STATE_PATH = Path(__file__).resolve().parent.parent / ".wikifur_bot_sync_state.json"


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def _save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _sync_table_bounds(text: str) -> tuple[int, int]:
    """Return (start, end) indices of the `{| ... |}` event table in a template's wikitext."""
    start = text.index(SYNC_TABLE_START)
    end = text.rindex("|}") + len("|}")
    return start, end


def _strip_bra_lines(table_text: str) -> str:
    """Drop target-only (e.g. Brazil) event lines, approximating the shared base both sides mirror."""
    lines = table_text.split("\n")
    kept = [line for line in lines if not line.strip().startswith("{{flagdiv|bra|")]
    return "\n".join(kept)


def _translate(table_text: str) -> str:
    translated = SYNC_DATE_RE.sub(_reformat_date, table_text)
    translated = SYNC_MONTH_RE.sub(lambda m: SYNC_MONTH_EN_TO_PT_LOWER[m.group(1)], translated)
    return translated.replace("(to be announced)", "(a serem anunciados)")


def _text_at_revision(page, revid: int) -> str:
    """Wikitext of `page` as of a specific past revision id."""
    rev = next(page.revisions(startid=revid, prop="content|ids", slots="main", max_items=1), None)
    if rev is None:
        raise RuntimeError(f"revision {revid} of [[{page.name}]] not found (deleted, or wrong id?)")
    if "slots" in rev:
        return rev["slots"]["main"]["*"]
    return rev["*"]


def _three_way_merge(mine: str, base: str, theirs: str) -> tuple[str, bool]:
    """Merge theirs' changes (relative to base) into mine via `git merge-file`.

    Returns (merged_text, had_conflicts).
    """
    with tempfile.TemporaryDirectory() as tmp:
        mine_path = Path(tmp) / "mine"
        base_path = Path(tmp) / "base"
        theirs_path = Path(tmp) / "theirs"
        mine_path.write_text(mine, encoding="utf-8")
        base_path.write_text(base, encoding="utf-8")
        theirs_path.write_text(theirs, encoding="utf-8")

        result = subprocess.run(
            [
                "git",
                "merge-file",
                "-p",
                "--diff3",
                "-L",
                "pt (atual, com eventos exclusivos)",
                "-L",
                "base (última sincronização)",
                "-L",
                "en (traduzido)",
                str(mine_path),
                str(base_path),
                str(theirs_path),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode < 0:
            raise RuntimeError(f"git merge-file failed: {result.stderr}")
        return result.stdout, result.returncode != 0


def cmd_sync_events(args: argparse.Namespace) -> None:
    if args.lang == SYNC_SOURCE_LANG:
        sys.exit(f"--lang can't be '{SYNC_SOURCE_LANG}' — that's the sync source, not a target.")
    if args.lang not in SYNC_TEMPLATE_TITLES:
        sys.exit(f"No known events template for --lang {args.lang}.")
    target_title = SYNC_TEMPLATE_TITLES[args.lang]
    source_title = SYNC_TEMPLATE_TITLES[SYNC_SOURCE_LANG]

    source_site = connect(SYNC_SOURCE_LANG, login=False)
    target_site = connect(args.lang, login=args.apply)

    source_page = source_site.pages[source_title]
    target_page = target_site.pages[target_title]
    if not source_page.exists:
        sys.exit(f"[[{source_title}]] does not exist on {SYNC_SOURCE_LANG}.wikifur.com")
    if not target_page.exists:
        sys.exit(f"[[{target_title}]] does not exist on {args.lang}.wikifur.com")

    source_text = source_page.text()
    target_text = target_page.text()

    source_start, source_end = _sync_table_bounds(source_text)
    target_start, target_end = _sync_table_bounds(target_text)

    mine = target_text[target_start:target_end]
    theirs = _translate(source_text[source_start:source_end])

    state = _load_state()
    last_revid = state.get(args.lang, {}).get("en_revid")
    if last_revid is None:
        print(
            "No recorded previous sync for this target — using an approximate base "
            "(this run may show more conflicts than usual; future runs won't).\n"
        )
        base = _strip_bra_lines(mine)
    else:
        try:
            base_source_text = _text_at_revision(source_page, last_revid)
            base_start, base_end = _sync_table_bounds(base_source_text)
            base = _translate(base_source_text[base_start:base_end])
        except (ValueError, RuntimeError) as exc:
            print(f"Warning: couldn't load recorded en revision {last_revid} ({exc}); using an approximate base.\n")
            base = _strip_bra_lines(mine)

    merged_body, had_conflicts = _three_way_merge(mine, base, theirs)
    new_text = target_text[:target_start] + merged_body + target_text[target_end:]

    if new_text == target_text:
        print(f"No changes to [[{target_title}]].")
        return

    diff = list(
        difflib.unified_diff(
            target_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"{target_title} (current)",
            tofile=f"{target_title} (synced from {SYNC_SOURCE_LANG}:{source_title})",
        )
    )
    sys.stdout.writelines(diff)

    if had_conflicts:
        print(
            "\nMerge conflicts (marked <<<<<<< / ||||||| / ======= / >>>>>>> above) — "
            "resolve them by hand (e.g. with `bot edit`) before saving."
        )
        if args.apply:
            sys.exit("Refusing to save with unresolved merge conflicts.")
        return

    if args.apply:
        summary = args.summary or f"Bot: sincronizando com {SYNC_SOURCE_LANG}:{source_title}"
        target_page.save(new_text, summary=summary, bot=True)
        state.setdefault(args.lang, {})["en_revid"] = source_page.revision
        _save_state(state)
        print(f"\nSaved [[{target_title}]] (recorded en revision {source_page.revision} as the new sync base).")
    else:
        print("\nDry run — rerun with --apply to save.")
