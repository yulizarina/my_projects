"""A Telegram newsreader for Italy and Rome. Run with python bot.py."""

import asyncio
import logging
import os
from datetime import datetime, time, timedelta
from html import escape

from telegram import BotCommand, LinkPreviewOptions, Update
from telegram.constants import MessageLimit, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from feeds import ROME, FeedsUnavailable, Headline, fetch_headlines
from translation import HeadlineTranslator

PAGE_SIZE = 8
MORNING = time(hour=8, tzinfo=ROME)
COMMANDS = {
    "news": "Read Italy and Rome",
    "italy": "Read national news",
    "rome": "Read local Rome news",
    "more": "Read the next headlines",
    "help": "Show commands and this chat’s ID",
}


def linked_headlines(stories: list[Headline], titles: tuple[str, ...]) -> tuple[str, int]:
    """Return one Telegram message and the number of headlines it contains."""
    lines = []
    used = 0
    limit = int(MessageLimit.MAX_TEXT_LENGTH)
    for story, title in zip(stories, titles, strict=True):
        visible = title.encode("utf-16-le")
        if len(visible) > limit * 2:
            title = visible[: (limit - 1) * 2].decode("utf-16-le", errors="ignore") + "…"
        size = len(title.encode("utf-16-le")) // 2
        if lines and used + 2 + size > limit:
            break
        used += size + (2 if lines else 0)
        lines.append(f'<a href="{escape(story.url, quote=True)}">{escape(title)}</a>')
    return "\n\n".join(lines), len(lines)


async def deliver(context, chat_id: int, stories: list[Headline]):
    page = stories[:PAGE_SIZE]
    translator = context.bot_data["translator"]
    try:
        english = await asyncio.to_thread(translator.translate, tuple(s.title for s in page))
        message, count = linked_headlines(page, english)
    except (RuntimeError, ValueError) as error:
        logging.warning("Translation failed (%s)", type(error).__name__)
        await context.bot.send_message(chat_id, "Translation is unavailable. Send /more to retry.")
        return
    await context.bot.send_message(
        chat_id, message, parse_mode=ParseMode.HTML,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    # Advance only after Telegram accepts the page, so a failed send can be retried.
    context.chat_data["unread"] = stories[count:]


async def show_news(context, chat_id: int, scope: str, *, morning_end: datetime | None = None):
    # The scheduled digest may arrive while the reader is asking for another page.
    async with context.chat_data.setdefault("page_lock", asyncio.Lock()):
        if scope == "more":
            stories = context.chat_data.get("unread", [])
            if not stories:
                await context.bot.send_message(chat_id, "You’re up to date. Send /news, /italy or /rome to refresh.")
                return
        else:
            try:
                stories = await fetch_headlines(scope)
            except FeedsUnavailable:
                if morning_end is None:
                    await context.bot.send_message(chat_id, "The news feeds are unavailable. Please try again shortly.")
                return
            if morning_end is not None:
                since = morning_end - timedelta(days=1)
                stories = [s for s in stories if s.published and since <= s.published < morning_end]
            if not stories:
                if morning_end is None:
                    context.chat_data["unread"] = []
                    await context.bot.send_message(chat_id, "The selected feeds have no headlines yet.")
                return
            context.chat_data["unread"] = stories
        await deliver(context, chat_id, stories)


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    command = update.effective_message.text.split()[0].split("@")[0].removeprefix("/").lower()
    scope = "news" if command == "start" else command
    await show_news(context, update.effective_chat.id, scope)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [f"/{name} — {label}" for name, label in COMMANDS.items() if name != "help"]
    lines.append(f"Chat ID for the optional morning edition: {update.effective_chat.id}")
    await update.effective_message.reply_text("\n".join(lines))


async def morning_news(context: ContextTypes.DEFAULT_TYPE):
    cutoff = datetime.combine(datetime.now(ROME).date(), MORNING)
    await show_news(context, context.job.chat_id, "news", morning_end=cutoff)


async def set_commands(app: Application):
    await app.bot.set_my_commands([BotCommand(name, label) for name, label in COMMANDS.items()])


def main():
    token = os.getenv("ITALY_ROME_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set ITALY_ROME_BOT_TOKEN to the token for this bot.")
    chat_id = os.getenv("ITALY_ROME_CHAT_ID", "").strip()
    try:
        recipient = int(chat_id) if chat_id else None
    except ValueError:
        raise SystemExit("ITALY_ROME_CHAT_ID must be the numeric ID shown by /help.") from None

    app = Application.builder().token(token).post_init(set_commands).build()
    app.bot_data["translator"] = HeadlineTranslator()
    app.add_handler(CommandHandler(["start", "news", "italy", "rome", "more"], news_command))
    app.add_handler(CommandHandler("help", help_command))
    if recipient is not None:
        app.job_queue.run_daily(morning_news, time=MORNING, chat_id=recipient)
    app.run_polling()


if __name__ == "__main__":
    main()
