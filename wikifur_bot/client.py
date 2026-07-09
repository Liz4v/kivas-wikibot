"""Connection handling for the WikiFur bot.

Wikis live at {lang}.wikifur.com with script path /w/ (hardcoded). The
language is picked per command with --lang, defaulting to DEFAULT_LANG
from .env. Credentials are per language ({LANG}_BOT_USERNAME/_PASSWORD).

The WikiFur wikis sit behind Cloudflare with a JS challenge that blocks
non-browser clients. Until the WikiFur admins add a WAF exception for the
bot, requests must carry a valid ``cf_clearance`` cookie copied from a
browser session. The cookie is set on the parent .wikifur.com domain, so
one CF_CLEARANCE covers every language subdomain — but it is bound to the
exact User-Agent (and IP) of the browser that solved the challenge, so
USER_AGENT_SPOOF must match that browser character-for-character.
"""

import os
import subprocess

import mwclient
import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_LANG = os.getenv("DEFAULT_LANG", "pt")
SCRIPT_PATH = "/w/"
USER_AGENT = os.getenv("USER_AGENT_SPOOF", "")


def host_for(lang: str) -> str:
    return f"{lang}.wikifur.com"


def get_user_agent():
    global USER_AGENT

    if not USER_AGENT:
        try:
            git_short_commit_id = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=os.path.dirname(__file__),
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            git_short_commit_id = "main"
        mwclient_version = mwclient.__version__
        parts = (
            f"Kiva.gay/wikibot/{git_short_commit_id}",
            f"mwclient/{mwclient_version}",
            "(+https://pt.wikifur.com/wiki/User:Kiva,",
            "https://kiva.gay)",
            "botid/3c8ff76b-1a8e-57d3-84bb-f1f93bc6d577",  # ns:URL https://kiva.gay/wikibot
        )
        USER_AGENT = " ".join(parts)

    return USER_AGENT


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = get_user_agent()
    cf_clearance = os.getenv("CF_CLEARANCE")
    if cf_clearance:
        session.cookies.set("cf_clearance", cf_clearance, domain=".wikifur.com")
    return session


def connect(lang: str = DEFAULT_LANG, login: bool = True) -> mwclient.Site:
    """Return an mwclient Site for {lang}.wikifur.com, optionally logged in."""
    site = mwclient.Site(
        host_for(lang),
        path=SCRIPT_PATH,
        pool=build_session(),
        clients_useragent=get_user_agent(),
    )
    if login:
        username = os.getenv(f"{lang.upper()}_BOT_USERNAME")
        password = os.getenv(f"{lang.upper()}_BOT_PASSWORD")
        if not (username and password):
            raise SystemExit(
                f"{lang.upper()}_BOT_USERNAME / {lang.upper()}_BOT_PASSWORD not set "
                "in .env — these wikis have no BotPasswords, so use a dedicated bot "
                "account's normal credentials."
            )
        site.login(username, password)
    return site
