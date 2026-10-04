import os
import sys
import telebot

# توکن ربات را می‌توانید از متغیر محیطی بگیرید یا برای تست سریع اینجا جایگزین کنید
BOT_TOKEN = "8831726454:AAG1TGtmv3dxlkacnAtyGonv342K4h98wpc"

if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
  print(
      "Warning: BOT_TOKEN is using the default placeholder.", file=sys.stderr
  )

bot = telebot.TeleBot(BOT_TOKEN)


@bot.message_handler(commands=["start"])
def handle_start(message):
  user_name = message.from_user.first_name or "User"
  response_text = (
      f"Hello {user_name}!\n"
      "Bot is active and running inside the isolated sandbox."
  )
  bot.reply_to(message, response_text)


if __name__ == "__main__":
  print("Telegram bot polling started successfully...")
  # infinity_polling باعث می‌شود ربات در صورت قطعی لحظه‌ای شبکه کرش نکند
  bot.infinity_polling(timeout=10, long_polling_timeout=5)