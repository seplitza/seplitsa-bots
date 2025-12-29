import telebot
import requests
import json
import os
import logging
import time
import re
import hashlib
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def clean_markdown(text):
    """Очищает текст от некорректных Markdown-символов"""
    if not text:
        return ""
    
    # Заменяем проблемные символы Markdown
    cleaned_text = re.sub(r'([*_`\\[\]])', r'\\\1', text)
    
    # Убеждаемся, что все Markdown-сущности правильно закрыты
    cleaned_text = re.sub(r'\*\*([^*]+)$', r'**\1**', cleaned_text)
    cleaned_text = re.sub(r'\*([^*]+)$', r'*\1*', cleaned_text)
    cleaned_text = re.sub(r'__([^_]+)$', r'__\1__', cleaned_text)
    cleaned_text = re.sub(r'`([^`]+)$', r'`\1`', cleaned_text)
    
    return cleaned_text

def safe_markdown_text(text):
    """Безопасно подготавливает текст для Markdown"""
    try:
        cleaned = clean_markdown(text)
        if len(cleaned) > 4000:
            cleaned = cleaned[:4000] + "..."
        return cleaned
    except Exception as e:
        logger.error(f"Ошибка очистки Markdown: {e}")
        return re.sub(r'([*_`\\[\]])', '', text)

# ==================== НАСТРОЙКИ ====================
TELEGRAM_TOKEN = "7411929961:AAFoWpxqQ_IBdcLYBE43qcmLpkRPfd5p3lY"
DEEPSEEK_API_KEY = "sk-030c8e9fbbb642a0b2850318ffad64a1"
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
AUTHOR_USERNAME = "alexpina76"
KNOWLEDGE_FILE = "seplitsa_knowledge.json"

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================clear
# = ПРОМПТ СЕПЛИЦА ====================
SEPLITSA_SYSTEM_PROMPT = """
Ты — «Сеплица-Эксперт», официальный AI-консультант системы естественного омоложения «Сеплица». 

# ОСНОВНЫЕ ПРИНЦИПЫ СИСТЕМЫ:
- Организм — единая система, где всё взаимосвязано
- Естественные методы вместо борьбы со следствиями
- Научная обоснованность каждого метода
- 4 ступени работают только вместе (синергетический эффект)

# ДЕТАЛЬНОЕ ОПИСАНИЕ 4-Х СТУПЕНЕЙ:

## 1. СЦЕПЛЕНИЕ (Упражнения для тела)
**Суть:** Работа с опорно-двигательным аппаратом для омоложения лица через фасциальные цепи.

**Конкретные методы:**
- 33 упражнения из курса «Зарядка долголетия»
- Улучшение осанки: раскрытие грудного отдела, укрепление кора
- Расслабление зажимов: трапеции, шея, поясница
- Активация фасций: улучшение эластичности соединительной ткани

**Результат:** Подтянутый овал лица, уменьшение второго подбородка, разглаживание морщин.

## 2. ЕСТЕСТВЕННОСТЬ (Массажи лица и шеи)
**Суть:** Локальная работа с мягкими тканями.

**Конкретные методы:**
- Лимфодренажный массаж: устранение отеков
- Расслабление миофасций: работа с жевательными, височными мышцами
- Тонизирование слабых мышц: скуловая мышца для подъема
- Упражнения для шеи и плеч

**Результат:** Устранение отеков, подтяжка овала, расслабленное выражение лица.

## 3. ПИТАНИЕ (Микробиом кишечника)
**Суть:** Создание внутренней среды для молодости.

**Конкретные методы:**
- Ферментированные продукты: квашеная капуста (без уксуса), моченые яблоки, кимчи
- Клетчатка: овощи, зелень, крупы (пребиотики)
- Исключение: ультра-обработанные продукты, сахар

**Результат:** Чистая кожа, крепкий иммунитет, улучшенное пищеварение.

## 4. ЗАБОТА О КЛЕТКАХ (Биохакинг)
**Суть:** Нутрицевтики для клеточных процессов.

**Конкретные добавки:**
- NMN (Никотинамидмононуклеотид) - энергия клеток, активация сиртуинов
- Омега-3 (DHA) - здоровье мозга и нервной системы
- Ресвератрол - активация сиртуинов, репарация ДНК
- Кверцетин - сенолитик (уничтожение старых клеток)

**Косметика:**
- GHK-Cu (Медный трипептид-1) - стимуляция коллагена
Отвечай строго в рамках системы.
"""

