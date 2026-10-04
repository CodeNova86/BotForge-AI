import os
import sys
import telebot

# توکن ربات - مستقیم در کد قرار داده شده
BOT_TOKEN = "7507998082:AAECM4xs-AzAshGchuU-7BOyXE-mnl-Gzao"

bot = telebot.TeleBot(BOT_TOKEN)


@bot.message_handler(commands=["start"])
def handle_start(message):
    user_name = message.from_user.first_name or "User"
    response_text = (
        f"سلام {user_name}!\n"
        "من یک بات اکو (Echo) هستم.\n"
        "هر پیامی بفرستید، من همان را برمی‌گردانم."
    )
    bot.reply_to(message, response_text)


@bot.message_handler(commands=["help"])
def handle_help(message):
    help_text = (
        "دستورات موجود:\n"
        "/start - شروع کار با بات\n"
        "/help - نمایش این راهنما\n\n"
        "هر متن دیگری بفرستید تا اکو شود."
    )
    bot.reply_to(message, help_text)


@bot.message_handler(func=lambda message: True)
def echo_message(message):
    """اکو کردن هر پیام متنی"""
    bot.reply_to(message, message.text)


if __name__ == "__main__":
    print("Echo bot polling started successfully...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)