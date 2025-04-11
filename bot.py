import random
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from fastapi import FastAPI
import uvicorn

# Telegram Bot Token
BOT_TOKEN = "8071747780:AAF_oRPKCf38r2vBlgGEkPQzfQeFAsN5H0k"

# Luhn algorithm
def luhn_checksum(card_number: str) -> int:
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10

def is_luhn_valid(card_number: str) -> bool:
    return luhn_checksum(card_number) == 0

# Card generator
def generate_card_details(bin_prefix: str, length: int, count: int = 15):
    cards = []
    if not bin_prefix.isdigit() or not (4 <= len(bin_prefix) <= 9):
        return [{"error": "Invalid BIN. BIN must be 4 to 9 digits."}]
    if length < len(bin_prefix) + 1:
        return [{"error": "Length must be greater than BIN length + 1."}]
    while len(cards) < count:
        number = bin_prefix
        while len(number) < length - 1:
            number += str(random.randint(0, 9))
        for check_digit in range(10):
            candidate = number + str(check_digit)
            if is_luhn_valid(candidate):
                cards.append({"card_number": candidate})
                break
    return cards

# Fake BIN details
def get_bin_details(bin_number: str):
    bin_prefix = str(bin_number)
    details = {
        "type": "Unknown",
        "issuer": "Unknown",
        "country": "Unknown"
    }
    if bin_prefix.startswith("4"):
        details.update({"type": "Visa", "issuer": "Bank X", "country": "USA"})
    elif bin_prefix.startswith("5"):
        details.update({"type": "Mastercard", "issuer": "Bank Y", "country": "UK"})
    elif bin_prefix.startswith("6"):
        details.update({"type": "Discover", "issuer": "Bank Z", "country": "Canada"})
    elif bin_prefix.startswith("34") or bin_prefix.startswith("37"):
        details.update({"type": "Amex", "issuer": "Amex Bank", "country": "USA"})
    return details

# Telegram bot commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Use /gen <BIN> <Length> to generate cards.\nExample: /gen 4532 16")

async def gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) == 2:
        bin_prefix = args[0]
        try:
            total_length = int(args[1])
        except ValueError:
            await update.message.reply_text("Error: Length must be a number (e.g., /gen 4532 16)")
            return
    else:
        await update.message.reply_text("Usage: /gen <BIN> <Length> (e.g., /gen 4532 16)")
        return

    cards = generate_card_details(bin_prefix, total_length, count=15)

    if "error" in cards[0]:
        await update.message.reply_text(cards[0]["error"])
        return

    card_lines = [card['card_number'] for card in cards]
    bin_details = get_bin_details(bin_prefix)
    card_output = ' | '.join(card_lines)

    message = (
        f"*Generated Cards (15):*\n"
        f"```{card_output}```\n\n"
        f"*BIN Info:*\n"
        f"Type: {bin_details['type']}\n"
        f"Issuer: {bin_details['issuer']}\n"
        f"Country: {bin_details['country']}"
    )

    await update.message.reply_text(message, parse_mode="Markdown")

# FastAPI for health check
app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Bot is running"}

def run_web():
    uvicorn.run(app, host="0.0.0.0", port=8080)

# Run both FastAPI and Telegram bot
def run_bot():
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("gen", gen))
    print("Telegram Bot running...")
    bot_app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    run_bot()