# ==================== ИНИЦИАЛИЗАЦИЯ БОТА ====================
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ==================== СИСТЕМА МЕНЮ ====================
MENU_STRUCTURE = {
    'main': {
        'title': '🏠 ГЛАВНОЕ МЕНЮ',
        'buttons': [
            '📚 СИСТЕМА СЕПЛИЦА: ОСНОВЫ',
            '💪 СТУПЕНЬ 1: СЦЕПЛЕНИЕ',
            '🙆 СТУПЕНЬ 2: ЕСТЕСТВЕННОСТЬ', 
            '🥗 СТУПЕНЬ 3: ПИТАНИЕ',
            '🔬 СТУПЕНЬ 4: БИОХАКИНГ',
            '🎓 КУРС "ОМОЛОДИСЬ"',
            '🛠️ ПРАКТИЧЕСКИЕ ИНСТРУМЕНТЫ',
            '❓ ЧАСТЫЕ ВОПРОСЫ'
        ]
    },
    '📚 СИСТЕМА СЕПЛИЦА: ОСНОВЫ': {
        'title': '📚 СИСТЕМА СЕПЛИЦА: ОСНОВЫ',
        'buttons': [
            'что такое система сеплица',
            'философия системы сеплица', 
            '4 ступени системы сеплица',
            '🔙 НАЗАД В ГЛАВНОЕ МЕНЮ'
        ]
    },
    '💪 СТУПЕНЬ 1: СЦЕПЛЕНИЕ': {
        'title': '💪 СТУПЕНЬ 1: СЦЕПЛЕНИЕ',
        'buttons': [
            'ступень 1 сцепление',
            'зарядка долголетия (33 упражнения)',
            'частые ошибки в зарядке',
            'связь осанки и молодости лица',
            '🔙 НАЗАД В ГЛАВНОЕ МЕНЮ'
        ]
    },
    '🙆 СТУПЕНЬ 2: ЕСТЕСТВЕННОСТЬ': {
        'title': '🙆 СТУПЕНЬ 2: ЕСТЕСТВЕННОСТЬ',
        'buttons': [
            'ступень 2 естественность',
            'лимфодренажный массаж лица',
            'расслабление миофасций',
            'тонизирование лицевых мышц',
            'массаж шейно-воротниковой зоны',
            'работа с триггерными точками',
            '🔙 НАЗАД В ГЛАВНОЕ МЕНЮ'
        ]
    },
    '🥗 СТУПЕНЬ 3: ПИТАНИЕ': {
        'title': '🥗 СТУПЕНЬ 3: ПИТАНИЕ',
        'buttons': [
            'ступень 3 питание',
            'что такое микробиом',
            'ферментированные продукты в сеплице',
            'пребиотики и клетчатка',
            'продукты, вредные для микробиома',
            'рецепты ферментированных продуктов',
            '🔙 НАЗАД В ГЛАВНОЕ МЕНЮ'
        ]
    },
    '🔬 СТУПЕНЬ 4: БИОХАКИНГ': {
        'title': '🔬 СТУПЕНЬ 4: ЗАБОТА О КЛЕТКАХ',
        'buttons': [
            'ступень 4 забота о клетках',
            'nmn (никотинамидмононуклеотид)',
            'омега-3 с упором на dha',
            'ресвератрол',
            'кверцетин',
            'косметика с ghk-cu (медный трипептид-1)',
            'как выбирать качественные добавки',
            '🔙 НАЗАД В ГЛАВНОЕ МЕНЮ'
        ]
    },
    '🎓 КУРС "ОМОЛОДИСЬ"': {
        'title': '🎓 КУРС "ОМОЛОДИСЬ"',
        'buttons': [
            'курс омолодись',
            'структура курса омолодись',
            'результаты курса омолодись',
            '🔙 НАЗАД В ГЛАВНОЕ МЕНЮ'
        ]
    },
    '🛠️ ПРАКТИЧЕСКИЕ ИНСТРУМЕНТЫ': {
        'title': '🛠️ ПРАКТИЧЕСКИЕ ИНСТРУМЕНТЫ',
        'buttons': [
            'приложение rejuvena',
            'фотодневник до/после',
            'как правильно делать селфи для отслеживания прогресса',
            '🔙 НАЗАД В ГЛАВНОЕ МЕНЮ'
        ]
    },
    '❓ ЧАСТЫЕ ВОПРОСЫ': {
        'title': '❓ ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ',
        'buttons': [
            'частые вопросы о системе',
            'противопоказания',
            'как совмещать с косметологией',
            'когда ждать первых результатов',
            '🔙 НАЗАД В ГЛАВНОЕ МЕНЮ'
        ]
    }
}

# Хранилище состояний пользователей
user_states = {}
# Хранилище режима обучения для автора
teaching_mode = {}

