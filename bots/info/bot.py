import telebot
import requests
import json
import os
import logging
import time
import re
import hashlib
import gspread
from google.oauth2.service_account import Credentials
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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
TELEGRAM_TOKEN = "7372636777:AAGZULVuDbnHh6GUE6atSNaReOEqdrK5LZg"
DEEPSEEK_API_KEY = "sk-030c8e9fbbb642a0b2850318ffad64a1"
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
AUTHOR_USERNAME = "alexpina76"
KNOWLEDGE_FILE = "seplitsa_info_knowledge.json"
USER_DATA_FILE = "seplitsa_info_user_data.json"

# Настройки Google Sheets
GOOGLE_SHEETS_CREDENTIALS = "seplitsa-credentials.json"  # Файл с ключами API
GOOGLE_SHEET_NAME = "Сеплица - База подписчиков"

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== ПРОМПТ СЕПЛИЦА ====================
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
try:
    bot.delete_webhook()
    logger.info("✅ Вебхук удален")
except Exception as e:
    logger.info(f"ℹ️ Вебхук не активен: {e}")

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
            'кверцeтин',
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
user_data = {}
user_progress = {}
teaching_mode = {}
data_collection_mode = {}

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
                
                knowledge = json.loads(content)
                logger.info(f"✅ База знаний успешно загружена: {len(knowledge)} записей")
                return knowledge
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}")
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

def load_user_data():
    """Загрузка данных пользователей"""
    global user_data, user_progress
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                user_data = data.get('user_data', {})
                user_progress = data.get('user_progress', {})
                logger.info(f"✅ Данные пользователей загружены: {len(user_data)} пользователей")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки данных пользователей: {e}")
            user_data = {}
            user_progress = {}

def save_user_data():
    """Сохранение данных пользователей"""
    try:
        data = {
            'user_data': user_data,
            'user_progress': user_progress
        }
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("✅ Данные пользователей сохранены")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения данных пользователей: {e}")
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

def is_data_collection_mode(user_id):
    """Проверка, находится ли пользователь в режиме сбора данных"""
    return data_collection_mode.get(user_id, False)

def set_data_collection_mode(user_id, mode):
    """Установка режима сбора данных"""
    data_collection_mode[user_id] = mode

# ==================== СИСТЕМА ЗВАНИЙ И ПРОГРЕССА ====================
def init_user_progress(user_id):
    """Инициализация прогресса пользователя"""
    if user_id not in user_progress:
        user_progress[user_id] = {
            'menus_visited': set(),
            'topics_read': set(),
            'details_clicks': 0,
            'messages_scrolled': set(),
            'current_rank': 'novice',
            'registration_date': datetime.now().isoformat(),
            'data_collected': False
        }

def update_user_progress(user_id, progress_type, value=None):
    """Обновление прогресса пользователя"""
    init_user_progress(user_id)
    
    if progress_type == 'menu_visited':
        user_progress[user_id]['menus_visited'].add(value)
    elif progress_type == 'topic_read':
        user_progress[user_id]['topics_read'].add(value)
    elif progress_type == 'details_click':
        user_progress[user_id]['details_clicks'] += 1
    elif progress_type == 'message_scrolled':
        user_progress[user_id]['messages_scrolled'].add(value)
    
    # Проверяем повышение звания
    check_rank_progression(user_id)
    save_user_data()

def check_rank_progression(user_id):
    """Проверка и обновление звания пользователя"""
    progress = user_progress[user_id]
    
    menus_count = len(progress['menus_visited'])
    topics_count = len(progress['topics_read'])
    details_count = progress['details_clicks']
    
    current_rank = progress['current_rank']
    
    if current_rank == 'novice' and \
       menus_count >= RANK_REQUIREMENTS['knowledgeable']['menus_visited'] and \
       topics_count >= RANK_REQUIREMENTS['knowledgeable']['topics_read'] and \
       details_count >= RANK_REQUIREMENTS['knowledgeable']['details_clicks']:
        progress['current_rank'] = 'knowledgeable'
        return USER_RANKS['knowledgeable']
    
    elif current_rank == 'knowledgeable' and \
         menus_count >= RANK_REQUIREMENTS['expert']['menus_visited'] and \
         topics_count >= RANK_REQUIREMENTS['expert']['topics_read'] and \
         details_count >= RANK_REQUIREMENTS['expert']['details_clicks']:
        progress['current_rank'] = 'expert'
        return USER_RANKS['expert']
    
    return None

