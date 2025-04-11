import random
import httpx

def luhn_checksum(card_number):
    def digits_of(n): return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd = digits[-1::-2]
    even = digits[-2::-2]
    total = sum(odd)
    for d in even:
        total += sum(digits_of(d * 2))
    return total % 10

def generate_card(bin_prefix):
    while True:
        partial = bin_prefix + ''.join(str(random.randint(0, 9)) for _ in range(15 - len(bin_prefix)))
        checksum = (10 - luhn_checksum(partial + '0')) % 10
        card = partial + str(checksum)
        if luhn_checksum(card) == 0:
            return card

async def get_bin_details(bin_number):
    url = f"https://lookup.binlist.net/{bin_number}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "scheme": data.get("scheme", "UNKNOWN").upper(),
                "type": data.get("type", "UNKNOWN").upper(),
                "bank": data.get("bank", {}).get("name", "UNKNOWN"),
                "country": data.get("country", {}).get("name", "UNKNOWN")
            }
    return {"scheme": "UNKNOWN", "type": "UNKNOWN", "bank": "UNKNOWN", "country": "UNKNOWN"}
  