# ==================== ФУНКЦИИ РАБОТЫ С БАЗОЙ ЗНАНИЙ ====================
def load_knowledge():
    """Загрузка базы знаний из файла с улучшенной обработкой ошибок"""
    if os.path.exists(KNOWLEDGE_FILE):
        try:
            with open(KNOWLEDGE_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    logger.warning("Файл базы знаний пуст")
                    return {}
                
                # Пытаемся загрузить JSON
                knowledge = json.loads(content)
                logger.info(f"✅ База знаний успешно загружена: {len(knowledge)} записей")
                return knowledge
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}")
            # Показываем проблемную область
            lines = content.split('\n')
            error_line = e.lineno
            start = max(0, error_line - 2)
            end = min(len(lines), error_line + 2)
            logger.error(f"Проблемная область:\n{chr(10).join(lines[start:end])}")
            return {}
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки базы знаний: {e}")
            return {}
    else:
        logger.warning(f"📁 Файл {KNOWLEDGE_FILE} не найден")
        return {}

def save_knowledge(knowledge):
    """Сохранение базы знаний в файл"""
    try:
        with open(KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(knowledge, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения базы знаний: {e}")
        return False

def is_author(user):
    """Проверка, является ли пользователь автором"""
    return user.username == AUTHOR_USERNAME

def is_teaching_mode(user_id):
    """Проверка, находится ли пользователь в режиме обучения"""
    return teaching_mode.get(user_id, False)

def set_teaching_mode(user_id, mode):
    """Установка режима обучения"""
    teaching_mode[user_id] = mode
def normalize_key(key):
    """Нормализует ключ для поиска в базе знаний"""
    if not key:
        return ""
    
    # Приводим к нижнему регистру и убираем лишние пробелы
    normalized = key.strip().lower()
    
    # Убираем эмодзи и специальные символы для точного сопоставления
    normalized = re.sub(r'[🔙📚💪🙆🥗🔬🎓🛠️❓🏠*_`]', '', normalized)
    normalized = re.sub(r'назад в главное меню', '', normalized)
    normalized = normalized.strip()
    
    return normalized

def find_knowledge_by_key(key):
    """Находит знания по ключу с нормализацией"""
    knowledge = load_knowledge()
    
    if not knowledge:
        logger.warning("База знаний пуста")
        return None
    
    logger.info(f"Ищем ключ: '{key}'")
    logger.info(f"Доступные ключи в базе: {list(knowledge.keys())}")
    
    normalized_key = normalize_key(key)
    logger.info(f"Нормализованный ключ: '{normalized_key}'")
    
    # Прямое совпадение (оригинальный ключ)
    if key in knowledge:
        logger.info(f"Найдено прямое совпадение по оригинальному ключу: '{key}'")
        return knowledge[key]
    
    # Прямое совпадение (после нормализации)
    for knowledge_key, value in knowledge.items():
        if normalize_key(knowledge_key) == normalized_key:
            logger.info(f"Найдено прямое совпадение: '{knowledge_key}' -> '{normalized_key}'")
            return value
    
    # Частичное совпадение
    for knowledge_key, value in knowledge.items():
        norm_knowledge_key = normalize_key(knowledge_key)
        if normalized_key in norm_knowledge_key:
            logger.info(f"Найдено частичное совпадение: '{knowledge_key}' содержит '{normalized_key}'")
            return value
        if norm_knowledge_key in normalized_key:
            logger.info(f"Найдено частичное совпадение: '{normalized_key}' содержит '{knowledge_key}'")
            return value
    
    logger.warning(f"Ключ '{key}' (норм: '{normalized_key}') не найден в базе")
    return None

def safe_markdown_text(text):
    """Безопасно подготавливает текст для Markdown"""
    try:
        # Сначала очищаем от проблемных символов
        cleaned = clean_markdown(text)
        
        # Проверяем, не слишком ли длинный текст (ограничение Telegram)
        if len(cleaned) > 4000:
            cleaned = cleaned[:4000] + "..."
            
        return cleaned
    except Exception as e:
        logger.error(f"Ошибка очистки Markdown: {e}")
        # В случае ошибки возвращаем простой текст
        return re.sub(r'([*_`\\[\]])', '', text)

def extract_video_file_id(text):
    """Извлекает file_id видео из маркера [VIDEO:file_id]"""
    pattern = r'\[VIDEO:([^\]]+)\]'
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return None

def send_video_if_present(chat_id, text):
    """Отправляет видео, если в тексте есть маркер [VIDEO:file_id]"""
    file_id = extract_video_file_id(text)
    if file_id:
        try:
            bot.send_video(chat_id, file_id)
            logger.info(f"Видео отправлено с file_id: {file_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки видео {file_id}: {e}")
            return False
    return False

def send_safe_message(chat_id, text, reply_markup=None, parse_mode='Markdown'):
    """Безопасная отправка сообщения с автоматическим определением режима"""
    try:
        # Сначала отправляем видео, если есть
        send_video_if_present(chat_id, text)
        
        # Удаляем VIDEO маркер и "Содержание:" из текста
        clean_text = re.sub(r'\[VIDEO:[^\]]+\]', '', text)
        clean_text = re.sub(r'Содержание:\s*', '', clean_text)
        clean_text = clean_text.strip()
        
        # Если текст слишком длинный или содержит сложную разметку, отправляем как обычный текст
        if len(clean_text) > 3000 or clean_text.count('*') > 50 or clean_text.count('_') > 50:
            return bot.send_message(chat_id, clean_text, reply_markup=reply_markup, parse_mode=None)
        else:
            safe_text = safe_markdown_text(clean_text)
            return bot.send_message(chat_id, safe_text, reply_markup=reply_markup, parse_mode=parse_mode)
            
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        # Пробуем отправить без Markdown
        try:
            # Очищаем от VIDEO маркеров перед отправкой
            clean_text = re.sub(r'\[VIDEO:[^\]]+\]', '', text)
            clean_text = re.sub(r'Содержание:\s*', '', clean_text)
            clean_text = clean_text.strip()
            return bot.send_message(chat_id, clean_text, reply_markup=reply_markup, parse_mode=None)
        except Exception as e2:
            logger.error(f"Ошибка отправки без Markdown: {e2}")
            # Последняя попытка - разбиваем текст
            clean_text = re.sub(r'\[VIDEO:[^\]]+\]', '', text)
            clean_text = re.sub(r'Содержание:\s*', '', clean_text)
            clean_text = clean_text.strip()
            if len(clean_text) > 4000:
                part1 = clean_text[:4000]
                part2 = clean_text[4000:8000] if len(clean_text) > 8000 else clean_text[4000:]
                bot.send_message(chat_id, part1, reply_markup=reply_markup, parse_mode=None)
                if part2:
                    return bot.send_message(chat_id, part2, reply_markup=reply_markup, parse_mode=None)
            else:
                # Убираем всю разметку и отправляем
                final_text = re.sub(r'[*_`\[\]]', '', clean_text)
                return bot.send_message(chat_id, final_text, reply_markup=reply_markup, parse_mode=None)


# ==================== ФУНКЦИИ ОБРАБОТКИ ТЕКСТА ====================
def clean_markdown(text):
    """Очищает текст от некорректных Markdown-символов"""
    if not text:
        return ""
    
    # Заменяем проблемные символы Markdown
    cleaned_text = re.sub(r'([*_`\\[\]])', r'\\\1', text)
    
    # Убеждаемся, что все Markdown-сущности правильно закрыты
    # Убираем незакрытые **
    cleaned_text = re.sub(r'\*\*([^*]+)$', r'**\1**', cleaned_text)
    # Убираем незакрытые *
    cleaned_text = re.sub(r'\*([^*]+)$', r'*\1*', cleaned_text)
    # Убираем незакрывые __
    cleaned_text = re.sub(r'__([^_]+)$', r'__\1__', cleaned_text)
    # Убираем незакрытые `
    cleaned_text = re.sub(r'`([^`]+)$', r'`\1`', cleaned_text)
    
    return cleaned_text


# ==================== ФУНКЦИИ СОЗДАНИЯ КЛАВИАТУР ====================
def create_menu(menu_key='main'):
    """Создает клавиатуру для указанного меню"""
    if menu_key not in MENU_STRUCTURE:
        menu_key = 'main'
    
    menu = MENU_STRUCTURE[menu_key]
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Разбиваем кнопки на ряды по 2 кнопки
    buttons = menu['buttons']
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.add(buttons[i], buttons[i + 1])
        else:
            keyboard.add(buttons[i])
    
    return keyboard, menu['title']

def create_author_menu(menu_key='main'):
    """Создает меню для автора с дополнительной кнопкой обучения"""
    keyboard, title = create_menu(menu_key)
    if menu_key == 'main':
        keyboard.add('🔧 Обучение')
    return keyboard, title

def create_teaching_keyboard():
    """Создает клавиатуру для режима обучения"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add('📝 Показать базу знаний')
    keyboard.add('❌ Выйти из режима обучения')
    keyboard.add('🏠 Главное меню')
    return keyboard

def create_details_button(topic):
    """Создает кнопку 'Подробнее' для инлайн-клавиатуры с безопасным callback_data"""
    keyboard = InlineKeyboardMarkup()
    
    # Ограничиваем длину topic для callback_data (макс 64 байта)
    # Используем хэш или обрезаем слишком длинные темы
    if len(topic.encode('utf-8')) > 50:
        # Для длинных тем используем хэш
        import hashlib
        topic_hash = hashlib.md5(topic.encode('utf-8')).hexdigest()[:16]
        callback_data = f"det_{topic_hash}"
    else:
        # Для коротких тем используем обрезанную версию
        safe_topic = topic.replace(' ', '_')[:30]
        callback_data = f"det_{safe_topic}"
    
    keyboard.add(InlineKeyboardButton("📖 Подробнее", callback_data=callback_data))
    return keyboard

def create_quick_actions_keyboard():
    """Клавиатура для быстрых действий (из старого кода)"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = [
        KeyboardButton('1️⃣ Ступень 1'),
        KeyboardButton('2️⃣ Ступень 2'),
        KeyboardButton('3️⃣ Ступень 3'),
        KeyboardButton('4️⃣ Ступень 4'),
        KeyboardButton('🏠 Главное меню')
    ]
    
    keyboard.add(buttons[0], buttons[1])
    keyboard.add(buttons[2], buttons[3])
    keyboard.add(buttons[4])
    
    return keyboard

def create_main_keyboard():
    """Создает основную клавиатуру меню (из старого кода)"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = [
        KeyboardButton('🏃‍♂️ Упражнения'),
        KeyboardButton('💆‍♀️ Массажи'),
        KeyboardButton('🥗 Питание'),
        KeyboardButton('💊 Добавки'),
        KeyboardButton('📚 О системе'),
        KeyboardButton('❓ Помощь')
    ]
    
    keyboard.add(buttons[0], buttons[1])
    keyboard.add(buttons[2], buttons[3])
    keyboard.add(buttons[4], buttons[5])
    
    return keyboard

# ==================== ФУНКЦИИ AI ====================
def ask_deepseek(user_message):
    """Запрос к DeepSeek API с увеличенным лимитом токенов"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SEPLITSA_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7,
        "max_tokens": 2000,  # УВЕЛИЧИЛИ С 500 ДО 2000
        "stream": False
    }
    
    try:
        logger.info(f"Отправляем: {user_message}")
        response = requests.post(DEEPSEEK_URL, headers=headers, json=data, timeout=60)  # Увеличили таймаут
        logger.info(f"Статус: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            ai_response = response_data['choices'][0]['message']['content']
            return ai_response
        else:
            logger.error(f"Ошибка API: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return None

# ==================== ФУНКЦИИ УПРАВЛЕНИЯ СОСТОЯНИЕМ ====================
def get_user_menu(user_id):
    """Получает текущее меню пользователя"""
    return user_states.get(user_id, 'main')

def set_user_menu(user_id, menu_key):
    """Устанавливает текущее меню пользователя"""
    user_states[user_id] = menu_key

# ==================== ФУНКЦИИ ОТПРАВКИ СООБЩЕНИЙ ====================
def send_typing_action(chat_id, duration=3):
    """Показывает анимацию 'бот печатает'"""
    bot.send_chat_action(chat_id, 'typing')
    time.sleep(duration)

def send_processing_message(chat_id, message_text="🤔 Думаю над ответом..."):
    """Отправляет сообщение о процессе обработки"""
    return bot.send_message(chat_id, message_text)

def send_short_response_with_details(chat_id, topic, text, max_length=300):
    """Отправляет короткий ответ с кнопкой 'Подробнее'"""
    try:
        # Очищаем текст от Markdown для короткого ответа
        clean_text = re.sub(r'[*_`\[\]]', '', text)
        
        if len(clean_text) > max_length:
            short_text = clean_text[:max_length] + "..."
            message = bot.send_message(
                chat_id, 
                f"📋 {topic}\n\n{short_text}",
                reply_markup=create_details_button(topic),
                parse_mode=None  # Отправляем как простой текст
            )
            return message
        else:
            message = bot.send_message(
                chat_id, 
                f"📋 {topic}\n\n{clean_text}",
                parse_mode=None  # Отправляем как простой текст
            )
            return message
    except Exception as e:
        logger.error(f"Ошибка отправки короткого ответа: {e}")
        # Упрощенная отправка без кнопки
        short_text = text[:200] + "..." if len(text) > 200 else text
        return bot.send_message(
            chat_id, 
            f"📋 {topic}\n\n{short_text}",
            parse_mode=None
        )

def send_new_year_promo(chat_id):
    """Отправляет всплывающее объявление о новогодней акции"""
    promo_text = """
🎉 ✨ НОВОГОДНЯЯ АКЦИЯ ✨ 🎉

🎁 Закажи СЕГОДНЯ и получи скидку 10% на ВСЕ услуги следующего года!

⏰ СПЕШИТЕ! Предложение действует только в новогодние дни!

Это ваш шанс начать год с омоложения по специальной цене! 

Узнать больше и сделать заказ можно на нашем сайте 👇
    """
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🌐 Перейти на сайт", url="https://seplitsa.com"))
    keyboard.add(InlineKeyboardButton("❌ Закрыть", callback_data="close_promo"))
    
    try:
        bot.send_message(chat_id, promo_text, reply_markup=keyboard, parse_mode=None)
    except Exception as e:
        logger.error(f"Ошибка отправки промо: {e}")

# ==================== ОБРАБОТЧИКИ КОМАНД ====================
@bot.message_handler(commands=['start', 'menu', 'меню'])
def send_welcome(message):
    """Приветственное сообщение с меню"""
    user_id = message.from_user.id
    set_user_menu(user_id, 'main')
    set_teaching_mode(user_id, False)  # Выходим из режима обучения
    
    if is_author(message.from_user):
        keyboard, title = create_author_menu('main')
        welcome_text = """
👋 Привет, Алексей! Вы в режиме автора системы Сеплица.

Выберите раздел или нажмите '🔧 Обучение' для коррекции знаний.
        """
    else:
        keyboard, title = create_menu('main')
        welcome_text = """
👋 Добро пожаловать в «Сеплица-Эксперт»!

Я — ваш AI-консультант по системе естественного омоложения.

Выберите нужный раздел из меню ниже или просто задайте вопрос!
        """
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=keyboard)
    
    # Показываем новогоднее объявление о скидке
    time.sleep(0.5)  # Небольшая задержка для лучшего восприятия
    send_new_year_promo(message.chat.id)
@bot.message_handler(commands=['debug'])
def debug_command(message):
    """Отладочная команда для проверки поиска"""
    test_key = 'ступень 1 сцепление'
    knowledge_text = find_knowledge_by_key(test_key)
    
    if knowledge_text:
        response = f"✅ Ключ '{test_key}' найден!\n\nПервые 200 символов:\n{knowledge_text[:200]}..."
    else:
        response = f"❌ Ключ '{test_key}' не найден"
    
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['teach', 'обучение'])
def teach_command(message):
    """Режим обучения для автора"""
    if not is_author(message.from_user):
        bot.send_message(message.chat.id, "⛔ Эта команда доступна только автору системы.")
        return
    
    user_id = message.from_user.id
    set_teaching_mode(user_id, True)
    
    bot.send_message(message.chat.id,
                    "🔧 **РЕЖИМ ОБУЧЕНИЯ АКТИВИРОВАН**\n\n"
                    "Для добавления/коррекции знаний используйте формат:\n"
                    "```\n"
                    "ТЕМА: исправленный текст\n"
                    "```\n\n"
                    "Пример:\n"
                    "`упражнения: Добавлены новые упражнения для шеи...`\n\n"
                    "Доступные команды:\n"
                    "• 'показать' - просмотр текущих знаний\n"
                    "• 'выход' - выход из режима обучения\n"
                    "• 'главное меню' - возврат в основное меню",
                    reply_markup=create_teaching_keyboard(),
                    parse_mode='Markdown')

