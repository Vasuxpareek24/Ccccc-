import random
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update

# Simulated BIN database (more realistic)
BIN_DATABASE = {
    "4532": {"type": "Visa", "issuer": "Chase Bank", "country": "United States"},
    "4111": {"type": "Visa", "issuer": "Bank of America", "country": "United States"},
    "5105": {"type": "Mastercard", "issuer": "Citibank", "country": "United States"},
    "5200": {"type": "Mastercard", "issuer": "Barclays", "country": "United Kingdom"},
    "3400": {"type": "American Express", "issuer": "American Express", "country": "United States"},
    "3700": {"type": "American Express", "issuer": "American Express", "country": "United States"},
    "6011": {"type": "Discover", "issuer": "Discover Financial", "country": "United States"},
    "3528": {"type": "JCB", "issuer": "JCB Co., Ltd.", "country": "Japan"},
    "5588": {"type": "Mastercard", "issuer": "HDFC Bank", "country": "India"},
    "6221": {"type": "UnionPay", "issuer": "China UnionPay", "country": "China"},
}

# Expanded address database for realistic fake addresses
ADDRESS_DATABASE = {
    "United States": {
        "cities": ["New York, NY", "Los Angeles, CA", "Chicago, IL", "Miami, FL", "Houston, TX", "Seattle, WA"],
        "streets": ["Main Street", "Park Avenue", "Broadway", "Sunset Boulevard", "Elm Street", "Cedar Lane"],
        "zip_codes": ["10001", "90001", "60601", "33101", "77001", "98101"]
    },
    "Japan": {
        "cities": ["Tokyo", "Osaka", "Kyoto", "Hiroshima", "Sapporo", "Yokohama"],
        "streets": ["Sakura Street", "Ginza Road", "Shibuya Avenue", "Umeda Boulevard", "Hakata Lane", "Asakusa Road"],
        "zip_codes": ["100-0001", "530-0001", "600-8001", "730-0001", "060-0001", "220-0001"]
    },
    "India": {
        "cities": ["Mumbai, Maharashtra", "Delhi", "Bangalore, Karnataka", "Kolkata, West Bengal", "Chennai, Tamil Nadu", "Hyderabad, Telangana"],
        "streets": ["MG Road", "Connaught Place", "Brigade Road", "Park Street", "Anna Salai", "Banjara Hills"],
        "zip_codes": ["400001", "110001", "560001", "700001", "600001", "500001"]
    },
    "United Kingdom": {
        "cities": ["London", "Manchester", "Birmingham", "Glasgow", "Liverpool", "Edinburgh"],
        "streets": ["High Street", "Oxford Road", "Queen’s Road", "Sauchiehall Street", "Bold Street", "Princes Street"],
        "zip_codes": ["SW1A 1AA", "M1 1AA", "B1 1AA", "G1 1AA", "L1 1AA", "EH1 1AA"]
    },
    "China": {
        "cities": ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Chengdu", "Hangzhou"],
        "streets": ["Nanjing Road", "Wangfujing Street", "Huaihai Road", "Jiefangbei Road", "Jinli Street", "West Lake Road"],
        "zip_codes": ["100000", "200000", "510000", "518000", "610000", "310000"]
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
        "streets": ["Unknown Street"],
        "zip_codes": ["00000"]
    })
    city = random.choice(country_data["cities"])
    street = random.choice(country_data["streets"])
    zip_code = random.choice(country_data["zip_codes"])
    house_number = random.randint(1, 999)
    return {
        "street": f"{house_number} {street}",
        "city": city,
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
/gen [BIN] [length] - Generate 15 card numbers (e.g., /gen 4532 16)
/fake <country> - Generate a realistic fake address (e.g., /fake United States)
----------------------------------------
*Note:* For educational purposes only! 🚀
"""
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

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
        bin_prefix = "4532"  # Default BIN
        total_length = 16    # Default length
    
    cards = generate_card_details(bin_prefix, total_length, count=15)
    
    if "error" in cards[0]:
        await update.message.reply_text(cards[0]["error"])
        return
    
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

async def fake(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        country = ' '.join(context.args).strip()
        if not country:
            await update.message.reply_text("Please specify a country (e.g., /fake United States)")
            return
        address = generate_fake_address(country)
        message = (
            f"*Generated Realistic Fake Address:*\n"
            f"Street: {address['street']}\n"
            f"City: {address['city']}\n"
            f"Zip Code: {address['zip_code']}\n"
            f"Country: {address['country']}"
        )
        await update.message.reply_text(message, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

def main():
    # Replace with your actual bot token from BotFather
    TOKEN = "8071747780:AAF_oRPKCf38r2vBlgGEkPQzfQeFAsN5H0k"  # <--- Yahan apna token daal do
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("gen", gen))
    application.add_handler(CommandHandler("fake", fake))
    
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
