import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import asyncio
import schedule

# Configurations (preserved as provided)
# Telegram bot token and chat ID
TELEGRAM_TOKEN = '7215307306:AAHmG0zVqNORgY1UXgfKESVBAr2NFzjHBHE'
CHAT_ID = '1958316281'

# NewsAPI token
NEWS_API_KEY = '57d9b7b034884cd7846407ff423f0379'  # Replace with your NewsAPI key
NEWS_URL = f'https://newsapi.org/v2/everything?q=visa+immigration&apiKey={NEWS_API_KEY}'
keywords = ["visa", "immigration", "policy", "residency", "work permit", "golden visa", "citizenship", "green card", "opportunity card", "chancenkarte"]



# Date one week ago
one_week_ago = (datetime.now() - timedelta(days=7)).isoformat()

def fetch_news():
    response = requests.get(NEWS_URL)

    if response.status_code != 200:
        print(f"Failed to fetch news. Status code: {response.status_code}")
        return []

    articles = response.json().get('articles', [])
    matched_articles = []

    for article in articles:
        # Filter by publication date within the last week
        published_at = article.get('publishedAt')
        if not published_at or published_at < one_week_ago:
            continue

        # Check if any keyword is in the title or description
        title = article.get('title', '').lower()
        description = article.get('description', '').lower()
        if any(keyword in title or keyword in description for keyword in keywords):
            # Extract and format the date of the article
            date_published = datetime.fromisoformat(published_at[:-1]).strftime('%Y-%m-%d')
            matched_articles.append({
                'description': article.get('description'),
                'url': article.get('url'),
                'date': date_published
            })

    return matched_articles

# Function to send news articles to a specific chat ID
async def send_news(chat_id, context, articles):
    for article in articles:
        message = (
            f"{article['description']}\n"
            f"Published on: {article['date']}\n"
            f"Read more: {article['url']}"
        )
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")

# Handler function for /start command
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Hi! Here are the latest immigration and visa news updates.")

    # Fetch the latest news and get the last 5 articles
    news_articles = fetch_news()[:5]  # Limit to the last 5 articles

    # Send the articles to the user
    if news_articles:
        await send_news(update.effective_chat.id, context, news_articles)
    else:
        await update.message.reply_text("No new articles found.")

def main():
    # Set up the bot application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add the /start command handler
    application.add_handler(CommandHandler("start", start))

    # Schedule news checks
    schedule.every().day.at("08:00").do(lambda: asyncio.run(scheduled_news_check(application)))
    # Run the bot
    application.run_polling()

    # Schedule loop to run alongside bot polling
    while True:
        schedule.run_pending()
        time.sleep(60)

# Start the bot
if __name__ == "__main__":
    main()
