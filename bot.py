import random
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update

# Simulated BIN database
BIN Database = {
    "4": {"type": "Visa", "issuer": "Visa Inc.", "country": "United States"},
    "51": {"type": "Mastercard", "issuer": "Mastercard Inc.", "country": "United States"},
    "52": {"type": "Mastercard", "issuer": "Mastercard Inc.", "country": "United States"},
    "53": {"type": "Mastercard", "issuer": "Mastercard Inc.", "country": "United States"},
    "34": {"type": "American Express", "issuer": "American Express", "country": "United States"},
    "37": {"type": "American Express", "issuer": "American Express", "country": "United States"},
    "6011": {"type": "Discover", "issuer": "Discover Financial", "country": "United States"},
    "35": {"type": "JCB", "issuer": "JCB Co., Ltd.", "country": "Japan"},
}

# Fake address database by country
ADDRESS_DATABASE = {
    "United States": {
        "cities": ["New York", "Los Angeles", "Chicago", "Miami", "Houston"],
        "streets": ["Main St", "Park Ave", "Broadway", "Sunset Blvd", "Elm St"],
        "zip_codes": ["10001", "90001", "60601", "33101", "77001"]
    },
    "Japan": {
        "cities": ["Tokyo", "Osaka", "Kyoto", "Hiroshima", "Sapporo"],
        "streets": ["Sakura St", "Ginza Rd", "Shibuya Ave", "Umeda Blvd", "Hakata Ln"],
        "zip_codes": ["100-0001", "530-0001", "600-8001", "730-0001", "060-0001"]
    },
    "India": {
        "cities": ["Mumbai", "Delhi", "Bangalore", "Kolkata", "Chennai"],
        "streets": ["MG Road", "Connaught Place", "Brigade Rd", "Park St", "Anna Salai"],
        "zip_codes": ["400001", "110001", "560001", "700001", "600001"]
    },
    "United Kingdom": {
        "cities": ["London", "Manchester", "Birmingham", "Glasgow", "Liverpool"],
        "streets": ["High St", "Oxford Rd", "Queen’s Rd", "Sauchiehall St", "Bold St"],
        "zip_codes": ["SW1A 1AA", "M1 1AA", "B1 1AA", "G1 1AA", "L1 1AA"]
    }
}

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

def get_bin_details(bin_prefix):
    bin_str = str(bin_prefix)
    for key in BIN_DATABASE:
        if bin_str.startswith(key):
            return BIN_DATABASE[key]
    return {"type": "Unknown", "issuer": "Unknown", "country": "Unknown"}

def generate_fake_address(country):
    country_data = ADDRESS_DATABASE.get(country, {
        "cities": ["Unknown City"],
        "streets": ["Unknown St"],
        "zip_codes": ["00000"]
    })
    city = random.choice(country_data["cities"])
    street = random.choice(country_data["streets"])
    zip_code = random.choice(country_data["zip_codes"])
    return {
        "city": city,
        "street": f"{random.randint(1, 999)} {street}",
        "zip_code": zip_code,
        "country": country
    }

def generate_card_details(bin_prefix, total_length, count=1):
    cards = []
    for _ in range(count):
        card_number, error = generate_luhn_card_number(bin_prefix, total_length)
        if error:
            return [{"error": error}]
        
        bin_details = get_bin_details(bin_prefix)
        cards.append({
            "card_number": card_number,
            "bin": str(bin_prefix),
            "card_type": bin_details["type"],
            "issuer": bin_details["issuer"],
            "country": bin_details["country"]
        })
    return cards

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = """
🌟 *Welcome to CardGen Pro Bot!* 🌟
----------------------------------------
*Commands:*
/start - Show this message
/gen - Generate 15 card numbers
/fake <country> - Generate fake address
----------------------------------------
*Note:* For educational purposes only!
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
                        f"Issuer: {card['issuer']}\n"
                        f"Country: {card['country']}\n"
                    )
                await update.message.reply_text(message, parse_mode="Markdown")
            context.user_data.clear()
        except ValueError:
            await update.message.reply_text("Please enter a valid number for length!")

def main():
    # Replace with your actual bot token from BotFather
    TOKEN = "8071747780:AAF_oRPKCf38r2vBlgGEkPQzfQeFAsN5H0k"  # <--- Yahan apna token daal do
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("gen", gen))
    application.add_handler(CommandHandler("fake", fake))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
