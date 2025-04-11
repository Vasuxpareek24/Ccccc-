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
stripe.api_key = os.getenv("STRIPE_API_KEY")

# Luhn Algorithm for Card Generation
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
    card_number = bin_prefix + ''.join(random.choice(string.digits) for _ in range(length - len(bin_prefix) - 1))
    for i in range(10):
        candidate = card_number + str(i)
        if is_luhn_valid(candidate):
            return candidate
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

# Card Validation with Charge (Pre-Authorization)
def validate_card(card_number, exp_month, exp_year, cvc):
    if not stripe.api_key:
        logger.error("Stripe API key missing")
        return {"status": "Dead", "error": "Stripe API key not configured. Contact admin to set STRIPE_API_KEY."}
    
    logger.info(f"Validating card: {card_number}")
    try:
        # Step 1: Create a Payment Method
        logger.info("Creating PaymentMethod")
        payment_method = stripe.PaymentMethod.create(
            type="card",
            card={
                "number": card_number,
                "exp_month": exp_month,
                "exp_year": exp_year,
                "cvc": cvc,
            },
        )
        logger.info(f"PaymentMethod created: {payment_method.id}")

        # Step 2: Create a Payment Intent for $1 pre-authorization
        logger.info("Creating PaymentIntent")
        payment_intent = stripe.PaymentIntent.create(
            amount=100,  # $1 in cents
            currency="usd",
            payment_method=payment_method.id,
            capture_method="manual",  # Authorize only
            confirmation_method="manual",
            confirm=True,
            description="Card validation charge test",
        )
        logger.info(f"PaymentIntent created: {payment_intent.id}, Status: {payment_intent.status}")

        # Step 3: Check Payment Intent status
        if payment_intent.status == "requires_capture":
            logger.info("Charge authorized, canceling intent")
            stripe.PaymentIntent.cancel(payment_intent.id)
            return {"status": "Live", "payment_intent_id": payment_intent.id}
        else:
            error_msg = payment_intent.last_payment_error.message if payment_intent.last_payment_error else payment_intent.status
            logger.info(f"Charge failed: {error_msg}")
            return {"status": "Dead", "error": f"Charge failed: {error_msg}"}

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        return {"status": "Dead", "error": str(e.user_message if hasattr(e, 'user_message') else e)}
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"status": "Dead", "error": f"Unknown error: {str(e)}"}

# Telegram Handlers
def start(update, context):
    user = update.effective_user
    update.message.reply_text(
        f"👋 *Welcome, {user.first_name}!* 👋\n"
        "This bot validates cards by attempting a $1 charge via Stripe.\n"
        "Join our channel: @DarkDorking for updates!\n\n"
        "🔍 *Commands:*\n"
        "/chk `card_number|exp_month|exp_year|cvc` - Validate a card\n"
        "/gen `bin` - Generate 15 cards\n"
        "Reply /chk to check generated cards\n"
        "/addsk `secret_key` - Update Stripe key (admin only)\n"
        "/removesk - Remove Stripe key (admin only)",
        parse_mode="Markdown"
    )

def add_sk(update, context):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("🚫 Unauthorized!", parse_mode="Markdown")
        return
    try:
        command = update.message.text.split(" ", 1)
        if len(command) < 2:
            update.message.reply_text("⚠️ Usage: /addsk `secret_key`", parse_mode="Markdown")
            return
        new_sk = command[1].strip()
        if not new_sk.startswith("sk_"):
            update.message.reply_text("⚠️ Invalid key format! Must start with 'sk_'.", parse_mode="Markdown")
            return
        stripe.api_key = new_sk
        stripe.Balance.retrieve()
        update.message.reply_text("✅ Stripe key updated! Set STRIPE_API_KEY in Heroku to persist.", parse_mode="Markdown")
    except Exception as e:
        update.message.reply_text(f"⚠️ Error: {str(e)}", parse_mode="Markdown")

def remove_sk(update, context):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("🚫 Unauthorized!", parse_mode="Markdown")
        return
    stripe.api_key = None
    update.message.reply_text("✅ Stripe key removed!", parse_mode="Markdown")

def generate_cards(update, context):
    if not stripe.api_key:
        update.message.reply_text("⚠️ Stripe key not configured. Contact @DarkDorking.", parse_mode="Markdown")
        return
    try:
        command = update.message.text.split(" ", 1)
        if len(command) < 2:
            update.message.reply_text("⚠️ Usage: /gen `bin`", parse_mode="Markdown")
            return
        bin_prefix = command[1].strip()
        if not bin_prefix.isdigit() or len(bin_prefix) < 6:
            update.message.reply_text("⚠️ BIN must be 6+ digits!", parse_mode="Markdown")
            return

        response = f"🛠 *Generated Cards for /gen {bin_prefix}* 🛠\n\n"
        cards = []
        for _ in range(15):
            card_number = generate_card_number(bin_prefix)
            if card_number:
                exp_month = random.randint(1, 12)
                exp_year = random.randint(2025, 2030)
                cvc = ''.join(random.choice(string.digits) for _ in range(3))
                response += f"💳 {card_number} | {exp_month:02d} | {exp_year} | {cvc}\n"
                cards.append({"number": card_number, "exp_month": exp_month, "exp_year": exp_year, "cvc": cvc})
            else:
                response += "❌ Failed to generate a valid card\n"

        bin_info = get_bin_info(bin_prefix)
        response += "\n🏦 *BIN Info*:\n"
        response += f"🏛 Bank: {bin_info.get('bank', 'Unknown')}\n"
        response += f"💳 Brand: {bin_info.get('brand', 'Unknown')}\n"
        response += f"📋 Type: {bin_info.get('type', 'Unknown')}\n"
        response += f"🌍 Country: {bin_info.get('country', 'Unknown')}\n"
        response += "\nℹ️ Reply with /chk to validate via Stripe charge!"
        update.message.reply_text(response, parse_mode="Markdown")
    except Exception as e:
        update.message.reply_text(f"⚠️ Error: {str(e)}", parse_mode="Markdown")