@bot.message_handler(func=lambda message: message.text == '🔧 Обучение')
def teach_mode(message):
    """Активация режима обучения через кнопку"""
    if not is_author(message.from_user):
        bot.send_message(message.chat.id, "⛔ Эта функция доступна только автору системы.")
        return
    teach_command(message)

@bot.message_handler(func=lambda message: message.text.lower() in ['показать', '📝 показать базу знаний'])
def show_knowledge(message):
    """Показать текущую базу знаний"""
    if not is_author(message.from_user):
        bot.send_message(message.chat.id, "⛔ Эта команда доступна только автору системы.")
        return
    
    knowledge = load_knowledge()
    if not knowledge:
        bot.send_message(message.chat.id, "📝 База знаний пуста.", reply_markup=create_teaching_keyboard())
        return
    
    response = "📚 **ТЕКУЩИЕ ЗНАНИЯ СИСТЕМЫ:**\n\n"
    for key, value in knowledge.items():
        response += f"**{key}:**\n{value}\n\n"
    
    if len(response) > 4000:
        # Если текст слишком длинный, разбиваем на части
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for part in parts:
            send_safe_message(message.chat.id, part, reply_markup=create_teaching_keyboard())
    else:
        send_safe_message(message.chat.id, response, reply_markup=create_teaching_keyboard())

