from fastapi import FastAPI, Query
from utils import generate_card, get_bin_details

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/gen")
async def gen_cards(bin: str = Query(..., min_length=4, max_length=16), count: int = 15):
    details = await get_bin_details(bin)
    cards = [generate_card(bin) + "|10|27|527" for _ in range(count)]
    card_block = "\n".join(cards)

    msg = (
        f"Generated Cards 🚀\n\n"
        f"💳 Card Type: {details['type']} ({details['scheme']})\n"
        f"🏦 Bank: {details['bank']}\n"
        f"🌍 Country: {details['country']}\n\n"
        f"```\n{card_block}\n```\n\n"
        f"👉 Join our channel! @DarkDorking"
    )

    return {"message": msg}
