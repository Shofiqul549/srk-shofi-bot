"""
Twitter t.co URL Shortener Telegram Bot
========================================
- লিংক টুইটারে পোস্ট করে t.co শর্ট লিংক নিয়ে আসে
- প্রতিটা লিংক unique (duplicate আসবে না)
- বাটন UI দিয়ে কতটা লিংক চাই বেছে নেওয়া যাবে
- টুইট পোস্ট করার পর ডিলিট করে দেয় (ট্যুইটার ফিড ক্লিন থাকে)

ইনস্টল:
    pip install python-telegram-bot requests requests-oauthlib

চালাও:
    python twitter_bot.py
"""

import logging
import requests
import time
import random
import string
from requests_oauthlib import OAuth1
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ========== CONFIG ==========
TELEGRAM_TOKEN = "8918620366:AAHO8KblMA2-9W7MRT4Pf-ZfHtZpR7uWA8k"

# Twitter API Keys (SrkShofiBot)
TWITTER_API_KEY        = "MylE4x0SdJKUsMeyGTzjnyrF"
TWITTER_API_SECRET     = "VxVabHfKI07c5lUEE2NH1MKlrWtiFuzTGf1kFaxNcGXppslbG1"
TWITTER_ACCESS_TOKEN   = "1709573049409032192-RXkv8nrK7v3i0NMnD1n7QxHeJj39T9"
TWITTER_ACCESS_SECRET  = "0xSiIhZqpcpUpeI5gHMESd0tx0uiFwuqHyuI2MID37J76"
# ============================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

user_urls = {}

# ট্র্যাক করবে কোন শর্ট লিংকগুলো আগে দেওয়া হয়েছে
used_short_links: set = set()


