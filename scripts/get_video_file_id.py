#!/usr/bin/env python3
"""
Telegram-бот для получения file_id видео и других медиа
Использование: перешлите медиа боту, он вернет file_id
Бот: @get_video_file_id_bot
"""

import telebot
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = "8037839466:AAF17Z5jGssJZxk9pO9VhM7uagdEZ_WZPHw"

bot = telebot.TeleBot(TOKEN)

# Статистика
stats = {
    'videos': 0,
    'photos': 0,
    'documents': 0,
    'audio': 0,
    'voice': 0,
    'video_notes': 0,
    'start_time': datetime.now()
}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Приветствие и инструкции"""
    welcome_text = """
🤖 **Telegram File ID Bot**

Я помогаю получать file_id для различных типов медиа!

📹 **Поддерживаемые типы:**
• Видео (video)
• Фото (photo)
• Документы (document)
• Аудио (audio)
• Голосовые (voice)
• Круглые видео (video_note)

💡 **Как использовать:**
1. Перешлите мне медиа-файл
2. Получите file_id для базы знаний

📊 **Команды:**
/start - Это сообщение
/stats - Статистика бота
/format - Формат для базы знаний

🌟 Готов к работе!
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def send_stats(message):
    """Статистика использования"""
    uptime = datetime.now() - stats['start_time']
    hours = int(uptime.total_seconds() // 3600)
    minutes = int((uptime.total_seconds() % 3600) // 60)
    
    stats_text = f"""
📊 **СТАТИСТИКА БОТА**

⏱ Время работы: {hours}ч {minutes}м

📹 Видео: {stats['videos']}
🖼 Фото: {stats['photos']}
📄 Документы: {stats['documents']}
🎵 Аудио: {stats['audio']}
🎤 Голосовые: {stats['voice']}
⭕️ Круглые видео: {stats['video_notes']}

📈 Всего обработано: {sum(stats.values()) - 1}
"""
    bot.reply_to(message, stats_text, parse_mode='Markdown')

@bot.message_handler(commands=['format'])
def send_format_info(message):
    """Информация о формате для базы знаний"""
    format_text = """
📝 **ФОРМАТ ДЛЯ БАЗЫ ЗНАНИЙ**

После получения file_id используйте такой формат:

```json
{
  "тема": "[VIDEO:file_id]\\n\\nОписание..."
}
```

**Примеры:**

1️⃣ Видео в начале:
```json
"упражнение": "[VIDEO:BAACAgI...]\\n\\n💪 Описание"
```

2️⃣ Видео в середине:
```json
"тема": "Текст...\\n\\n[VIDEO:BAACAgI...]\\n\\nЕще текст"
```

3️⃣ Несколько видео:
```json
"комплекс": "[VIDEO:id1]\\n\\nЧасть 1\\n\\n[VIDEO:id2]"
```

📚 Документация: docs/video-knowledge-base.md
"""
    bot.reply_to(message, format_text, parse_mode='Markdown')

@bot.message_handler(content_types=['video'])
def handle_video(message):
    """Обработка видео"""
    stats['videos'] += 1
    
    video = message.video
    file_id = video.file_id
    file_size = video.file_size / 1024 / 1024  # MB
    duration = video.duration
    width = video.width
    height = video.height
    
    response = f"""
✅ **VIDEO FILE ID ПОЛУЧЕН!**

📹 **File ID:**
`{file_id}`

ℹ️ **Информация:**
• Размер: {file_size:.2f} MB
• Длительность: {duration} сек
• Разрешение: {width}x{height}

📋 **Для базы знаний:**
```
[VIDEO:{file_id}]
```

💡 Скопируйте file_id и используйте в knowledge.json
"""
    
    bot.reply_to(message, response, parse_mode='Markdown')
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Video: {file_id[:20]}... ({file_size:.2f}MB)")

@bot.message_handler(content_types=['video_note'])
def handle_video_note(message):
    """Обработка круглых видео"""
    stats['video_notes'] += 1
    
    video_note = message.video_note
    file_id = video_note.file_id
    duration = video_note.length
    
    response = f"""
✅ **VIDEO NOTE FILE ID ПОЛУЧЕН!**

⭕️ **File ID:**
`{file_id}`

ℹ️ **Длительность:** {duration} сек

📋 **Для базы знаний:**
```
[VIDEO:{file_id}]
```
"""
    
    bot.reply_to(message, response, parse_mode='Markdown')
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Video Note: {file_id[:20]}...")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """Обработка фото"""
    stats['photos'] += 1
    
    # Берем фото максимального размера
    photo = message.photo[-1]
    file_id = photo.file_id
    file_size = photo.file_size / 1024 if photo.file_size else 0
    
    response = f"""
✅ **PHOTO FILE ID ПОЛУЧЕН!**

🖼 **File ID:**
`{file_id}`

ℹ️ **Размер:** {file_size:.2f} KB
📐 **Разрешение:** {photo.width}x{photo.height}

📋 **Для использования:**
```
[PHOTO:{file_id}]
```
"""
    
    bot.reply_to(message, response, parse_mode='Markdown')
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Photo: {file_id[:20]}...")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    """Обработка документов"""
    stats['documents'] += 1
    
    document = message.document
    file_id = document.file_id
    file_name = document.file_name
    file_size = document.file_size / 1024 / 1024
    
    response = f"""
✅ **DOCUMENT FILE ID ПОЛУЧЕН!**

📄 **File ID:**
`{file_id}`

ℹ️ **Информация:**
• Имя: {file_name}
• Размер: {file_size:.2f} MB

📋 **Для использования:**
```
[DOCUMENT:{file_id}]
```
"""
    
    bot.reply_to(message, response, parse_mode='Markdown')
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Document: {file_name}")

@bot.message_handler(content_types=['audio'])
def handle_audio(message):
    """Обработка аудио"""
    stats['audio'] += 1
    
    audio = message.audio
    file_id = audio.file_id
    duration = audio.duration
    title = audio.title or "Без названия"
    performer = audio.performer or "Неизвестен"
    
    response = f"""
✅ **AUDIO FILE ID ПОЛУЧЕН!**

🎵 **File ID:**
`{file_id}`

ℹ️ **Информация:**
• Исполнитель: {performer}
• Название: {title}
• Длительность: {duration} сек

📋 **Для использования:**
```
[AUDIO:{file_id}]
```
"""
    
    bot.reply_to(message, response, parse_mode='Markdown')
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Audio: {title}")

@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    """Обработка голосовых"""
    stats['voice'] += 1
    
    voice = message.voice
    file_id = voice.file_id
    duration = voice.duration
    
    response = f"""
✅ **VOICE FILE ID ПОЛУЧЕН!**

🎤 **File ID:**
`{file_id}`

ℹ️ **Длительность:** {duration} сек

📋 **Для использования:**
```
[VOICE:{file_id}]
```
"""
    
    bot.reply_to(message, response, parse_mode='Markdown')
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Voice: {duration}s")

@bot.message_handler(func=lambda message: True)
def handle_other(message):
    """Обработка всех остальных сообщений"""
    response = """
❓ **Неизвестный тип медиа**

Я работаю с:
📹 Видео
🖼 Фото  
📄 Документы
🎵 Аудио
🎤 Голосовые
⭕️ Круглые видео

Отправьте /help для справки
"""
    bot.reply_to(message, response, parse_mode='Markdown')

if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("🤖 Get Video File ID Bot (@get_video_file_id_bot)")
    logger.info("=" * 50)
    logger.info(f"✅ Бот запущен: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("📹 Готов к получению медиа-файлов...")
    logger.info("💡 Нажмите Ctrl+C для остановки")
    logger.info("=" * 50)
    
    try:
        # Удаляем вебхук
        bot.remove_webhook()
        
        # Запускаем polling
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
        
    except KeyboardInterrupt:
        logger.info("\n" + "=" * 50)
        logger.info("🛑 Бот остановлен пользователем")
        total = sum([v for k, v in stats.items() if k != 'start_time'])
        logger.info(f"📊 Обработано файлов: {total}")
        logger.info("=" * 50)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        logger.info("👋 Завершение работы бота")

