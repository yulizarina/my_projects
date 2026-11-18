# Italy & Rome News in English

A Python Telegram bot for reading Italian national and Rome news in English. Each item is a single clickable, machine-translated headline. Tapping it opens the full article on the publisher’s website in Italian. Telegram link previews are disabled.

## Read the news

| Telegram command | What you get |
| --- | --- |
| `/start` or `/news` | National and Rome headlines together, newest first |
| `/italy` | National coverage from the Italian editions and domestic news desks below |
| `/rome` | Local coverage from Rome and the surrounding area |
| `/more` | The next 8 headlines from the same list |
| `/help` | Commands and the current chat’s numeric ID |

The bot includes every topic carried by its feeds. It merges the available articles, removes duplicate links and keeps the full list while you page through it. Starting a new edition refreshes the list for that chat. After a restart, send a news command to load a fresh edition.

**National sources** include Il Post’s Italia section, Euronews articles tagged Italia, and ANSA’s Cronaca and Politica desks. **Rome sources** are RomaToday and Il Messaggero’s Roma section. Publishers decide which articles appear in their rolling feeds. Feed addresses are listed in `feeds.py`.

## Run on Windows

1. In Telegram, send `/newbot` to [@BotFather](https://t.me/BotFather). Choose a name and an available username for this bot. Keep the token for the PowerShell prompt.
2. Open PowerShell in the folder containing `bot.py`. With 64-bit Python 3.12 installed, run the commands below.
3. Open the bot in Telegram and press **Start**. Keep the Python process running while using the bot.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:ITALY_ROME_BOT_TOKEN = Read-Host "Paste the Telegram token for Italy and Rome news"
.\.venv\Scripts\python.exe bot.py
```

The first run downloads about **238 MB** of Italian-to-English model files. Subsequent runs use the local copy. Translation runs on the CPU and requires no translation API key. Proper names and idioms can be translated literally.

## Optional morning edition

To receive a combined edition at **08:00 Europe/Rome**, send `/help` in the destination chat and copy the chat ID. Stop the running bot with **Ctrl+C**. In the same PowerShell window, run the commands below and paste the ID when prompted.

```powershell
$env:ITALY_ROME_CHAT_ID = Read-Host "Destination chat ID"
.\.venv\Scripts\python.exe bot.py
```

While the bot is running, the morning edition uses headlines still available in the feeds with publication times between yesterday’s and today’s 08:00 cutoffs. It sends the first page if there are new items. Use `/more` for the rest.

## Translation model

Helsinki-NLP trained the Italian-to-English OPUS-MT model. This project uses VoragoStudios’ CTranslate2 conversion with SentencePiece tokenization. The model downloads separately when the bot starts. [Original model](https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-it-en) · [Converted model](https://huggingface.co/VoragoStudios/gct-opus-mt-tc-big-it-en-ct2)
