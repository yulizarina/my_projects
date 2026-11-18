"""Read Italian publishers' domestic and Rome RSS editions."""

import asyncio
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import httpx

ROME = ZoneInfo("Europe/Rome")
FEEDS = {
    "italy": {
        "Il Post · Italia": "https://www.ilpost.it/italia/feed/",
        "Euronews · Italia": "https://it.euronews.com/rss?level=tag&name=italia",
        "ANSA · Cronaca": "https://www.ansa.it/sito/notizie/cronaca/cronaca_rss.xml",
        "ANSA · Politica": "https://www.ansa.it/sito/notizie/politica/politica_rss.xml",
    },
    "rome": {
        "RomaToday": "https://www.romatoday.it/rss",
        "Il Messaggero · Roma": "https://www.ilmessaggero.it/rss/roma.xml",
    },
}

ITALIAN_MONTHS = dict(zip(
    "gen feb mar apr mag giu lug ago set ott nov dic".split(),
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
))
EARLIEST = datetime.min.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class Headline:
    title: str
    url: str
    published: datetime | None


class FeedsUnavailable(Exception):
    pass


def publication_time(raw: str) -> datetime | None:
    # Some Italian feeds localize the weekday and month in their RSS dates.
    parts = raw.rsplit(",", 1)[-1].split()
    if len(parts) >= 2:
        parts[1] = ITALIAN_MONTHS.get(parts[1].lower(), parts[1])
    try:
        value = parsedate_to_datetime(" ".join(parts))
    except (TypeError, ValueError, OverflowError):
        return None
    return value if value.tzinfo else value.replace(tzinfo=ROME)


def parse_feed(xml: bytes) -> list[Headline]:
    # Il Post sometimes sends a newline before the XML declaration.
    channel = ET.fromstring(xml.lstrip()).find("channel")
    if channel is None:
        raise ValueError("Expected an RSS channel")

    stories = []
    for item in channel.findall("item"):
        title = " ".join(unescape(item.findtext("title", "")).split())
        url = item.findtext("link", "").strip()
        try:
            link = urlsplit(url)
            valid_url = link.scheme in {"http", "https"} and link.hostname
        except ValueError:
            continue
        if title and valid_url:
            stories.append(Headline(title, url, publication_time(item.findtext("pubDate", ""))))
    return stories


def article_key(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (name, value) for name, value in parse_qsl(parts.query, keep_blank_values=True)
        if not name.lower().startswith("utm_") and name.lower() not in {"fbclid", "gclid", "rss"}
    ]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), ""))


async def read_feed(client: httpx.AsyncClient, name: str, url: str) -> list[Headline] | None:
    try:
        response = await client.get(url)
        response.raise_for_status()
        return parse_feed(response.content)
    except (httpx.HTTPError, ET.ParseError, ValueError) as error:
        logging.warning("Feed unavailable: %s (%s)", name, type(error).__name__)
        return None


async def fetch_headlines(scope: str) -> list[Headline]:
    sources = FEEDS["italy"] | FEEDS["rome"] if scope == "news" else FEEDS[scope]
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=15, headers={"User-Agent": "ItalyRomeNewsReader/1.0"}
    ) as client:
        batches = await asyncio.gather(*(read_feed(client, name, url) for name, url in sources.items()))

    available = [batch for batch in batches if batch is not None]
    if not available:
        raise FeedsUnavailable("All selected feeds are unavailable")
    ordered = sorted(
        (story for batch in available for story in batch),
        key=lambda story: story.published or EARLIEST,
        reverse=True,
    )
    unique = {}
    for story in ordered:
        unique.setdefault(article_key(story.url), story)
    return list(unique.values())