@bot.message_handler(func=lambda message: message.text.lower() in ['выход', '❌ выйти из режима обучения', 'отмена', 'стоп'])
def exit_teaching_mode(message):
    """Выход из режима обучения"""
    user_id = message.from_user.id
    if not is_author(message.from_user):
        bot.send_message(message.chat.id, "⛔ Эта команда доступна только автору системы.")
        return
    
    set_teaching_mode(user_id, False)
    keyboard, title = create_author_menu('main')
    
    bot.send_message(message.chat.id, 
                    "✅ **Режим обучения завершен**\n\n"
                    "Вы вернулись в обычный режим работы.",
                    reply_markup=keyboard,
                    parse_mode='Markdown')

@bot.message_handler(func=lambda message: ':' in message.text and is_author(message.from_user) and is_teaching_mode(message.from_user.id))
def process_teaching(message):
    """Обработка добавления знаний в системе в режиме обучения"""
    if not is_author(message.from_user):
        return
    
    try:
        parts = message.text.split(':', 1)
        if len(parts) == 2:
            topic = parts[0].strip()
            knowledge_text = parts[1].strip()
            
            knowledge = load_knowledge()
            knowledge[topic] = knowledge_text
            if save_knowledge(knowledge):
                logger.info(f"Знания обновлены: {topic}")
                bot.send_message(message.chat.id, 
                               f"✅ **Знания обновлены!**\n\n"
                               f"**Тема:** {topic}\n"
                               f"**Содержание:** {knowledge_text}\n\n"
                               f"Продолжайте добавлять знания или нажмите '❌ Выйти из режима обучения'",
                               reply_markup=create_teaching_keyboard(),
                               parse_mode='Markdown')
            else:
                bot.send_message(message.chat.id, 
                               "❌ Ошибка сохранения знаний",
                               reply_markup=create_teaching_keyboard())
        else:
            bot.send_message(message.chat.id, 
                           "❌ Неверный формат. Используйте:\n`ТЕМА: текст`",
                           reply_markup=create_teaching_keyboard())
    except Exception as e:
        logger.error(f"Ошибка обучения: {e}")
        bot.send_message(message.chat.id, 
                       f"❌ Ошибка: {e}",
                       reply_markup=create_teaching_keyboard())

