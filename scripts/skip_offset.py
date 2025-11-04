#!/usr/bin/env python3
"""
Скрипт для принудительного пропуска проблемного offset в Telegram getUpdates.
Использовать когда бот застревает на одном offset.

Использование:
python skip_offset.py <offset_to_skip>

Например: python skip_offset.py 451606370
"""

import sys
import requests

# Токен бота
BOT_TOKEN = "7372636777:AAGZULVuDbnHh6GUE6atSNaReOEqdrK5LZg"

def skip_offset(offset):
    """Пропускает указанный offset, запросив следующий"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    
    print(f"🔍 Попытка пропустить offset {offset}...")
    
    # Запрашиваем offset + 1, чтобы Telegram пропустил проблемный
    params = {
        'offset': int(offset) + 1,
        'timeout': 0
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if data.get('ok'):
        print(f"✅ Offset {offset} пропущен!")
        print(f"📊 Следующие обновления: {len(data.get('result', []))} шт.")
        return True
    else:
        print(f"❌ Ошибка: {data}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("❌ Использование: python skip_offset.py <offset_to_skip>")
        print("Например: python skip_offset.py 451606370")
        sys.exit(1)
    
    try:
        offset = int(sys.argv[1])
        skip_offset(offset)
    except ValueError:
        print("❌ Offset должен быть числом!")
        sys.exit(1)