def check_card(update, context):
    if not stripe.api_key:
        update.message.reply_text("⚠️ Stripe key not configured. Contact @DarkDorking.", parse_mode="Markdown")
        return
    try:
        if update.message.reply_to_message and "Generated Cards" in update.message.reply_to_message.text:
            lines = update.message.reply_to_message.text.split("\n")
            cards = []
            for line in lines:
                if line.startswith("💳"):
                    try:
                        card_data = line.replace("💳", "").strip().split(" | ")
                        if len(card_data) == 4:
                            card_number, exp_month, exp_year, cvc = card_data
                            cards.append({
                                "number": card_number.replace(" ", ""),
                                "exp_month": int(exp_month),
                                "exp_year": int(exp_year),
                                "cvc": cvc
                            })
                    except Exception:
                        continue

            if not cards:
                update.message.reply_text("⚠️ No valid cards found!", parse_mode="Markdown")
                return

            update.message.reply_text("🔄 *Charging cards... Please wait...* 🔄", parse_mode="Markdown")
            message = update.message.reply_text("📊 *Results*:\nStarting...", parse_mode="Markdown")
            results = "📊 *Card Check Results* 📊\n\n"
            batch_results = ""
            batch_size = 3

            for i, card in enumerate(cards, 1):
                result = validate_card(card["number"], card["exp_month"], card["exp_year"], card["cvc"])
                status = result["status"]
                result_text = (
                    f"💳 *Card {i}*\n"
                    f"🔢 *Card Number*: {card['number']}\n"
                    f"📅 *Expiry*: {card['exp_month']:02d} / {card['exp_year']}\n"
                    f"🔐 *CVC*: {card['cvc']}\n"
                    f"{'✅' if status == 'Live' else '❌'} *Status*: {status}\n"
                )
                if status == "Dead" and "error" in result:
                    result_text += f"❗ Reason: {result['error']}\n"
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
                time.sleep(0.5)

            bin_info = get_bin_info(cards[0]["number"])
            results += "\n🏦 *BIN Info*:\n"
            results += f"🏛 Bank: {bin_info.get('bank', 'Unknown')}\n"
            results += f"💳 Brand: {bin_info.get('brand', 'Unknown')}\n"
            results += f"📋 Type: {bin_info.get('type', 'Unknown')}\n"
            results += f"🌍 Country: {bin_info.get('country', 'Unknown')}\n"
            context.bot.edit_message_text(
                chat_id=message.chat_id,
                message_id=message.message_id,
                text=results,
                parse_mode="Markdown"
            )
            return

        # Manual /chk
        command = update.message.text.split(" ", 1)
        if len(command) < 2:
            update.message.reply_text("⚠️ Usage: /chk `card_number|exp_month|exp_year|cvc`", parse_mode="Markdown")
            return
        card_details = command[1].split("|")
        if len(card_details) != 4:
            update.message.reply_text("⚠️ Invalid format! Use: `card_number|exp_month|exp_year|cvc`", parse_mode="Markdown")
            return
        card_number, exp_month, exp_year, cvc = card_details
        card_number = card_number.replace(" ", "").strip()
        result = validate_card(card_number, int(exp_month), int(exp_year), cvc)
        bin_info = get_bin_info(card_number)
        response = f"💳 *Card Validation Result* 💳\n\n"
        response += f"🔢 *Card Number*: {card_number}\n"
        response += f"📅 *Expiry*: {exp_month}/{exp_year}\n"
        response += f"🔐 *CVC*: {cvc}\n\n"
        response += f"{'✅' if result['status'] == 'Live' else '❌'} *Status*: {result['status']}\n"
        if result["status"] == "Dead" and "error" in result:
            response += f"❗ *Error*: {result['error']}\n"
        response += "\n🏦 *BIN Info*:\n"
        response += f"🏛 Bank: {bin_info.get('bank', 'Unknown')}\n"
        response += f"💳 Brand: {bin_info.get('brand', 'Unknown')}\n"
        response += f"📋 Type: {bin_info.get('type', 'Unknown')}\n"
        response += f"🌍 Country: {bin_info.get('country', 'Unknown')}\n"
        update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        update.message.reply_text(f"⚠️ Error: {str(e)}", parse_mode="Markdown")

def error_handler(update, context):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.message:
        update.message.reply_text("⚠️ An error occurred.", parse_mode="Markdown")

def main():
    if not stripe.api_key:
        logger.error("STRIPE_API_KEY not set.")
    else:
        logger.info("Stripe API key loaded.")
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("addsk", add_sk))
    dp.add_handler(CommandHandler("removesk", remove_sk))
    dp.add_handler(CommandHandler("chk", check_card))
    dp.add_handler(CommandHandler("gen", generate_cards))
    dp.add_error_handler(error_handler)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