# ==================== ОБРАБОТЧИКИ НАВИГАЦИИ ====================
@bot.message_handler(func=lambda message: message.text in ['🔙 НАЗАД В ГЛАВНОЕ МЕНЮ', '🏠 Главное меню', 'главное меню'])
def handle_back(message):
    """Обработка кнопки Назад и Главное меню"""
    user_id = message.from_user.id
    set_user_menu(user_id, 'main')
    set_teaching_mode(user_id, False)  # Выходим из режима обучения
    
    if is_author(message.from_user):
        keyboard, title = create_author_menu('main')
    else:
        keyboard, title = create_menu('main')
    
    bot.send_message(message.chat.id, "🏠 Возвращаемся в главное меню:", reply_markup=keyboard)

@bot.message_handler(func=lambda message: message.text in MENU_STRUCTURE)
def handle_menu_navigation(message):
    """Навигация по меню"""
    user_id = message.from_user.id
    menu_key = message.text
    
    # Выходим из режима обучения при переходе по меню
    set_teaching_mode(user_id, False)
    
    logger.info(f"Пользователь {user_id} переходит в меню: {menu_key}")
    set_user_menu(user_id, menu_key)
    
    if is_author(message.from_user):
        keyboard, title = create_author_menu(menu_key)
    else:
        keyboard, title = create_menu(menu_key)
    
    bot.send_message(message.chat.id, f"{title}:", reply_markup=keyboard)

