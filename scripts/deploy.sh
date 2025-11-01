#!/bin/bash

echo "🚀 Deploying Seplitsa Bots..."

# Останавливаем ботов
sudo systemctl stop seplitsa-expert-bot
sudo systemctl stop seplitsa-info-bot

# Копируем обновленные файлы
cp bots/expert/bot.py /home/ubuntu/seplitsa-expert-bot/
cp bots/info/bot.py /home/ubuntu/seplitsa-info-bot/

# Копируем systemd службы если изменились
if [ -f systemd/seplitsa-expert-bot.service.template ]; then
    sudo cp systemd/seplitsa-expert-bot.service.template /etc/systemd/system/seplitsa-expert-bot.service
fi

if [ -f systemd/seplitsa-info-bot.service.template ]; then
    sudo cp systemd/seplitsa-info-bot.service.template /etc/systemd/system/seplitsa-info-bot.service
fi

# Обновляем systemd
sudo systemctl daemon-reload

# Запускаем ботов
sudo systemctl start seplitsa-expert-bot
sudo systemctl start seplitsa-info-bot

echo "✅ Deployment completed!"
echo "📊 Check status: sudo systemctl status seplitsa-*-bot"
