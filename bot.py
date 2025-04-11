import random
import requests
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Luhn Algorithm for Card Number Validation
def luhn_check(card_number: str) -> bool:
    total = 0
    reverse_digits = card_number[::-1]
    for i, digit in enumerate(reverse_digits):
        n = int(digit)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0

# Card Number Generation from BIN (Luhn Algorithm)
def generate_card_number(bin: str) -> str:
    card_number = bin
    while len(card_number) < 15:  # Assuming length of card is 15 before applying Luhn
        card_number += str(random.randint(0, 9))
    
    # Apply Luhn Check to finalize the card number
    if luhn_check(card_number):
        return card_number
    else:
        # If it's not valid, add one more digit and check again
        card_number += str(random.randint(0, 9))
        return card_number

# Function to get BIN details from API
def get_bin_details(bin: str):
    url = f"https://lookup.binlist.net/{bin}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None

# Telegram Bot Command to Handle Card Generation
def generate_card(update: Update, context: CallbackContext):
    bin = context.args[0] if context.args else ""
    
    if not bin:
        update.message.reply_text("Please provide a BIN number.")
        return
    
    if len(bin) < 4 or len(bin) > 10:
        update.message.reply_text("Please enter a valid BIN (4 to 10 digits).")
        return

    card_number = generate_card_number(bin)
    
    bin_details = get_bin_details(bin)
    if bin_details:
        bin_info = f"BIN Details:\nBank: {bin_details.get('bank', {}).get('name', 'N/A')}\nCountry: {bin_details.get('country', {}).get('name', 'N/A')}\nType: {bin_details.get('type', 'N/A')}"
    else:
        bin_info = "BIN details not found."

    update.message.reply_text(f"Generated Card Number: {card_number}\n{bin_info}")

def main():
    # **INSERT YOUR BOT TOKEN HERE**
    updater = Updater("8071747780:AAF_oRPKCf38r2vBlgGEkPQzfQeFAsN5H0k", use_context=True)
    
    updater.dispatcher.add_handler(CommandHandler("generate_card", generate_card))
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
