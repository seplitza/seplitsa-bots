#!/bin/bash
# Скрипт для проверки кода на сервере

echo "========================================="
echo "🔍 ПРОВЕРКА КОДА НА СЕРВЕРЕ"
echo "========================================="
echo ""

echo "1️⃣ Проверка функции should_initiate_data_collection (должна быть return True):"
grep -A 3 "Инициируем сбор данных для новых пользователей" /home/seplitsa/seplitsa-bots/bots/info/bot.py
echo ""

echo "2️⃣ Проверка функции send_typing_periodically (должна быть 'Первый typing'):"
grep -A 2 "Первый typing отправлен" /home/seplitsa/seplitsa-bots/bots/info/bot.py
echo ""

echo "3️⃣ Последний коммит в репозитории:"
cd /home/ubuntu/seplitsa-bots && git log --oneline -1
echo ""

echo "4️⃣ Последний коммит в рабочей директории:"
cd /home/seplitsa/seplitsa-bots && git log --oneline -1 2>/dev/null || echo "❌ Не git репозиторий"
echo ""

echo "5️⃣ Сравнение файлов (должно быть пусто если идентичны):"
diff /home/ubuntu/seplitsa-bots/bots/info/bot.py /home/seplitsa/seplitsa-bots/bots/info/bot.py | head -20
echo ""

echo "========================================="
echo "✅ ПРОВЕРКА ЗАВЕРШЕНА"
echo "========================================="