def random_suffix(length=8) -> str:
    """প্রতিটা URL এ আলাদা suffix যোগ করে unique করতে"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))


def make_unique_url(base_url: str) -> str:
    """একই লিংককে unique বানায় যাতে Twitter আলাদা t.co দেয়"""
    suffix = random_suffix(8)
    if "?" in base_url:
        return f"{base_url}&_t={suffix}"
    else:
        return f"{base_url}?_t={suffix}"


def post_tweet_and_get_tco(url: str) -> tuple[str | None, str | None]:
    """
    Twitter এ tweet করে t.co লিংক নিয়ে আসে।
    Returns: (tco_url, tweet_id) অথবা (None, None) যদি ব্যর্থ হয়
    """
    auth = OAuth1(
        TWITTER_API_KEY,
        TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN,
        TWITTER_ACCESS_SECRET
    )

    # Tweet পোস্ট করো
    tweet_url = "https://api.twitter.com/2/tweets"
    payload = {"text": url}

    try:
        response = requests.post(tweet_url, auth=auth, json=payload, timeout=15)
        if response.status_code != 201:
            logger.error(f"Tweet post failed: {response.status_code} {response.text}")
            return None, None

        tweet_data = response.json()
        tweet_id = tweet_data.get("data", {}).get("id")
        if not tweet_id:
            return None, None

        # Tweet এর বিস্তারিত নিয়ে t.co URL বের করো
        time.sleep(1.5)  # Twitter কে process করার সময় দাও

        detail_url = f"https://api.twitter.com/2/tweets/{tweet_id}"
        params = {"tweet.fields": "entities"}
        detail_resp = requests.get(detail_url, auth=auth, params=params, timeout=10)

        tco_url = None
        if detail_resp.status_code == 200:
            detail_data = detail_resp.json()
            entities = detail_data.get("data", {}).get("entities", {})
            urls = entities.get("urls", [])
            if urls:
                tco_url = urls[0].get("url")  # t.co লিংক

        return tco_url, tweet_id

    except Exception as e:
        logger.error(f"Error posting tweet: {e}")
        return None, None


def delete_tweet(tweet_id: str):
    """Tweet ডিলিট করে দেয় যাতে ফিড ক্লিন থাকে"""
    auth = OAuth1(
        TWITTER_API_KEY,
        TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN,
        TWITTER_ACCESS_SECRET
    )
    try:
        requests.delete(
            f"https://api.twitter.com/2/tweets/{tweet_id}",
            auth=auth,
            timeout=10
        )
    except Exception as e:
        logger.error(f"Delete tweet error: {e}")


def get_unique_tco(base_url: str, max_attempts: int = 5) -> str | None:
    """
    Duplicate না হওয়া পর্যন্ত চেষ্টা করে।
    প্রতিবার আলাদা unique suffix দেয়।
    """
    for attempt in range(max_attempts):
        unique_url = make_unique_url(base_url)
        tco_url, tweet_id = post_tweet_and_get_tco(unique_url)

        if tco_url:
            if tco_url not in used_short_links:
                used_short_links.add(tco_url)
                # Tweet ডিলিট করো (ফিড ক্লিন রাখতে)
                if tweet_id:
                    delete_tweet(tweet_id)
                return tco_url
            else:
                # Duplicate হলে tweet ডিলিট করে আবার চেষ্টা
                if tweet_id:
                    delete_tweet(tweet_id)
                logger.info(f"Duplicate found, retrying... (attempt {attempt+1})")
        else:
            # Tweet ব্যর্থ হলে একটু অপেক্ষা করো
            time.sleep(2)

    return None


def is_valid_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")


def get_count_buttons():
    keyboard = [
        [
            InlineKeyboardButton("🔟 ১০টা", callback_data="count_10"),
            InlineKeyboardButton("2️⃣0️⃣ ২০টা", callback_data="count_20"),
            InlineKeyboardButton("3️⃣0️⃣ ৩০টা", callback_data="count_30"),
        ],
        [
            InlineKeyboardButton("5️⃣0️⃣ ৫০টা", callback_data="count_50"),
            InlineKeyboardButton("7️⃣5️⃣ ৭৫টা", callback_data="count_75"),
            InlineKeyboardButton("💯 ১০০টা", callback_data="count_100"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ *Twitter t.co Shortener Bot* ⚡\n\n"
        "🔗 লিংক পাঠাও → কতটা চাও বেছে নাও → ব্যস!\n\n"
        "✅ *Twitter t.co দিয়ে শর্ট হবে*\n"
        "✅ প্রতিটা লিংক সম্পূর্ণ আলাদা (duplicate নেই)\n"
        "✅ Tweet অটো ডিলিট হয়ে যাবে\n\n"
        "📌 এখনই যেকোনো লিংক পাঠাও!",
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not is_valid_url(text):
        await update.message.reply_text(
            "⚠️ *Valid URL দাও!*\n`http://` বা `https://` দিয়ে শুরু হতে হবে।",
            parse_mode="Markdown"
        )
        return

    user_id = update.effective_user.id
    user_urls[user_id] = text

    await update.message.reply_text(
        "✅ *লিংক পেয়েছি!*\n\n"
        "👇 *কতটা Short লিংক বানাবে?*",
        parse_mode="Markdown",
        reply_markup=get_count_buttons()
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data

    if not data.startswith("count_"):
        return

    count = int(data.split("_")[1])
    base_url = user_urls.get(user_id)

    if not base_url:
        await query.edit_message_text("⚠️ আগে একটা লিংক পাঠাও!")
        return

    await query.edit_message_text(
        f"⏳ *{count}টি t.co লিংক বানানো হচ্ছে...*\n"
        f"Twitter API call করতে একটু সময় লাগবে 🙏",
        parse_mode="Markdown"
    )

    short_links = []
    failed = 0

    for i in range(1, count + 1):
        short = get_unique_tco(base_url)
        if short:
            short_links.append(short)
        else:
            failed += 1

        # প্রতি ৫টায় progress দেখাও
        if i % 5 == 0:
            try:
                await query.edit_message_text(
                    f"⏳ *{i}/{count} টি হয়েছে...*\n✅ সফল: {len(short_links)} | ❌ ব্যর্থ: {failed}",
                    parse_mode="Markdown"
                )
            except:
                pass

        # Twitter rate limit এড়াতে একটু বিরতি
        time.sleep(1)

    if not short_links:
        await query.edit_message_text(
            "❌ কোনো লিংক বানানো যায়নি।\n"
            "Twitter API limit হয়ে গেছে, কিছুক্ষণ পর আবার চেষ্টা করো।"
        )
        return

    await query.edit_message_text(
        f"✅ *{len(short_links)}টি t.co লিংক তৈরি হয়েছে!*\n"
        f"{'⚠️ ' + str(failed) + 'টি ব্যর্থ' if failed > 0 else '🎉 সব সফল!'}",
        parse_mode="Markdown"
    )

    # লিংকগুলো পাঠাও (২০টা করে chunk)
    chunk_size = 20
    for chunk_start in range(0, len(short_links), chunk_size):
        chunk = short_links[chunk_start:chunk_start + chunk_size]
        await update.effective_message.reply_text("\n".join(chunk))
        time.sleep(0.5)

    await update.effective_message.reply_text(
        "🔄 *আরো লিংক বানাতে নতুন লিংক পাঠাও!*",
        parse_mode="Markdown",
        reply_markup=get_count_buttons()
    )


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")


def main():
    print("🤖 Twitter t.co Shortener Bot চালু হচ্ছে...")
    print(f"✅ Twitter API connected")
    print(f"✅ Duplicate protection চালু")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    print("✅ Bot চালু হয়েছে!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
