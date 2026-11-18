# Good News Telegram Bot

Send `/news` to get up to five uplifting stories from [Positive News](https://www.positive.news/) and [Good News Network](https://www.goodnewsnetwork.org/). Each story includes a headline linked to the original article, a short excerpt when available, the publisher and the publication date.

The bot reads the publishers’ RSS feeds, picks stories from the past seven days, removes duplicate links and sorts the results newest first. If one feed is unavailable, the bot can still use the other.

## Run locally

You need Python 3.10 or newer and a Telegram bot token from [@BotFather](https://t.me/BotFather). The news feeds are public.

Open PowerShell in the folder containing `news.py` and run these commands. Paste the token at the prompt.

```powershell
py -m pip install -r requirements.txt
$env:TELEGRAM_TOKEN = Read-Host "Bot token"
py news.py
```

Open the bot in Telegram and press **Start** for the first roundup. Send `/news` to refresh it or `/help` to see the commands and the current chat’s numeric ID.

## Optional morning digest

The bot can also send a digest to one chat every morning at **08:00 Europe/Rome**, while the Python process is running. It includes up to five stories published since the previous morning’s cutoff and skips days with no stories.

Send `/help` in the destination chat and copy the ID from the reply. Stop the running process with Ctrl+C, then run the following in the same PowerShell window.

```powershell
$env:CHAT_ID = Read-Host "Destination chat ID"
py news.py
```

On a host, set `TELEGRAM_TOKEN` and the optional `CHAT_ID` in the service environment and run `python news.py`. Start the bot in the destination chat before enabling delivery.

## License

MIT