def get_user_rank(user_id):
    """Получение текущего звания пользователя"""
    init_user_progress(user_id)
    return USER_RANKS[user_progress[user_id]['current_rank']]

def get_user_progress_stats(user_id):
    """Получение статистики прогресса пользователя"""
    init_user_progress(user_id)
    progress = user_progress[user_id]
    
    current_rank = progress['current_rank']
    next_rank = None
    progress_percent = 0
    
    if current_rank == 'novice':
        next_rank = 'knowledgeable'
        req = RANK_REQUIREMENTS['knowledgeable']
        progress_percent = min(100, int(
            (len(progress['menus_visited']) / req['menus_visited'] * 30 +
             len(progress['topics_read']) / req['topics_read'] * 40 +
             progress['details_clicks'] / req['details_clicks'] * 30)
        ))
    elif current_rank == 'knowledgeable':
        next_rank = 'expert'
        req = RANK_REQUIREMENTS['expert']
        progress_percent = min(100, int(
            (len(progress['menus_visited']) / req['menus_visited'] * 30 +
             len(progress['topics_read']) / req['topics_read'] * 40 +
             progress['details_clicks'] / req['details_clicks'] * 30)
        ))
    else:
        progress_percent = 100
    
    return {
        'current_rank': USER_RANKS[current_rank],
        'next_rank': USER_RANKS[next_rank] if next_rank else None,
        'progress_percent': progress_percent,
        'menus_visited': len(progress['menus_visited']),
        'topics_read': len(progress['topics_read']),
        'details_clicks': progress['details_clicks']
    }

# ==================== GOOGLE SHEETS ИНТЕГРАЦИЯ ====================
def save_to_google_sheets(user_info):
    """Сохранение данных пользователя в Google Sheets"""
    try:
        # Проверяем наличие файла с учетными данными
        if not os.path.exists(GOOGLE_SHEETS_CREDENTIALS):
            logger.warning("Файл учетных данных Google Sheets не найден")
            return False
        
        # Авторизация
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(GOOGLE_SHEETS_CREDENTIALS, scopes=scope)
        client = gspread.authorize(creds)
        
        # Открываем таблицу
        sheet = client.open(GOOGLE_SHEET_NAME).sheet1
        
        # Подготавливаем данные
        row_data = [
            user_info.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            user_info.get('user_id', ''),
            user_info.get('username', ''),
            user_info.get('first_name', ''),
            user_info.get('last_name', ''),
            user_info.get('age', ''),
            user_info.get('gender', ''),
            user_info.get('gym_attendance', ''),
            user_info.get('gym_frequency', ''),
            user_info.get('phone_type', ''),
            user_info.get('financial_status', ''),
            user_info.get('motivation_level', ''),
            user_info.get('current_rank', ''),
            user_info.get('registration_date', '')
        ]
        
        # Добавляем строку
        sheet.append_row(row_data)
        logger.info(f"✅ Данные пользователя {user_info.get('user_id')} сохранены в Google Sheets")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения в Google Sheets: {e}")
        return False

