import nest_asyncio
nest_asyncio.apply()
import telegram
from telegram.ext import Updater, CommandHandler
import stripe
import requests
import random
import string
import time
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8071747780:AAF_oRPKCf38r2vBlgGEkPQzfQeFAsN5H0k")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "6972264549").split(",") if id.isdigit()]
BIN_LOOKUP_URL = "https://lookup.binlist.net/"

# Initialize Stripe key
stripe.api_key = os.getenv("STRIPE_API_KEY")

# Luhn Algorithm
def luhn_checksum(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10

def is_luhn_valid(card_number):
    return luhn_checksum(card_number) == 0

def generate_card_number(bin_prefix, length=16):
    if not bin_prefix.isdigit() or len(bin_prefix) != 6:
        logger.error(f"Invalid BIN prefix: {bin_prefix}")
        return None
    card_number = bin_prefix + ''.join(random.choice(string.digits) for _ in range(length - len(bin_prefix) - 1))
    for i in range(10):
        candidate = card_number + str(i)
        if is_luhn_valid(candidate):
            logger.debug(f"Generated card number: {candidate}")
            return candidate
    logger.error(f"Failed to generate valid card for BIN: {bin_prefix}")
    return None

# BIN Lookup
def get_bin_info(card_number):
    try:
        bin_number = card_number[:6]
        response = requests.get(f"{BIN_LOOKUP_URL}{bin_number}", headers={"Accept-Version": "3"}, timeout=5)
        response.raise_for_status()
        data = response.json()
        return {
            "bank": data.get("bank", {}).get("name", "Unknown"),
            "brand": data.get("brand", "Unknown"),
            "type": data.get("type", "Unknown"),
            "country": data.get("country", {}).get("name", "Unknown")
        }
    except requests.RequestException as e:
        logger.error(f"BIN lookup failed: {str(e)}")
        return {"error": str(e)}

# Stripe Card Validation
def validate_card(card_number, exp_month, exp_year, cvc):
    try:
        if len(card_number) != 16:
            logger.warning(f"Invalid card length: {card_number}")
            return {"status": "Dead", "error": "Card number must be 16 digits"}
        payment_method = stripe.PaymentMethod.create(
            type="card",
            card={
                "number": card_number,
                "exp_month": exp_month,
                "exp_year": exp_year,
                "cvc": cvc,
            },
        )
        return {"status": "Live", "payment_method_id": payment_method.id}
    except (stripe.error.CardError, stripe.error.RateLimitError, stripe.error.InvalidRequestError,
            stripe.error.AuthenticationError, stripe.error.APIConnectionError) as e:
        return {"status": "Dead", "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in validate_card: {str(e)}")
        return {"status": "Dead", "error": "Unknown error"}

# Telegram Handlers
def start(update, context):
    user = update.effective_user
    welcome_message = (
        f"👋 *Welcome, {user.first_name}!* 👋\n"
        "This is a card validation and generation bot for educational purposes.\n"
        "Join our channel: @DarkDorking for updates!\n\n"
        "🔍 *Commands:*\n"
        "/chk `card_number|exp_month|exp_year|cvc` - Validate a card\n"
        "/gen `bin` - Generate 15 cards with given BIN\n"
        "Reply /chk to a /gen message to check all generated cards\n"
        "/addsk `secret_key` - Update Stripe key (admin only)\n"
        "/removesk - Remove Stripe key (admin only)"
    )
    update.message.reply_text(welcome_message, parse_mode="Markdown")

def add_sk(update, context):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        logger.info(f"Unauthorized /addsk attempt by user {user_id}")
        update.message.reply_text(
            "🚫 You are not authorized to use this command!",
            parse_mode="Markdown"
        )
        return

    try:
        command = update.message.text.split(" ", 1)
        if len(command) < 2:
            update.message.reply_text(
                "⚠️ Usage: /addsk `secret_key`",
                parse_mode="Markdown"
            )
            return

        new_sk = command[1].strip()
        if not new_sk.startswith("sk_"):
            update.message.reply_text(
                "⚠️ Invalid Stripe key format! Must start with 'sk_'.",
                parse_mode="Markdown"
            )
            return

        stripe.api_key = new_sk
        logger.info(f"Stripe key updated by user {user_id}")
        update.message.reply_text(
            "✅ Stripe Secret Key updated successfully! Note: Set STRIPE_API_KEY in Heroku config to persist across restarts.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in add_sk: {str(e)}")
        update.message.reply_text(
            f"⚠️ Error updating Stripe key: {str(e)}",
            parse_mode="Markdown"
        )

def remove_sk_command(update, context):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        logger.info(f"Unauthorized /removesk attempt by user {user_id}")
        update.message.reply_text(
            "🚫 You are not authorized to use this command!",
            parse_mode="Markdown"
        )
        return

    try:
        stripe.api_key = None
        logger.info(f"Stripe key removed by user {user_id}")
        update.message.reply_text(
            "✅ Stripe Secret Key removed successfully!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in remove_sk: {str(e)}")
        update.message.reply_text(
            f"⚠️ Error: {str(e)}",
            parse_mode="Markdown"
        )

def generate_cards(update, context):
    if not stripe.api_key:
        logger.warning("Stripe key not set for /gen")
        update.message.reply_text(
            "⚠️ Stripe Secret Key is not set. Please contact @DarkDorking for support.",
            parse_mode="Markdown"
        )
        return

    try:
        command = update.message.text.split(" ", 1)
        if len(command) < 2:
            update.message.reply_text("⚠️ Usage: /gen `bin`", parse_mode="Markdown")
            return

        bin_prefix = command[1].strip()
        if not bin_prefix.isdigit() or len(bin_prefix) != 6:
            update.message.reply_text("⚠️ BIN must be exactly 6 digits!", parse_mode="Markdown")
            return

        response = f"🛠 *Generated Cards for /gen {bin_prefix}* 🛠\n\n"
        cards = []
        for _ in range(15):
            card_number = generate_card_number(bin_prefix)
            if card_number and len(card_number) == 16:
                exp_month = random.randint(1, 12)
                exp_year = random.randint(2025, 2030)
                cvc = ''.join(random.choice(string.digits) for _ in range(3))
                response += f"💳 {card_number} | {exp_month:02d} | {exp_year} | {cvc}\n"
                cards.append({"number": card_number, "exp_month": exp_month, "exp_year": exp_year, "cvc": cvc})
            else:
                response += "❌ Failed to generate a valid card\n"
                logger.warning(f"Failed to generate card for BIN: {bin_prefix}")

        if not cards:
            update.message.reply_text(
                "⚠️ No valid cards could be generated!",
                parse_mode="Markdown"
            )
            return

        bin_info = get_bin_info(bin_prefix)
        response += "\n🏦 *BIN Info*:\n"
        if "error" in bin_info:
            response += f"❌ *Error*: {bin_info['error']}\n"
        else:
            response += f"🏛 *Bank*: {bin_info['bank']}\n"
            response += f"💳 *Brand*: {bin_info['brand']}\n"
            response += f"📋 *Type*: {bin_info['type']}\n"
            response += f"🌍 *Country*: {bin_info['country']}\n"

        response += "\nℹ️ Reply with /chk to validate all generated cards!"
        logger.info(f"Generated {len(cards)} cards for BIN: {bin_prefix}")
        update.message.reply_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in generate_cards: {str(e)}")
        update.message.reply_text(f"⚠️ Error: {str(e)}", parse_mode="Markdown")

def check_card(update, context):
    logger.info(f"Received /chk command from user {update.effective_user.id}")
    if not stripe.api_key:
        logger.warning("Stripe key not set for /chk")
        update.message.reply_text(
            "⚠️ Stripe Secret Key is not set. Please contact @DarkDorking for support.",
            parse_mode="Markdown"
        )
        return

    try:
        if update.message.reply_to_message:
            logger.info(f"Reply detected. Replied message text: {update.message.reply_to_message.text[:100]}...")
            original_message = update.message.reply_to_message.text
            if "Generated Cards" in original_message:
                logger.info("Processing as reply to /gen message")
                lines = original_message.split("\n")
                cards = []
                for line in lines:
                    if line.startswith("💳"):
                        try:
                            card_data = line.replace("💳", "").strip().split(" | ")
                            if len(card_data) == 4:
                                card_number = card_data[0].replace(" ", "")
                                exp_month = card_data[1].strip()
                                exp_year = card_data[2].strip()
                                cvc = card_data[3].strip()
                                if (card_number.isdigit() and len(card_number) == 16 and
                                        exp_month.isdigit() and exp_year.isdigit() and cvc.isdigit()):
                                    cards.append({
                                        "number": card_number,
                                        "exp_month": int(exp_month),
                                        "exp_year": int(exp_year),
                                        "cvc": cvc
                                    })
                                    logger.debug(f"Parsed card: {card_number}")
                                else:
                                    logger.warning(f"Invalid card data in line: {line}")
                            else:
                                logger.warning(f"Malformed card line: {line}")
                        except (ValueError, IndexError) as e:
                            logger.warning(f"Failed to parse card: {line}, error: {str(e)}")
                            continue

                if not cards:
                    logger.error("No valid cards parsed from /gen message")
                    update.message.reply_text(
                        "⚠️ No valid cards found in the replied message!",
                        parse_mode="Markdown"
                    )
                    return

                logger.info(f"Checking {len(cards)} cards")
                update.message.reply_text(
                    "🔄 *Checking cards... Please wait...* 🔄",
                    parse_mode="Markdown"
                )
                message = update.message.reply_text(
                    "📊 *Results*:\nStarting...",
                    parse_mode="Markdown"
                )
                results = "📊 *Card Check Results* 📊\n\n"
                batch_results = ""
                batch_size = 3

                for i, card in enumerate(cards, 1):
                    result = validate_card(
                        card["number"],
                        card["exp_month"],
                        card["exp_year"],
                        card["cvc"]
                    )
                    status = result["status"]
                    masked_number = f"{card['number'][:6]}****{card['number'][-4:]}"
                    result_text = (
                        f"💳 *Card {i}*: {masked_number}\n"
                        f"{'✅' if status == 'Live' else '❌'} *Status*: {status}\n"
                    )
                    batch_results += result_text + "\n"

                    if i % batch_size == 0 or i == len(cards):
                        results += batch_results
                        context.bot.edit_message_text(
                            chat_id=message.chat_id,
                            message_id=message.message_id,
                            text=results,
                            parse_mode="Markdown"
                        )
                        batch_results = ""
                    time.sleep(1)

                bin_info = get_bin_info(cards[0]["number"])
                results += "\n🏦 *BIN Info*:\n"
                if "error" in bin_info:
                    results += f"❌ *Error*: {bin_info['error']}\n"
                else:
                    results += f"🏛 *Bank*: {bin_info['bank']}\n"
                    results += f"💳 *Brand*: {bin_info['brand']}\n"
                    results += f"📋 *Type*: {bin_info['type']}\n"
                    results += f"🌍 *Country*: {bin_info['country']}\n"

                context.bot.edit_message_text(
                    chat_id=message.chat_id,
                    message_id=message.message_id,
                    text=results,
                    parse_mode="Markdown"
                )
                logger.info("Card checking completed")
                return

        logger.info("Processing as manual /chk command")
        command = update.message.text.split(" ", 1)
        if len(command) < 2:
            update.message.reply_text(
                "⚠️ Usage: /chk `card_number|exp_month|exp_year|cvc`",
                parse_mode="Markdown"
            )
            return

        card_details = command[1].split("|")
        if len(card_details) != 4:
            update.message.reply_text(
                "⚠️ Invalid format! Use: `card_number|exp_month|exp_year|cvc`",
                parse_mode="Markdown"
            )
            return

        card_number, exp_month, exp_year, cvc = card_details
        card_number = card_number.replace(" ", "").strip()

        result = validate_card(card_number, int(exp_month), int(exp_year), cvc)
        bin_info = get_bin_info(card_number)

        response = f"💳 *Card Validation Result* 💳\n\n"
        response += f"🔢 *Card Number*: {card_number[:6]}****{card_number[-4:]}\n"
        response += f"📅 *Expiry*: {exp_month}/{exp_year}\n"
        response += f"🔐 *CVC*: {cvc}\n\n"
        response += f"{'✅' if result['status'] == 'Live' else '❌'} *Status*: {result['status']}\n"
        if result["status"] == "Dead":
            response += f"❗ *Error*: {result['error']}\n"

        response += "\n🏦 *BIN Info*:\n"
        if "error" in bin_info:
            response += f"❌ *Error*: {bin_info['error']}\n"
        else:
            response += f"🏛 *Bank*: {bin_info['bank']}\n"
            response += f"💳 *Brand*: {bin_info['brand']}\n"
            response += f"📋 *Type*: {bin_info['type']}\n"
            response += f"🌍 *Country*: {bin_info['country']}\n"

        update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in check_card: {str(e)}")
        update.message.reply_text(f"⚠️ Error: {str(e)}", parse_mode="Markdown")

def error_handler(update, context):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.message:
        update.message.reply_text(
            "⚠️ An error occurred. Please try again later.",
            parse_mode="Markdown"
        )

def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("addsk", add_sk))
    dp.add_handler(CommandHandler("removesk", remove_sk_command))
    dp.add_handler(CommandHandler("chk", check_card))
    dp.add_handler(CommandHandler("gen", generate_cards))
    dp.add_error_handler(error_handler)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
