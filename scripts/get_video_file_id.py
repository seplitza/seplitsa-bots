#!/usr/bin/env python3
"""
Скрипт для получения file_id видео из Telegram
Использование: перешлите видео боту, он вернет file_id
"""

import telebot
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN_INFO')

if not TOKEN:
    print("❌ Не найден TELEGRAM_BOT_TOKEN_INFO в .env")
    exit(1)

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(content_types=['video', 'video_note'])
def get_file_id(message):
    """Получает file_id видео"""
    if message.video:
        file_id = message.video.file_id
        file_size = message.video.file_size
        duration = message.video.duration
        
        response = (
            f"✅ VIDEO FILE ID получен!\n\n"
            f"📹 File ID:\n`{file_id}`\n\n"
            f"ℹ️ Размер: {file_size / 1024 / 1024:.2f} MB\n"
            f"⏱ Длительность: {duration} сек\n\n"
            f"Используйте этот file_id в базе знаний!"
        )
        bot.reply_to(message, response, parse_mode='Markdown')
        print(f"File ID: {file_id}")
        
    elif message.video_note:
        file_id = message.video_note.file_id
        response = f"✅ VIDEO NOTE FILE ID:\n`{file_id}`"
        bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(
        message, 
        "👋 Пришлите мне видео из канала, и я верну его file_id!\n\n"
        "📹 Просто перешлите видео сюда."
    )

if __name__ == '__main__':
    print("🤖 Бот запущен! Перешлите видео, чтобы получить file_id...")
    bot.polling(none_stop=True)
