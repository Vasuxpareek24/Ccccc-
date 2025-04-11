import random
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Luhn algorithm to generate valid card numbers
def generate_luhn_card_number(bin_prefix, total_length):
    if not bin_prefix.isdigit():
        return None, "Error: BIN prefix must contain only digits!"
    if total_length < len(bin_prefix) + 1:
        return None, "Error: Total length must be greater than BIN length!"
    
    card_number = [int(d) for d in str(bin_prefix)]
    while len(card_number) < total_length - 1:
        card_number.append(random.randint(0, 9))
    
    total = 0
    is_even = False
    for i in range(len(card_number) - 1, -1, -1):
        digit = card_number[i]
        if is_even:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
        is_even = not is_even
    
    check_digit = (10 - (total % 10)) % 10
    card_number.append(check_digit)
    
    return ''.join(map(str, card_number)), None

# Fetch real BIN details from binlist.net
def get_bin_details(bin_prefix):
    try:
        response = requests.get(f"https://lookup.binlist.net/{bin_prefix[:6]}")
        if response.status_code == 200:
            data = response.json()
            return {
                "type": data.get("type", "Unknown"),
                "brand": data.get("brand", "Unknown"),
                "issuer": data.get("bank", {}).get("name", "Unknown"),
                "country": data.get("country", {}).get("name", "Unknown")
            }
        return {"type": "Unknown", "brand": "Unknown", "issuer": "Unknown", "country": "Unknown"}
    except:
        return {"type": "Unknown", "brand": "Unknown", "issuer": "Unknown", "country": "Unknown"}

# Generate fake address using fakerapi.it
def generate_fake_address(country):
    try:
        # fakerapi.it doesn't support country-specific filtering directly, so we'll request multiple and pick one
        response = requests.get("https://fakerapi.it/api/v1/addresses?_quantity=1")
        if response.status_code == 200:
            data = response.json()["data"][0]
            return {
                "street": f"{data['streetName']} {random.randint(1, 999)}",
                "city": data.get("city", "Unknown City"),
                "zip_code": data.get("zipcode", "00000"),
                "country": country or "Unknown"  # Override with user-specified country
            }
    except:
        pass
    # Fallback to random data if API fails
    return {
        "street": f"{random.randint(1, 999)} Unknown St",
        "city": "Unknown City",
        "zip_code": "00000",
        "country": country or "Unknown"
    }

# Generate multiple card details
def generate_card_details(bin_prefix, total_length, count=1):
    cards = []
    bin_details = get_bin_details(bin_prefix)
    for _ in range(count):
        card_number, error = generate_luhn_card_number(bin_prefix, total_length)
        if error:
            return [{"error": error}]
        cards.append({
            "card_number": card_number,
            "bin": str(bin_prefix),
            "card_type": bin_details["type"],
            "brand": bin_details["brand"],
            "issuer": bin_details["issuer"],
            "country": bin_details["country"]
        })
    return cards

# Telegram command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = """
🌟 *Welcome to CardGen Pro Bot!* 🌟
----------------------------------------
*Commands:*
/start - Show this message
/gen - Generate 15 card numbers
/fake <country> - Generate fake address
----------------------------------------
*Note:* For educational purposes only! Do not use for illegal activities.
"""
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

async def gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please enter the BIN prefix (e.g., 4532):")
    context.user_data["awaiting"] = "bin"

async def fake(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        country = ' '.join(context.args).strip()
        if not country:
            await update.message.reply_text("Please specify a country (e.g., /fake United States)")
            return
        address = generate_fake_address(country)
        message = (
            f"*Generated Fake Address:*\n"
            f"Street: {address['street']}\n"
            f"City: {address['city']}\n"
            f"Zip Code: {address['zip_code']}\n"
            f"Country: {address['country']}"
        )
        await update.message.reply_text(message, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "awaiting" not in context.user_data:
        return
    
    text = update.message.text.strip()
    
    if context.user_data["awaiting"] == "bin":
        context.user_data["bin"] = text
        await update.message.reply_text("Enter total card number length (e.g., 16):")
        context.user_data["awaiting"] = "length"
    
    elif context.user_data["awaiting"] == "length":
        try:
            total_length = int(text)
            bin_prefix = context.user_data["bin"]
            cards = generate_card_details(bin_prefix, total_length, count=15)
            
            if "error" in cards[0]:
                await update.message.reply_text(cards[0]["error"])
            else:
                message = "*Generated 15 Card Details:*\n"
                for i, card in enumerate(cards, 1):
                    message += (
                        f"\n*Card {i}:*\n"
                        f"Card Number: `{card['card_number']}`\n"
                        f"BIN: {card['bin']}\n"
                        f"Card Type: {card['card_type']}\n"
                        f"Brand: {card['brand']}\n"
                        f"Issuer: {card['issuer']}\n"
                        f"Country: {card['country']}\n"
                    )
                # Split message if too long for Telegram
                if len(message) > 4096:
                    for i in range(0, len(message), 4096):
                        await update.message.reply_text(message[i:i+4096], parse_mode="Markdown")
                else:
                    await update.message.reply_text(message, parse_mode="Markdown")
            context.user_data.clear()
        except ValueError:
            await update.message.reply_text("Please enter a valid number for length!")

def main():
    # Replace with your actual bot token from BotFather
    TOKEN = "8071747780:AAF_oRPKCf38r2vBlgGEkPQzfQeFAsN5H0k"
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("gen", gen))
    application.add_handler(CommandHandler("fake", fake))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
