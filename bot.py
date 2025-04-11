import random
import requests
import os
from fastapi import FastAPI, Query
from typing import Optional

app = FastAPI()

# Luhn Algorithm to validate the card number
def luhn_check(card_number: str) -> bool:
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10 == 0

# Complete Luhn Algorithm to generate a valid card number
def complete_luhn(card_number: str) -> str:
    digits = [int(d) for d in card_number]
    checksum = sum(digits[-1::-2])
    for d in digits[-2::-2]:
        checksum += sum([int(x) for x in str(d * 2)])
    check_digit = (10 - checksum % 10) % 10
    return card_number + str(check_digit)

# Generate a random card number using the provided BIN
def generate_card(bin: str) -> str:
    remaining = 16 - len(bin)
    while True:
        num = bin + ''.join(str(random.randint(0, 9)) for _ in range(remaining - 1))
        num = complete_luhn(num)
        if luhn_check(num):
            break
    exp_month = str(random.randint(1, 12)).zfill(2)
    exp_year = str(random.randint(25, 30))
    cvv = str(random.randint(100, 999))
    return f"`{num}`|{exp_month}|{exp_year}|{cvv}"

# Fetch BIN details using an external API
async def get_bin_details(bin: str) -> dict:
    url = f"https://lookup.binlist.net/{bin}"
    response = requests.get(url)
    return response.json()

# Send the generated cards to a Telegram bot using the bot token
def send_to_telegram(message: str):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")  # Bot token from environment variable
    chat_id = os.getenv("TELEGRAM_CHAT_ID")  # Chat ID from environment variable
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    params = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }
    response = requests.get(url, params=params)
    return response.json()

# Health Check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}

# Generate cards endpoint
@app.get("/gen")
async def gen_cards(bin: str = Query(..., min_length=6, max_length=16), count: int = 15):
    details = await get_bin_details(bin)
    cards = [generate_card(bin) for _ in range(count)]
    card_block = "\n".join(cards)

    msg = (
        f"Generated Cards 🚀\n\n"
        f"💳 Card Type: {details.get('type', 'Unknown')} ({details.get('scheme', 'Unknown')})\n"
        f"🏦 Bank: {details.get('bank', {}).get('name', 'Unknown')}\n"
        f"🌍 Country: {details.get('country', {}).get('name', 'Unknown')}\n\n"
        f"```\n{card_block}\n```\n\n"
        f"👉 Join our channel! @DarkDorking"
    )

    # Optionally send the message to Telegram
    send_to_telegram(msg)

    return {"message": msg}