# ==================== ОБРАБОТЧИКИ КОНТЕНТА ====================
@bot.message_handler(func=lambda message: message.text in ['📚 О системе', '❓ Помощь'])
def about_system(message):
    """Информация о системе"""
    user_id = message.from_user.id
    set_teaching_mode(user_id, False)  # Выходим из режима обучения
    
    about_text = """
📚 **СИСТЕМА «СЕПЛИЦА»**

4 ступени естественного омоложения:

1. 🏃‍♂️ **СЦЕПЛЕНИЕ** - Упражнения для осанки
2. 💆‍♀️ **ЕСТЕСТВЕННОСТЬ** - Массажи лица и шеи
3. 🥗 **ПИТАНИЕ** - Ферментированные продукты  
4. 💊 **ЗАБОТА О КЛЕТКАХ** - Добавки (NMN, Омега-3 и др.)

Выберите раздел для подробной информации!
    """
    
    send_safe_message(message.chat.id, about_text, parse_mode='Markdown')
    

@bot.message_handler(func=lambda message: message.text in ['🏃‍♂️ Упражнения', '1️⃣ Ступень 1'])
def exercises_handler(message):
    """Обработчик упражнений с анимацией"""
    user_id = message.from_user.id
    set_teaching_mode(user_id, False)  # Выходим из режима обучения
    
    send_typing_action(message.chat.id)
    processing_msg = send_processing_message(message.chat.id, "💭 Составляю ответ по упражнениям...")
    
    response = ask_deepseek("Расскажи подробно о первой ступени Сеплицы: упражнения для осанки и фасций")
    
    bot.delete_message(message.chat.id, processing_msg.message_id)
    
    if response:
        send_short_response_with_details(message.chat.id, "🏃‍♂️ Упражнения Сеплицы", response)
    else:
        bot.send_message(message.chat.id, "⚠️ Ошибка связи с AI")

