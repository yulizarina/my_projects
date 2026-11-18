"""Send a roundup of recent good news to a Telegram chat."""

import asyncio
import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import escape, unescape
from textwrap import shorten
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from telegram import Bot, LinkPreviewOptions, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

FEEDS = {
    "Positive News": "https://www.positive.news/feed/",
    "Good News Network": "https://www.goodnewsnetwork.org/category/news/feed/",
}
ROME = ZoneInfo("Europe/Rome")
MORNING = time(hour=8, tzinfo=ROME)
MAX_STORIES = 5


@dataclass(frozen=True)
class Story:
    title: str
    summary: str
    url: str
    publisher: str
    published: datetime


def parse_feed(content: bytes, publisher: str) -> list[Story]:
    channel = ET.fromstring(content).find("channel")
    if channel is None:
        raise ValueError("Expected an RSS channel")

    stories = []
    for item in channel.findall("item"):
        title = unescape(item.findtext("title", "")).strip()
        url = item.findtext("link", "").strip()
        if not title or not url.startswith(("https://", "http://")):
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate", ""))
        except (ValueError, TypeError, OverflowError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)

        # WordPress feeds often append a second paragraph linking back to the post.
        description = BeautifulSoup(item.findtext("description", ""), "html.parser")
        intro = (description.find("p") or description).get_text(" ", strip=True)
        stories.append(Story(title, intro, url, publisher, published))
    return stories


async def fetch_source(
    client: httpx.AsyncClient, publisher: str, url: str
) -> list[Story] | None:
    try:
        response = await client.get(url)
        response.raise_for_status()
        return parse_feed(response.content, publisher)
    except (httpx.HTTPError, ET.ParseError, ValueError) as error:
        logging.warning("Could not read %s (%s)", publisher, type(error).__name__)
        return None


async def fetch_news(since: datetime, until: datetime) -> list[Story] | None:
    async with httpx.AsyncClient(
        timeout=15, follow_redirects=True, headers={"User-Agent": "GoodNewsTelegramBot/1.0"}
    ) as client:
        requests = (fetch_source(client, name, url) for name, url in FEEDS.items())
        batches = await asyncio.gather(*requests)

    available = [batch for batch in batches if batch is not None]
    if not available:
        return None

    by_url: dict[str, Story] = {}
    for batch in available:
        for story in batch:
            if since <= story.published < until:
                by_url.setdefault(story.url, story)
    return sorted(by_url.values(), key=lambda story: story.published, reverse=True)[:MAX_STORIES]


async def send_news(
    bot: Bot, chat_id: int, since: datetime, until: datetime, *, scheduled: bool = False
) -> None:
    stories = await fetch_news(since, until)
    if not stories:
        if not scheduled:
            message = (
                "I couldn’t reach the news sources. Try /news again in a few minutes."
                if stories is None
                else "No new stories this week. Check back with /news."
            )
            await bot.send_message(chat_id=chat_id, text=message)
        return

    edition = "Morning edition" if scheduled else "Latest stories"
    sections = [f"<b>Good News · {edition}</b>"]
    for story in stories:
        title = escape(shorten(story.title, width=140, placeholder="…"))
        summary = escape(shorten(story.summary, width=180, placeholder="…"))
        date = story.published.astimezone(ROME).strftime("%d %b %Y")
        lines = [f'<a href="{escape(story.url, quote=True)}">{title}</a>']
        if summary:
            lines.append(summary)
        lines.append(f"<i>{escape(story.publisher)} · {date}</i>")
        sections.append("\n".join(lines))

    await bot.send_message(
        chat_id=chat_id,
        text="\n\n".join(sections),
        parse_mode=ParseMode.HTML,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


async def latest_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    await send_news(context.bot, update.effective_chat.id, now - timedelta(days=7), now)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Send /news for up to five recent stories from Positive News and Good News Network.\n"
        f"Chat ID for the optional morning digest: {update.effective_chat.id}"
    )


async def morning_news(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(ROME).date()
    end = datetime.combine(today, MORNING)
    start = datetime.combine(today - timedelta(days=1), MORNING)
    await send_news(context.bot, context.job.chat_id, start, end, scheduled=True)


def main():
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set TELEGRAM_TOKEN to the bot token from @BotFather.")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler(["start", "news"], latest_news))
    app.add_handler(CommandHandler("help", help_command))

    chat_id = os.getenv("CHAT_ID", "").strip()
    if chat_id:
        try:
            recipient = int(chat_id)
        except ValueError:
            raise SystemExit("CHAT_ID must be the numeric ID shown by /help.") from None
        app.job_queue.run_daily(morning_news, time=MORNING, chat_id=recipient)
    app.run_polling()


if __name__ == "__main__":
    main()