def collect_user_data_step_by_step(user_id, message_text):
    """Пошаговый сбор данных пользователя"""
    if user_id not in user_data:
        user_data[user_id] = {
            'user_id': user_id,
            'registration_date': datetime.now().isoformat(),
            'current_step': 0
        }
    
    current_step = user_data[user_id].get('current_step', 0)
    
    if current_step == 0:
        # Шаг 1: Имя
        user_data[user_id]['first_name'] = message_text
        user_data[user_id]['current_step'] = 1
        return "📝 Отлично! А сколько вам лет?"
    
    elif current_step == 1:
        # Шаг 2: Возраст
        if message_text.isdigit() and 10 <= int(message_text) <= 100:
            user_data[user_id]['age'] = message_text
            user_data[user_id]['current_step'] = 2
            return "👤 Выберите ваш пол:", create_gender_keyboard()
        else:
            return "📝 Пожалуйста, введите корректный возраст (число от 10 до 100):"
    
    elif current_step == 2:
        # Шаг 3: Пол
        if message_text in ['Мужской', 'Женский']:
            user_data[user_id]['gender'] = message_text
            user_data[user_id]['current_step'] = 3
            return "🏋️ Вы ходите в спортзал?", create_gym_keyboard()
        else:
            return "👤 Пожалуйста, выберите пол из предложенных вариантов:"
    
    elif current_step == 3:
        # Шаг 4: Посещение спортзала
        if message_text in ['Да, регулярно', 'Да, иногда', 'Нет']:
            user_data[user_id]['gym_attendance'] = message_text
            
            if message_text != 'Нет':
                user_data[user_id]['current_step'] = 4
                return "📅 Как часто вы ходите в спортзал?", create_gym_frequency_keyboard()
            else:
                user_data[user_id]['gym_frequency'] = 'Не хожу'
                user_data[user_id]['current_step'] = 5
                return "📱 Какой у вас тип телефона?", create_phone_keyboard()
        else:
            return "🏋️ Пожалуйста, выберите вариант из предложенных:"
    
    elif current_step == 4:
        # Шаг 5: Частота посещения спортзала
        if message_text in ['1-2 раза в неделю', '3-4 раза в неделю', '5+ раз в неделю']:
            user_data[user_id]['gym_frequency'] = message_text
            user_data[user_id]['current_step'] = 5
            return "📱 Какой у вас тип телефона?", create_phone_keyboard()
        else:
            return "📅 Пожалуйста, выберите частоту из предложенных вариантов:"
    
    elif current_step == 5:
        # Шаг 6: Тип телефона
        if message_text in ['iPhone', 'Android']:
            user_data[user_id]['phone_type'] = message_text
            user_data[user_id]['current_step'] = 6
            return "💎 Как бы вы описали свое финансовое положение?", create_financial_keyboard()
        else:
            return "📱 Пожалуйста, выберите тип телефона:"
    
    elif current_step == 6:
        # Шаг 7: Финансовое положение
        if message_text in ['Экономлю', 'Стабильно', 'Могу позволить себе многое', 'Не ограничен']:
            user_data[user_id]['financial_status'] = message_text
            user_data[user_id]['current_step'] = 7
            return "🎯 Насколько вы настроены на работу над собой?", create_motivation_keyboard()
        else:
            return "💎 Пожалуйста, выберите вариант из предложенных:"
    
    elif current_step == 7:
        # Шаг 8: Настроенность на работу
        if message_text in ['Только знакомлюсь', 'Готов изучать', 'Очень настроен', 'Уже работаю над собой']:
            user_data[user_id]['motivation_level'] = message_text
            user_data[user_id]['current_step'] = 8
            
            # Завершаем сбор данных
            user_data[user_id]['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user_data[user_id]['current_rank'] = get_user_rank(user_id)
            
            # Сохраняем в Google Sheets
            save_to_google_sheets(user_data[user_id])
            
            # Отмечаем в прогрессе
            user_progress[user_id]['data_collected'] = True
            
            set_data_collection_mode(user_id, False)
            save_user_data()
            
            stats = get_user_progress_stats(user_id)
            
            return (f"✅ **Спасибо! Анкета завершена!**\n\n"
                   f"Теперь вы официально в системе Сеплица!\n"
                   f"Ваше текущее звание: **{stats['current_rank']}**\n\n"
                   f"Изучайте систему, повышайте звание и достигайте результатов! 🎯")
    
    return None

def create_gender_keyboard():
    """Клавиатура для выбора пола"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add('Мужской', 'Женский')
    return keyboard

def create_gym_keyboard():
    """Клавиатура для вопроса о спортзале"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add('Да, регулярно', 'Да, иногда')
    keyboard.add('Нет')
    return keyboard

def create_gym_frequency_keyboard():
    """Клавиатура для частоты посещения спортзала"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add('1-2 раза в неделю', '3-4 раза в неделю')
    keyboard.add('5+ раз в неделю')
    return keyboard

def create_phone_keyboard():
    """Клавиатура для типа телефона"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add('iPhone', 'Android')
    return keyboard

def create_financial_keyboard():
    """Клавиатура для финансового положения"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add('Экономлю', 'Стабильно')
    keyboard.add('Могу позволить себе многое', 'Не ограничен')
    return keyboard

def create_motivation_keyboard():
    """Клавиатура для настроенности на работу"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add('Только знакомлюсь', 'Готов изучать')
    keyboard.add('Очень настроен', 'Уже работаю над собой')
    return keyboard

# ==================== ОСТАЛЬНЫЕ ФУНКЦИИ (без изменений) ====================
def normalize_key(key):
    """Нормализует ключ для поиска в базе знаний"""
    if not key:
        return ""
    
    normalized = key.strip().lower()
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

def send_safe_message(chat_id, text, reply_markup=None, parse_mode='Markdown'):
    """Безопасная отправка сообщения с автоматическим определением режима"""
    try:
        if len(text) > 3000 or text.count('*') > 50 or text.count('_') > 50:
            return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=None)
        else:
            safe_text = safe_markdown_text(text)
            return bot.send_message(chat_id, safe_text, reply_markup=reply_markup, parse_mode=parse_mode)
            
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        try:
            return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=None)
        except Exception as e2:
            logger.error(f"Ошибка отправки без Markdown: {e2}")
            if len(text) > 4000:
                part1 = text[:4000]
                part2 = text[4000:8000] if len(text) > 8000 else text[4000:]
                bot.send_message(chat_id, part1, reply_markup=reply_markup, parse_mode=None)
                if part2:
                    return bot.send_message(chat_id, part2, reply_markup=reply_markup, parse_mode=None)
            else:
                clean_text = re.sub(r'[*_`\[\]]', '', text)
                return bot.send_message(chat_id, clean_text, reply_markup=reply_markup, parse_mode=None)