# ... остальные обработчики контента (массажи, питание, добавки) остаются без изменений ...

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Обработка всех остальных сообщений"""
    user_id = message.from_user.id
    current_menu = get_user_menu(user_id)
    
    logger.info(f"Получено сообщение от {user_id}: '{message.text}'")
    
    # Сначала проверяем базу знаний для ВСЕХ сообщений
    knowledge_text = find_knowledge_by_key(message.text)
    if knowledge_text:
        logger.info(f"Найдено в базе знаний для: '{message.text}'")
        send_safe_message(
            message.chat.id,
            f"📋 **{message.text}**\n\n{knowledge_text}",
            parse_mode='Markdown'
        )
        return
    
    # Проверяем, является ли сообщение темой из текущего меню
    if current_menu in MENU_STRUCTURE:
        current_buttons = MENU_STRUCTURE[current_menu]['buttons']
        if message.text in current_buttons and message.text not in ['🔙 НАЗАД В ГЛАВНОЕ МЕНЮ', '🏠 Главное меню']:
            
            # Если темы нет в базе, используем AI
            logger.info(f"Отправляем запрос к AI для меню: '{message.text}'")
            bot.send_chat_action(message.chat.id, 'typing')
            response = ask_deepseek(message.text)
            
            if response:
                send_safe_message(
                    message.chat.id,
                    response,
                    parse_mode='Markdown'
                )
            else:
                send_safe_message(
                    message.chat.id,
                    f"📋 **{message.text}**\n\nИнформация по этой теме будет добавлена в ближайшее время.",
                    parse_mode='Markdown'
                )
            return
    
    # AI запрос для любых других сообщений
    logger.info(f"Отправляем запрос к AI: '{message.text}'")
    bot.send_chat_action(message.chat.id, 'typing')
    response = ask_deepseek(message.text)
    
    if response:
        logger.info("AI ответ получен")
        send_safe_message(message.chat.id, response, parse_mode='Markdown')
    else:
        logger.error("AI не ответил")
        bot.send_message(
            message.chat.id,
            "🤖 Используйте кнопки меню для получения конкретной информации о системе Сеплица."
        )

@bot.callback_query_handler(func=lambda call: call.data == 'close_promo')
def close_promo(call):
    """Закрытие объявления о новогодней акции"""
    bot.answer_callback_query(call.id, "✅ Объявление закрыто")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.error(f"Ошибка при удалении объявления: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('det_'))
def handle_details(call):
    """Обработка кнопки 'Подробнее'"""
    bot.answer_callback_query(call.id)
    
    callback_data = call.data.replace('det_', '')
    
    # Восстанавливаем оригинальную тему из текста сообщения
    # Ищем тему в тексте сообщения, из которого была нажата кнопка
    message_text = call.message.text
    if '📋' in message_text:
        # Извлекаем тему из формата "📋 ТЕМА\n\nтекст..."
        topic = message_text.split('\n\n')[0].replace('📋 ', '').strip()
    else:
        # Альтернативный способ - используем callback_data для поиска
        topic = callback_data
    
    logger.info(f"Запрошены подробности по теме: '{topic}'")
    
    # Показываем анимацию загрузки
    send_typing_action(call.message.chat.id, 1)
    
    # Ищем в базе знаний с нормализацией
    knowledge_text = find_knowledge_by_key(topic)
    if knowledge_text:
        detailed_response = f"📖 **{topic}:**\n\n{knowledge_text}"
        send_safe_message(call.message.chat.id, detailed_response)
    else:
        # Если нет в базе, запрашиваем у AI
        processing_msg = send_processing_message(call.message.chat.id, "💭 Запрашиваю подробную информацию...")
        response = ask_deepseek(f"Расскажи подробно о {topic} в контексте системы Сеплица")
        bot.delete_message(call.message.chat.id, processing_msg.message_id)
        
        if response:
            send_safe_message(call.message.chat.id, f"📖 **{topic}:**\n\n{response}")
        else:
            bot.send_message(call.message.chat.id, "❌ Информация по этой теме временно недоступна.")
# ==================== ЗАПУСК БОТА ====================
if __name__ == "__main__":
    logger.info("🚀 Бот Сеплица запускается с улучшенной системой...")
    
    # Загружаем и логируем информацию о базе знаний
    knowledge = load_knowledge()
    logger.info(f"📚 Загружено тем из базы знаний: {len(knowledge)}")
    if knowledge:
        logger.info(f"📋 Темы в базе: {list(knowledge.keys())}")
    
    # Логируем структуру меню
    logger.info("🏗️ Структура меню:")
    for menu_key, menu_data in MENU_STRUCTURE.items():
        logger.info(f"  {menu_key} -> {len(menu_data['buttons'])} кнопок")
    
    bot.polling(none_stop=True, timeout=60)