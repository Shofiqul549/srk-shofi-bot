import logging
import requests
import time
import random
import string
from requests_oauthlib import OAuth1
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)

TELEGRAM_TOKEN = "8918620366:AAHO8KblMA2-9W7MRT4Pf-ZfHtZpR7uWA8k"
TWITTER_API_KEY       = "GlvUW14Z4KBjuWls3hharj6DI"
TWITTER_API_SECRET    = "sNjeMv8nRBJqnRhRKe3w8hXtLmDoVkIaQAoAesGnVZ50kR0b15"
TWITTER_ACCESS_TOKEN  = "1709573049409032192-WtV8xXsNKsK89N8xu4ztfE0iY5Oorp"
TWITTER_ACCESS_SECRET = "8ZLH56zvUqvNs1JcovqdNHRS5CW91UTZ3TH7uishJxrRF"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

user_urls = {}
used_short_links: set = set()

AUTH = OAuth1(TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)


def random_suffix(length=8) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def make_unique_url(base_url: str) -> str:
    suffix = random_suffix(8)
    return f"{base_url}&_t={suffix}" if "?" in base_url else f"{base_url}?_t={suffix}"


def post_tweet_get_tco(url: str) -> str | None:
    try:
        response = requests.post(
            "https://api.twitter.com/2/tweets",
            auth=AUTH,
            json={"text": url},
            timeout=15
        )
        logger.info(f"Status: {response.status_code}, Body: {response.text[:400]}")

        if response.status_code != 201:
            return None

        resp_json = response.json()
        tweet_id = resp_json.get("data", {}).get("id")
        tweet_text = resp_json.get("data", {}).get("text", "")

        # tweet text এ t.co আছে কিনা চেক
        for word in tweet_text.split():
            if word.startswith("https://t.co/"):
                logger.info(f"t.co found in text: {word}")
                return word

        # না থাকলে entities দিয়ে GET করো
        if tweet_id:
            time.sleep(1.5)
            detail = requests.get(
                f"https://api.twitter.com/2/tweets/{tweet_id}",
                auth=AUTH,
                params={"tweet.fields": "entities"},
                timeout=10
            )
            logger.info(f"Detail: {detail.status_code}, {detail.text[:400]}")
            if detail.status_code == 200:
                entities = detail.json().get("data", {}).get("entities", {})
                urls = entities.get("urls", [])
                if urls:
                    tco = urls[0].get("url")
                    logger.info(f"t.co from entities: {tco}")
                    return tco

        logger.error("Could not extract t.co URL")
        return None

    except Exception as e:
        logger.error(f"Exception: {e}")
        return None


def get_unique_tco(base_url: str) -> str | None:
    for _ in range(3):
        unique_url = make_unique_url(base_url)
        tco = post_tweet_get_tco(unique_url)
        if tco and tco not in used_short_links:
            used_short_links.add(tco)
            return tco
        time.sleep(1)
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
        "✅ Twitter t.co দিয়ে শর্ট হবে\n"
        "✅ প্রতিটা লিংক আলাদা (duplicate নেই)\n\n"
        "📌 এখনই লিংক পাঠাও!",
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not is_valid_url(text):
        await update.message.reply_text("⚠️ Valid URL দাও! `https://` দিয়ে শুরু হতে হবে।", parse_mode="Markdown")
        return
    user_urls[update.effective_user.id] = text
    await update.message.reply_text(
        "✅ *লিংক পেয়েছি!*\n\n👇 *কতটা Short লিংক বানাবে?*",
        parse_mode="Markdown", reply_markup=get_count_buttons()
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if not query.data.startswith("count_"):
        return

    count = int(query.data.split("_")[1])
    base_url = user_urls.get(user_id)
    if not base_url:
        await query.edit_message_text("⚠️ আগে একটা লিংক পাঠাও!")
        return

    await query.edit_message_text(f"⏳ *{count}টি t.co লিংক বানানো হচ্ছে...*", parse_mode="Markdown")

    short_links = []
    failed = 0

    for i in range(1, count + 1):
        short = get_unique_tco(base_url)
        if short:
            short_links.append(short)
        else:
            failed += 1
        if i % 5 == 0:
            try:
                await query.edit_message_text(
                    f"⏳ *{i}/{count} টি হয়েছে...*\n✅ {len(short_links)} | ❌ {failed}",
                    parse_mode="Markdown"
                )
            except:
                pass

    if not short_links:
        await query.edit_message_text("❌ কোনো লিংক বানানো যায়নি।\nTwitter API limit হয়েছে, কিছুক্ষণ পর চেষ্টা করো।")
        return

    await query.edit_message_text(
        f"✅ *{len(short_links)}টি t.co লিংক তৈরি হয়েছে!*\n"
        f"{'⚠️ ' + str(failed) + 'টি ব্যর্থ' if failed > 0 else '🎉 সব সফল!'}",
        parse_mode="Markdown"
    )

    for chunk_start in range(0, len(short_links), 20):
        chunk = short_links[chunk_start:chunk_start + 20]
        await update.effective_message.reply_text("\n".join(chunk))
        time.sleep(0.3)

    await update.effective_message.reply_text(
        "🔄 *আরো লিংক বানাতে নতুন লিংক পাঠাও!*",
        parse_mode="Markdown", reply_markup=get_count_buttons()
    )


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")


def main():
    print("🤖 Twitter t.co Bot চালু হচ্ছে...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    print("✅ Bot চালু হয়েছে!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