def create_menu(menu_key='main'):
    """Создает клавиатуру для указанного меню"""
    if menu_key not in MENU_STRUCTURE:
        menu_key = 'main'
    
    menu = MENU_STRUCTURE[menu_key]
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
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
    
    if len(topic.encode('utf-8')) > 50:
        topic_hash = hashlib.md5(topic.encode('utf-8')).hexdigest()[:16]
        callback_data = f"det_{topic_hash}"
    else:
        safe_topic = topic.replace(' ', '_')[:30]
        callback_data = f"det_{safe_topic}"
    
    keyboard.add(InlineKeyboardButton("📖 Подробнее", callback_data=callback_data))
    return keyboard

def ask_deepseek(user_message):
    """Запрос к DeepSeek API с увеличенным таймаутом"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SEPLITSA_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        "stream": False,
        "temperature": 0.7,
        "max_tokens": 4000
    }
    
    try:
        response = requests.post(DEEPSEEK_URL, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        logger.error("Таймаут запроса к DeepSeek API")
        return "Извините, сервис временно недоступен. Пожалуйста, попробуйте позже."
    except Exception as e:
        logger.error(f"Ошибка запроса к DeepSeek: {e}")
        return "Произошла ошибка при обработке запроса. Пожалуйста, попробуйте еще раз."

def handle_author_command(message):
    """Обработка команд автора"""
    user = message.from_user
    if not is_author(user):
        return False
    
    if message.text == '🔧 Обучение':
        set_teaching_mode(user.id, True)
        send_safe_message(message.chat.id, 
                         "🔧 **РЕЖИМ ОБУЧЕНИЯ АКТИВИРОВАН**\n\n"
                         "Доступные команды:\n"
                         "• 📝 Показать базу знаний\n"
                         "• ❌ Выйти из режима обучения\n\n"
                         "Для добавления знаний в базу просто отправьте текст в формате:\n"
                         "`Ключ: Значение`", 
                         reply_markup=create_teaching_keyboard())
        return True
    
    if is_teaching_mode(user.id):
        if message.text == '❌ Выйти из режима обучения':
            set_teaching_mode(user.id, False)
            keyboard, title = create_author_menu()
            send_safe_message(message.chat.id, "✅ Режим обучения деактивирован", reply_markup=keyboard)
            return True
        
        elif message.text == '📝 Показать базу знаний':
            knowledge = load_knowledge()
            if knowledge:
                knowledge_text = "📚 **ТЕКУЩАЯ БАЗА ЗНАНИЙ:**\n\n"
                for key, value in knowledge.items():
                    knowledge_text += f"**{key}:**\n{value[:200]}...\n\n"
                send_safe_message(message.chat.id, knowledge_text[:4000])
            else:
                send_safe_message(message.chat.id, "❌ База знаний пуста")
            return True
        
        elif ':' in message.text:
            parts = message.text.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                
                knowledge = load_knowledge()
                knowledge[key] = value
                
                if save_knowledge(knowledge):
                    send_safe_message(message.chat.id, f"✅ Знание добавлено в базу:\n**{key}**")
                else:
                    send_safe_message(message.chat.id, "❌ Ошибка сохранения в базу знаний")
            return True
    
    return False

# ==================== ОБРАБОТЧИКИ СООБЩЕНИЙ ====================
@bot.message_handler(commands=['start'])
def handle_start(message):
    """Обработчик команды /start"""
    user = message.from_user
    
    # Инициализация прогресса пользователя
    init_user_progress(user.id)
    
    # Начинаем сбор данных
    set_data_collection_mode(user.id, True)
    
    welcome_text = (
        "🌟 **Добро пожаловать в систему СЕПЛИЦА!** 🌟\n\n"
        "Я — ваш AI-консультант по естественному омоложению.\n\n"
        "Прежде чем начать, давайте познакомимся поближе!\n"
        "📝 Как вас зовут?"
    )
    
    send_safe_message(message.chat.id, welcome_text)

@bot.message_handler(commands=['complete_profile'])
def handle_complete_profile(message):
    """Команда для завершения регистрации"""
    user_id = message.from_user.id
    
    if is_user_profile_complete(user_id):
        send_safe_message(message.chat.id, "✅ Ваш профиль уже завершен!")
        # Показываем главное меню
        if is_author(message.from_user):
            keyboard, title = create_author_menu('main')
        else:
            keyboard, title = create_menu('main')
        send_safe_message(message.chat.id, title, reply_markup=keyboard)
        return
    
    set_data_collection_mode(user_id, True)
    send_safe_message(message.chat.id, 
                     "📝 Давайте завершим вашу регистрацию!\n\n"
                     "Как вас зовут?")

@bot.message_handler(func=lambda message: is_data_collection_mode(message.from_user.id))
def handle_data_collection(message):
    """Обработчик сбора данных пользователя"""
    user_id = message.from_user.id
    
    # 🔥 ВАЖНОЕ ИСПРАВЛЕНИЕ: Проверяем команды для выхода из режима
    if message.text.startswith('/'):
        set_data_collection_mode(user_id, False)
        send_safe_message(message.chat.id, 
                         "❌ Режим сбора данных отменен.\n"
                         "Используйте /complete_profile чтобы продолжить позже.")
        return
    
    response = collect_user_data_step_by_step(user_id, message.text)
    if response:
        if isinstance(response, tuple):
            send_safe_message(message.chat.id, response[0], reply_markup=response[1])
        else:
            send_safe_message(message.chat.id, response)
    else:
        send_safe_message(message.chat.id, "Пожалуйста, ответьте на предыдущий вопрос:")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """Основной обработчик сообщений"""
    user = message.from_user
    user_id = user.id
    
    # 🔥 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем, не в режиме ли сбора данных
    if is_data_collection_mode(user_id):
        handle_data_collection(message)
        return
    
    # 🔥 Проверяем, завершена ли анкета
    if not is_user_profile_complete(user_id):
        # Показываем напоминание и меню
        reminder_text = (
            "📋 *Завершите регистрацию для полного доступа!*\n\n"
            "Чтобы получить персонализированные рекомендации, завершите анкету:\n"
            "`/complete_profile`\n\n"
            "Но вы можете продолжить изучение системы! 🎯"
        )
        send_safe_message(message.chat.id, reminder_text)
        
        # ВСЕГДА показываем меню, даже если анкета не завершена
        if is_author(user):
            keyboard, title = create_author_menu('main')
        else:
            keyboard, title = create_menu('main')
        send_safe_message(message.chat.id, title, reply_markup=keyboard)
        return
    
    # Обработка команд автора
    if handle_author_command(message):
        return
    
    # Обработка обычных сообщений пользователя
    user_message = message.text.strip()
    
    # Обновляем прогресс для сообщений с кнопкой "Подробнее"
    if user_message.endswith('_details'):
        topic = user_message[:-8]
        update_user_progress(user.id, 'details_click')
        user_message = topic
    
    # Определяем меню
    current_menu = 'main'
    for menu_key, menu_data in MENU_STRUCTURE.items():
        if user_message in menu_data['buttons']:
            current_menu = menu_key
            break
    
    # Обработка навигации по меню
    if user_message in ['🏠 Главное меню', '🔙 НАЗАД В ГЛАВНОЕ МЕНЮ']:
        current_menu = 'main'
    
    # Обновляем прогресс посещения меню
    if current_menu != 'main':
        update_user_progress(user.id, 'menu_visited', current_menu)
    
    # Поиск в базе знаний
    knowledge = find_knowledge_by_key(user_message)
    
    if knowledge:
        # Обновляем прогресс прочтения темы
        update_user_progress(user.id, 'topic_read', user_message)
        
        # Отправляем ответ с кнопкой "Подробнее"
        bot.send_chat_action(message.chat.id, 'typing')
        
        response = knowledge
        if len(response) > 400:
            short_response = response[:400] + "..."
            send_safe_message(message.chat.id, short_response, 
                            reply_markup=create_details_button(user_message))
        else:
            send_safe_message(message.chat.id, response)
        
        # Создаем меню
        if is_author(user):
            keyboard, title = create_author_menu(current_menu)
        else:
            keyboard, title = create_menu(current_menu)
        
        send_safe_message(message.chat.id, title, reply_markup=keyboard)
        
    else:
        # Если не найдено в базе знаний, используем AI
        bot.send_chat_action(message.chat.id, 'typing')
        
        # ИНИЦИИРУЕМ СБОР ДАННЫХ ВО ВРЕМЯ ОЖИДАНИЯ AI
        if user.id not in user_data or not user_data[user.id].get('data_collected', False):
            set_data_collection_mode(user.id, True)
            send_safe_message(message.chat.id, 
                            "⏳ Пока AI готовит ответ, давайте завершим вашу анкету!\n\n"
                            "📝 Как вас зовут?")
            return
        
        # Если данные уже собраны, используем AI
        ai_response = ask_deepseek(user_message)
        
        # Отправляем ответ AI
        if len(ai_response) > 400:
            short_response = ai_response[:400] + "..."
            send_safe_message(message.chat.id, short_response, 
                            reply_markup=create_details_button(user_message))
        else:
            send_safe_message(message.chat.id, ai_response)
        
        # Создаем меню
        if is_author(user):
            keyboard, title = create_author_menu(current_menu)
        else:
            keyboard, title = create_menu(current_menu)
        
        send_safe_message(message.chat.id, title, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('det_'))
def handle_details_callback(call):
    """Обработчик нажатия на кнопку 'Подробнее'"""
    try:
        topic_key = call.data[4:]  # Убираем префикс 'det_'
        
        # Ищем оригинальный ключ по хешу
        knowledge = load_knowledge()
        found_topic = None
        
        for key in knowledge.keys():
            if len(key.encode('utf-8')) > 50:
                key_hash = hashlib.md5(key.encode('utf-8')).hexdigest()[:16]
                if key_hash == topic_key:
                    found_topic = key
                    break
            else:
                safe_key = key.replace(' ', '_')[:30]
                if safe_key == topic_key:
                    found_topic = key
                    break
        
        if found_topic:
            full_response = knowledge[found_topic]
            
            # Обновляем прогресс (промотал до конца)
            update_user_progress(call.from_user.id, 'message_scrolled', found_topic)
            
            # Отправляем полный ответ
            send_safe_message(call.message.chat.id, full_response)
            
            # Проверяем повышение звания
            new_rank = check_rank_progression(call.from_user.id)
            if new_rank:
                send_safe_message(call.message.chat.id, 
                                f"🎉 **Поздравляем! Вы достигли нового звания: {new_rank}!**")
            
        else:
            send_safe_message(call.message.chat.id, "Извините, не удалось найти подробную информацию.")
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка обработки callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")

@bot.message_handler(commands=['progress'])
def handle_progress_command(message):
    """Показывает прогресс пользователя и текущее звание"""
    user_id = message.from_user.id
    stats = get_user_progress_stats(user_id)
    
    progress_text = (
        f"🏆 **ВАШ ПРОГРЕСС В СИСТЕМЕ СЕПЛИЦА**\n\n"
        f"📊 **Текущее звание:** {stats['current_rank']}\n"
        f"✅ Изучено меню: {stats['menus_visited']}\n"
        f"📚 Прочитано тем: {stats['topics_read']}\n"
        f"🔍 Нажатий 'Подробнее': {stats['details_clicks']}\n\n"
    )
    
    if stats['next_rank']:
        progress_text += (
            f"🎯 **Следующее звание:** {stats['next_rank']}\n"
            f"📈 Прогресс: {stats['progress_percent']}%\n\n"
            f"Продолжайте изучать систему для повышения звания!"
        )
    else:
        progress_text += "🎉 **Вы достигли максимального звания!**\nВы — настоящий эксперт системы Сеплица!"
    
    send_safe_message(message.chat.id, progress_text)

@bot.message_handler(commands=['rank'])
def handle_rank_command(message):
    """Показывает текущее звание пользователя"""
    user_id = message.from_user.id
    current_rank = get_user_rank(user_id)
    
    rank_text = (
        f"🏆 **ВАШЕ ТЕКУЩЕЕ ЗВАНИЕ:** {current_rank}\n\n"
        f"Система званий Сеплица:\n"
        f"• {USER_RANKS['novice']} - начальный уровень\n"
        f"• {USER_RANKS['knowledgeable']} - углубленное изучение\n"
        f"• {USER_RANKS['expert']} - полное освоение системы\n\n"
        f"Используйте /progress для детальной статистики"
    )
    
    send_safe_message(message.chat.id, rank_text)

# ==================== ЗАПУСК БОТА ====================
if __name__ == "__main__":
    logger.info("🚀 Запуск бота Сеплица...")
    
    # Загружаем данные пользователей
    load_user_data()
    
    # Проверяем наличие базы знаний
    knowledge = load_knowledge()
    if knowledge:
        logger.info(f"✅ База знаний загружена: {len(knowledge)} записей")
    else:
        logger.warning("❌ База знаний пуста или не загружена")
    
    logger.info("✅ Бот готов к работе!")
    
    try:
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        time.sleep(5)
