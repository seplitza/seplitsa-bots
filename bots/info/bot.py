import telebot
import requests
import json
import os
import logging
import time
import re
import gspread
import signal
import sys
import threading
from google.oauth2.service_account import Credentials
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from datetime import datetime

# ==================== УПРАВЛЕНИЕ ПРОЦЕССОМ ====================
PID_FILE_CANDIDATES = [
    '/run/seplitsa-info-bot.pid',
    '/var/run/seplitsa-info-bot.pid',
    '/tmp/seplitsa-info-bot.pid',
    'bot.pid'
]

# Allow overriding the desired PID file via environment (useful for systemd)
DEFAULT_PID_FILE = os.getenv('SEPLITSA_PID_FILE', '/tmp/seplitsa-info-bot.pid')

def _write_pid(path):
    try:
        pid = str(os.getpid())
        with open(path, 'w') as f:
            f.write(pid)
        return True
    except Exception as e:
        logger.debug(f"Не удалось записать PID в {path}: {e}")
        return False

def create_pid_file():
    """Создает PID файл в первом доступном месте из списка кандидатов"""
    # Prefer explicit environment-provided path first
    candidates = [DEFAULT_PID_FILE] + [p for p in PID_FILE_CANDIDATES if p != DEFAULT_PID_FILE]

    for p in candidates:
        if _write_pid(p):
            logger.info(f"✅ PID файл создан: {p}")
            global PID_PATH
            PID_PATH = p
            return True

    logger.warning("⚠️ Не удалось создать PID файл ни в одном из путей; продолжаем без PID файла")
    return False

def remove_pid_file():
    """Удаляет PID файл, если он существует"""
    try:
        if 'PID_PATH' in globals() and os.path.exists(PID_PATH):
            os.remove(PID_PATH)
            return True
        # Попытка удалить по всем кандидатам
        for p in PID_FILE_CANDIDATES:
            try:
                if os.path.exists(p):
                    os.remove(p)
                    return True
            except Exception:
                continue
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка удаления PID файла: {e}")
        return False

def check_running_instance():
    """Проверяет, запущен ли уже бот"""
    try:
        # Проверяем стандартные места для PID: сначала явный DEFAULT_PID_FILE, затем старый 'bot.pid'
        candidate_paths = [DEFAULT_PID_FILE, 'bot.pid']
        existing = None
        for p in candidate_paths:
            if os.path.exists(p):
                existing = p
                break

        if existing:
            with open(existing, 'r') as f:
                old_pid = int(f.read().strip())
            # Проверяем, существует ли процесс
            try:
                os.kill(old_pid, 0)
                logger.error(f"❌ Бот уже запущен (PID: {old_pid})")
                return True
            except OSError:
                logger.info("🔄 Найден устаревший PID файл, удаляем...")
                remove_pid_file()
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка проверки запущенного экземпляра: {e}")
        return False

def ensure_not_root():
    """Проверяет, что бот не запущен от имени root"""
    if os.geteuid() == 0:
        logger.error("❌ Бот не должен запускаться с правами root!")
        sys.exit(1)

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения работы бота"""
    signal_name = signal.Signals(sig).name
    logger.info(f'🛑 Получен сигнал {signal_name} на завершение работы...')
    
    try:
        # Помечаем флаг для завершения работы
        bot.stop_bot = True
        
        # Удаляем вебхук перед выходом
        bot.remove_webhook()
        logger.info('✅ Вебхук успешно удален')
        
        # Останавливаем поллинг
        bot.stop_polling()
        logger.info('✅ Поллинг остановлен')
        
        # Даем небольшую паузу для завершения текущих операций
        time.sleep(1)
        
    except Exception as e:
        logger.error(f'❌ Ошибка при завершении работы бота: {e}')
    
    finally:
        try:
            # Сохраняем данные и удаляем PID файл перед выходом
            save_user_data()
            remove_pid_file()
            logger.info('👋 Бот завершает работу')
        except Exception as e:
            logger.error(f'❌ Ошибка при финальной очистке: {e}')
        finally:
            sys.exit(0)

# Регистрируем обработчики сигналов
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGHUP, signal_handler)  # Добавляем обработку SIGHUP

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==================== СОСТОЯНИЕ ПОЛЬЗОВАТЕЛЕЙ ====================
user_states = {}
teaching_mode = {}

def get_user_menu(user_id):
    """Получает текущее меню пользователя"""
    return user_states.get(user_id, 'main')

def set_user_menu(user_id, menu_key):
    """Устанавливает текущее меню пользователя"""
    user_states[user_id] = menu_key

def is_author(user):
    """Проверка, является ли пользователь автором"""
    return user.username == AUTHOR_USERNAME

def is_teaching_mode(user_id):
    """Проверка, находится ли пользователь в режиме обучения"""
    return teaching_mode.get(user_id, False)

def set_teaching_mode(user_id, mode):
    """Установка режима обучения"""
    teaching_mode[user_id] = mode

# ==================== КЛАВИАТУРЫ ====================
def create_main_menu_button():
    """Создает клавиатуру с одной кнопкой возврата в главное меню"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    keyboard.add(KeyboardButton('🏠 Главное меню'))
    keyboard.add(KeyboardButton('🔙 НАЗАД В ГЛАВНОЕ МЕНЮ'))
    return keyboard

def create_financial_keyboard():
    """Создает клавиатуру для финансового положения"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(KeyboardButton('Экономлю'), KeyboardButton('Стабильно'))
    keyboard.add(KeyboardButton('Могу позволить себе многое'), KeyboardButton('Не ограничен'))
    keyboard.add(KeyboardButton('🔙 НАЗАД В ГЛАВНОЕ МЕНЮ'))
    return keyboard

def create_motivation_keyboard():
    """Создает клавиатуру для мотивации"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(KeyboardButton('Только знакомлюсь'), KeyboardButton('Готов изучать'))
    keyboard.add(KeyboardButton('Очень настроен'), KeyboardButton('Уже работаю над собой'))
    keyboard.add(KeyboardButton('🔙 НАЗАД В ГЛАВНОЕ МЕНЮ'))
    return keyboard

def create_menu(menu_key='main'):
    """Создает клавиатуру для указанного меню (ЕДИНСТВЕННАЯ ВЕРСИЯ)"""
    if menu_key not in MENU_STRUCTURE:
        menu_key = 'main'
    menu = MENU_STRUCTURE[menu_key]
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [KeyboardButton(btn) for btn in menu['buttons']]
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        keyboard.add(*row)
    return keyboard, menu['title']

def create_author_menu(menu_key='main'):
    """Создает меню для автора с дополнительной кнопкой обучения"""
    keyboard, title = create_menu(menu_key)
    if menu_key == 'main':
        keyboard.add(KeyboardButton('🔧 Обучение'))
    return keyboard, title

def create_teaching_keyboard():
    """Создает клавиатуру для режима обучения"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(KeyboardButton('📝 Показать базу знаний'))
    keyboard.add(KeyboardButton('❌ Выйти из режима обучения'))
    keyboard.add(KeyboardButton('🏠 Главное меню'))
    return keyboard

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
# Data directory from environment or current directory
DATA_DIR = os.getenv('SEPLITSA_DATA_DIR', '.')
# Knowledge base stays in project directory (persistent)
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')

KNOWLEDGE_FILE = os.path.join(KNOWLEDGE_DIR, "info_knowledge.json.example")
USER_DATA_FILE = os.path.join(DATA_DIR, "seplitsa_info_user_data.json")

# Настройки Google Sheets
GOOGLE_SHEETS_CREDENTIALS = os.path.join(DATA_DIR, "seplitsa-credentials.json")  # Файл с ключами API
GOOGLE_SHEET_NAME = "Сеплица - База подписчиков"

# ==================== ЗВАНИЯ И ТРЕБОВАНИЯ ====================
USER_RANKS = {
    'interested': '🌱 Интересующийся Сеплицей',
    'novice': '👶 Сеплица-Неофит',
    'knowledgeable': '📚 Знаток',
    'expert': '🎓 Эксперт'
}

RANK_REQUIREMENTS = {
    'interested': {
        'data_collected': True  # Просто заполнить анкету
    },
    'knowledgeable': {
        'menus_visited': 3,
        'topics_read': 5,
        'details_clicks': 3
    },
    'expert': {
        'menus_visited': 6,
        'topics_read': 10,
        'details_clicks': 6
    }
}

# ==================== СИСТЕМА СБОРА ДАННЫХ ====================
def validate_user_data(user_id):
    """Проверяет корректность собранных данных"""
    if user_id not in user_data:
        logger.info(f"🔍 Валидация: пользователь {user_id} не найден в user_data")
        return False, []
    
    profile = user_data[user_id]
    errors = []
    
    logger.info(f"🔍 Валидация данных для {user_id}: {profile}")
    
    # Проверяем корректность финансового положения
    valid_financial = ['Экономлю', 'Стабильно', 'Могу позволить себе многое', 'Не ограничен']
    if 'financial' in profile:
        if profile['financial'] not in valid_financial:
            logger.info(f"❌ Некорректное финансовое положение: '{profile['financial']}' не в {valid_financial}")
            errors.append('financial')
        else:
            logger.info(f"✅ Финансовое положение корректно: '{profile['financial']}'")
    
    # Проверяем корректность мотивации
    valid_motivation = ['Только знакомлюсь', 'Готов изучать', 'Очень настроен', 'Уже работаю над собой']
    if 'motivation' in profile:
        if profile['motivation'] not in valid_motivation:
            logger.info(f"❌ Некорректная мотивация: '{profile['motivation']}' не в {valid_motivation}")
            errors.append('motivation')
        else:
            logger.info(f"✅ Мотивация корректна: '{profile['motivation']}'")
    
    # Проверяем, что город - это не ответ из других вопросов
    if 'city' in profile:
        city = profile['city']
        if city in valid_financial or city in valid_motivation:
            logger.info(f"❌ Город содержит ответ из других вопросов: '{city}'")
            errors.append('city')
        else:
            logger.info(f"✅ Город корректен: '{city}'")
    
    result = len(errors) == 0
    logger.info(f"🔍 Результат валидации для {user_id}: valid={result}, errors={errors}")
    return result, errors

def is_user_profile_complete(user_id):
    """Проверяет, завершена ли анкета пользователя корректно"""
    if user_id not in user_data:
        return False
    
    required_fields = ['name', 'age', 'city', 'financial', 'motivation']
    user_profile = user_data[user_id]
    
    # Проверяем наличие всех полей
    if not all(field in user_profile for field in required_fields):
        return False
    
    # Проверяем корректность данных
    is_valid, _ = validate_user_data(user_id)
    
    # Если данные корректны и все поля заполнены, устанавливаем флаг
    if is_valid:
        init_user_progress(user_id)
        user_progress[user_id]['data_collected'] = True
        user_data[user_id]['data_collected'] = True
        logger.info(f"✅ Профиль пользователя {user_id} полностью корректен, установлен флаг data_collected")
        
    return is_valid

def fix_incorrect_data(user_id):
    """Исправляет некорректные данные и возвращает с какого шага продолжить"""
    logger.info(f"🔧 Исправление данных для {user_id}")
    is_valid, errors = validate_user_data(user_id)
    if is_valid:
        logger.info(f"✅ Данные корректны, исправление не требуется")
        return None
    
    profile = user_data[user_id]
    logger.info(f"🔧 Найдены ошибки: {errors}")
    
    # Если город некорректный, начинаем с города
    if 'city' in errors:
        logger.info(f"🔧 Исправляем город, устанавливаем step='city'")
        profile['step'] = 'city'
        return 'city'
    
    # Если финансы некорректные, начинаем с финансов
    if 'financial' in errors:
        logger.info(f"🔧 Исправляем финансы, устанавливаем step='financial'")
        profile['step'] = 'financial'
        # Очищаем некорректные данные
        if 'financial' in profile:
            logger.info(f"🔧 Удаляем некорректные финансы: '{profile['financial']}'")
            del profile['financial']
        if 'motivation' in profile:
            logger.info(f"🔧 Удаляем мотивацию: '{profile['motivation']}'")
            del profile['motivation']
        return 'financial'
    
    # Если мотивация некорректная, начинаем с мотивации
    if 'motivation' in errors:
        logger.info(f"🔧 Исправляем мотивацию, устанавливаем step='motivation'")
        profile['step'] = 'motivation'
        if 'motivation' in profile:
            logger.info(f"🔧 Удаляем некорректную мотивацию: '{profile['motivation']}'")
            del profile['motivation']
        return 'motivation'
    
    logger.info(f"🔧 Неизвестные ошибки: {errors}")
    return None

def collect_user_data_step_by_step(user_id, answer):
    """Пошаговый сбор данных пользователя"""
    try:
        if user_id not in user_data:
            user_data[user_id] = {'step': 'name'}
        
        profile = user_data[user_id]
        current_step = profile.get('step', 'name')
        
        # Если пользователь находится в состоянии проверки данных
        if current_step == 'review':
            logger.info(f"📋 Пользователь {user_id} находится в режиме проверки данных")
            return show_data_review(user_id, profile)
        
        # МИГРАЦИЯ: если пользователь застрял на старом шаге 'device', пропускаем его
        if current_step == 'device':
            logger.info(f"🔄 Миграция: пропускаем устаревший шаг 'device' для {user_id}")
            current_step = 'financial'
            profile['step'] = 'financial'
            save_user_data()
        
        logger.info(f"📊 Сбор данных для {user_id}: текущий шаг='{current_step}', ответ='{answer}' [BUILD: 230de2f]")
        
        # Словарь валидации для каждого шага
        step_validation = {
            'name': {
                'validate': lambda x: len(x.strip()) >= 2,
                'error': "🤔 Пожалуйста, введите корректное имя (минимум 2 символа):",
                'next': 'age',
                'success': lambda x: x.strip(),
                'next_message': "👋 Приятно познакомиться! Сколько вам лет?",
                'keyboard': create_main_menu_button
            },
            'age': {
                'validate': lambda x: x.isdigit() and 18 <= int(x) <= 100,
                'error': "🤔 Пожалуйста, введите корректный возраст (18-100):",
                'next': 'city',
                'success': lambda x: int(x),
                'next_message': "🌍 В каком городе вы живете?",
                'keyboard': create_main_menu_button
            },
            'city': {
                'validate': lambda x: len(x.strip()) >= 2 and x.strip() not in ['Экономлю', 'Стабильно', 'Могу позволить себе многое', 'Не ограничен', 'Только знакомлюсь', 'Готов изучать', 'Очень настроен', 'Уже работаю над собой'],
                'error': "🤔 Пожалуйста, введите корректное название города:",
                'next': 'financial',
                'success': lambda x: x.strip(),
                'next_message': "💰 Как бы вы оценили свое финансовое положение?",
                'keyboard': create_financial_keyboard
            },
            'financial': {
                'validate': lambda x: x in ['Экономлю', 'Стабильно', 'Могу позволить себе многое', 'Не ограничен'],
                'error': "💰 Пожалуйста, выберите из предложенных вариантов:",
                'next': 'motivation',
                'success': lambda x: x,
                'next_message': "🎯 Насколько вы настроены на работу над собой?",
                'keyboard': create_financial_keyboard
            },
            'motivation': {
                'validate': lambda x: x in ['Только знакомлюсь', 'Готов изучать', 'Очень настроен', 'Уже работаю над собой'],
                'error': "🎯 Пожалуйста, выберите из предложенных вариантов:",
                'next': 'complete',
                'success': lambda x: x,
                'keyboard': create_motivation_keyboard
            }
        }
        
        # Если текущий шаг не найден в словаре валидации, начинаем сначала
        if current_step not in step_validation:
            profile['step'] = 'name'
            return "Давайте начнем сначала. Как вас зовут?", None
        
        step = step_validation[current_step]
        
        # Проверяем валидность ответа
        is_valid = step['validate'](answer)
        logger.info(f"🔍 Валидация для шага '{current_step}': ответ='{answer}' -> valid={is_valid}")
        
        if not is_valid:
            logger.info(f"❌ Валидация не прошла для шага '{current_step}': ответ='{answer}'")
            return step['error'], step.get('keyboard', lambda: None)()
        
        # Сохраняем ответ и обновляем шаг
        logger.info(f"✅ Валидация пройдена для шага '{current_step}': ответ='{answer}' → следующий шаг='{step['next']}'")
        profile[current_step] = step['success'](answer)
        next_step = step['next']
        
        # Если это был последний шаг
        if next_step == 'complete':
            profile['data_collected'] = True
            profile['step'] = 'review'  # Переходим к проверке данных
            
            # Присваиваем звание "Интересующийся Сеплицей"
            if user_id in user_progress:
                user_progress[user_id]['current_rank'] = 'interested'
                # ⚠️ ВАЖНО: устанавливаем флаг в user_progress тоже!
                user_progress[user_id]['data_collected'] = True
            
            save_user_data()
            
            # Показываем собранные данные для подтверждения
            return show_data_review(user_id, profile)
        
        # Переходим к следующему шагу
        profile['step'] = next_step
        save_user_data()  # Сохраняем после каждого шага
        
        next_keyboard_func = step_validation[next_step].get('keyboard', lambda: None)
        next_keyboard = next_keyboard_func()
        logger.info(f"🎹 Показываем клавиатуру для шага '{next_step}': функция={next_keyboard_func.__name__ if hasattr(next_keyboard_func, '__name__') else 'lambda'}")
        
        return step_validation[next_step]['next_message'], next_keyboard
        
    except Exception as e:
        logger.error(f"Ошибка в сборе данных: {e}")
        return "Произошла ошибка. Пожалуйста, попробуйте еще раз или обратитесь к администратору.", None

def show_data_review(user_id, profile):
    """Показывает собранные данные для подтверждения"""
    try:
        review_text = (
            "📋 **ПРОВЕРЬТЕ ВАШИ ДАННЫЕ**\n\n"
            f"👤 **Имя:** {profile.get('name', 'Не указано')}\n"
            f"🎂 **Возраст:** {profile.get('age', 'Не указан')}\n"
            f"🌍 **Город:** {profile.get('city', 'Не указан')}\n"
            f"💰 **Финансовое положение:** {profile.get('financial', 'Не указано')}\n"
            f"🎯 **Мотивация:** {profile.get('motivation', 'Не указана')}\n\n"
            "❓ **Все данные корректны?**"
        )
        
        keyboard = create_data_confirmation_keyboard()
        return review_text, keyboard
        
    except Exception as e:
        logger.error(f"Ошибка при показе данных: {e}")
        return "Произошла ошибка при отображении данных.", None

def create_data_confirmation_keyboard():
    """Создает клавиатуру для подтверждения данных"""
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        KeyboardButton("✅ Все верно"),
        KeyboardButton("✏️ Исправить данные")
    )
    markup.add(KeyboardButton("🔙 НАЗАД В ГЛАВНОЕ МЕНЮ"))
    return markup

def create_notification_frequency_keyboard():
    """Создает клавиатуру для выбора частоты уведомлений"""
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        KeyboardButton("⏰ Раз в час"),
        KeyboardButton("📅 Раз в день")
    )
    markup.add(
        KeyboardButton("📆 Раз в неделю"), 
        KeyboardButton("🗓 Раз в месяц")
    )
    markup.add(KeyboardButton("🚫 Никогда"))
    markup.add(KeyboardButton("🔙 НАЗАД В ГЛАВНОЕ МЕНЮ"))
    return markup

def complete_data_collection(user_id):
    """Завершает сбор данных и переводит в основное меню"""
    set_data_collection_mode(user_id, False)
    
    completion_text = (
        "🎉 **СПАСИБО ЗА РЕГИСТРАЦИЮ!**\n\n"
        "🌱 Вам присвоено звание: **Интересующийся Сеплицей**\n\n"
        "🎯 Теперь я смогу давать вам более персонализированные рекомендации по системе омоложения.\n\n"
        "💡 Изучайте систему через меню и задавайте вопросы!"
    )
    
    keyboard = create_menu('main')[0]
    return completion_text, keyboard

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
                
                # 🔥 ПРЕОБРАЗУЕМ списки обратно в множества
                loaded_progress = data.get('user_progress', {})
                user_progress = {}
                
                for user_id, progress in loaded_progress.items():
                    user_progress[user_id] = {
                        'menus_visited': set(progress.get('menus_visited', [])),
                        'topics_read': set(progress.get('topics_read', [])),
                        'details_clicks': progress.get('details_clicks', 0),
                        'messages_scrolled': set(progress.get('messages_scrolled', [])),
                        'current_rank': progress.get('current_rank', 'novice'),
                        'registration_date': progress.get('registration_date'),
                        'data_collected': progress.get('data_collected', False)
                    }
                
                logger.info(f"✅ Данные пользователей загружены: {len(user_data)} пользователей")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки данных пользователей: {e}")
            user_data = {}
            user_progress = {}

def save_user_data():
    """Сохранение данных пользователей"""
    try:
        # 🔥 ПРЕОБРАЗУЕМ множества в списки для JSON-сериализации
        serializable_progress = {}
        for user_id, progress in user_progress.items():
            serializable_progress[user_id] = {
                'menus_visited': list(progress.get('menus_visited', set())),
                'topics_read': list(progress.get('topics_read', set())),
                'details_clicks': progress.get('details_clicks', 0),
                'messages_scrolled': list(progress.get('messages_scrolled', set())),
                'current_rank': progress.get('current_rank', 'novice'),
                'registration_date': progress.get('registration_date'),
                'data_collected': progress.get('data_collected', False)
            }
        
        data = {
            'user_data': user_data,
            'user_progress': serializable_progress
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

# Старые версии функций сбора данных и клавиатур были удалены.
# Используется новая версия collect_user_data_step_by_step с валидацией через словарь
# и стандартизированными клавиатурами.

# ==================== ОСТАЛЬНЫЕ ФУНКЦИИ (без изменений) ====================
def normalize_key(key):
    """Нормализует ключ для поиска в базе знаний"""
    if not key:
        return ""
    
    normalized = key.strip().lower()
    normalized = re.sub(r'[🔙📚💪🙆🥗🔬🎓🛠️❓🏠🔧📝❌*_`\\[\\]]', '', normalized)
    normalized = re.sub(r'назад в главное меню', '', normalized)
    normalized = re.sub(r'система сеплица: основы', 'система сеплица основы', normalized)
    normalized = normalized.strip()
    return normalized

def find_knowledge_by_key(key):
    """Находит знания по ключу с нормализацией"""
    knowledge = load_knowledge()
    
    if not knowledge:
        logger.warning("База знаний пуста")
        return None
    
    original_key = key
    normalized_key = normalize_key(key)
    logger.info(f"Поиск: '{original_key}' -> нормализовано: '{normalized_key}'")
    if original_key in knowledge:
        logger.info(f"Найдено прямое совпадение: '{original_key}'")
        return knowledge[original_key]
    for knowledge_key, value in knowledge.items():
        norm_knowledge_key = normalize_key(knowledge_key)
        if norm_knowledge_key == normalized_key:
            logger.info(f"Найдено по нормализованному ключу: '{knowledge_key}'")
            return value
        if normalized_key in norm_knowledge_key or norm_knowledge_key in normalized_key:
            if len(normalized_key) > 3:
                logger.info(f"Найдено частичное совпадение: '{knowledge_key}' ~ '{normalized_key}'")
                return value
    logger.warning(f"Ключ не найден: '{original_key}' (норм: '{normalized_key}')")
    return None

def send_safe_message(chat_id, text, reply_markup=None, parse_mode='Markdown'):
    """Безопасная отправка сообщения с автоматическим определением режима"""
    try:
        # Для длинных текстов или текстов с большим количеством спецсимволов отключаем Markdown
        if len(text) > 3000 or text.count('*') > 50 or text.count('_') > 50:
            return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=None)
        else:
            # Пробуем отправить с Markdown
            return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
            
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения с Markdown: {e}")
        try:
            # Пробуем отправить без Markdown
            return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=None)
        except Exception as e2:
            logger.error(f"Ошибка отправки без Markdown: {e2}")
            # Если и это не работает, разбиваем на части или очищаем
            if len(text) > 4000:
                part1 = text[:4000]
                part2 = text[4000:8000] if len(text) > 8000 else text[4000:]
                bot.send_message(chat_id, part1, reply_markup=reply_markup, parse_mode=None)
                if part2:
                    return bot.send_message(chat_id, part2, reply_markup=reply_markup, parse_mode=None)
            else:
                # Удаляем все проблемные символы
                clean_text = re.sub(r'[*_`\[\]\\]', '', text)
                return bot.send_message(chat_id, clean_text, reply_markup=reply_markup, parse_mode=None)

# duplicate old create_menu removed; using the single KeyboardButton-based implementation above

def ask_deepseek(user_message, chat_id=None):
    """Запрос к DeepSeek API с увеличенным таймаутом и индикатором typing"""
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
        # Если указан chat_id, периодически отправляем typing индикатор
        stop_typing = threading.Event()
        
        def send_typing_periodically():
            """Отправляет typing каждые 4 секунды пока AI думает"""
            # ВАЖНО: Первый typing отправляем СРАЗУ, без задержки
            if chat_id:
                try:
                    bot.send_chat_action(chat_id, 'typing')
                    logger.info("✅ Первый typing отправлен")
                except Exception as e:
                    logger.error(f"Ошибка отправки первого typing: {e}")
            
            # Затем отправляем в цикле каждые 4 секунды
            while not stop_typing.is_set():
                time.sleep(4)  # Ждем 4 секунды
                if not stop_typing.is_set() and chat_id:  # Проверяем что не остановлен
                    try:
                        bot.send_chat_action(chat_id, 'typing')
                        logger.info("✅ Периодический typing отправлен")
                    except Exception as e:
                        logger.error(f"Ошибка отправки typing: {e}")
                        break
        
        # Запускаем поток для периодической отправки typing
        if chat_id:
            typing_thread = threading.Thread(target=send_typing_periodically, daemon=True)
            typing_thread.start()
        
        response = requests.post(DEEPSEEK_URL, headers=headers, json=data, timeout=60)
        
        # Останавливаем отправку typing
        stop_typing.set()
        
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        if 'stop_typing' in locals():
            stop_typing.set()
        logger.error("Таймаут запроса к DeepSeek API")
        return "Извините, сервис временно недоступен. Пожалуйста, попробуйте позже."
    except Exception as e:
        if 'stop_typing' in locals():
            stop_typing.set()
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

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def should_initiate_data_collection(user_id, user_message):
    """Определяет, нужно ли инициировать сбор данных ТОЛЬКО при запросе к AI"""
    
    # 🔥 НИКОГДА не прерываем меню и команды
    if any(user_message in menu['buttons'] for menu in MENU_STRUCTURE.values()):
        logger.info(f"🚫 Сбор данных пропущен: сообщение '{user_message}' - это кнопка меню")
        return False
    
    if user_message.startswith('/'):
        logger.info(f"🚫 Сбор данных пропущен: '{user_message}' - это команда")
        return False
    
    if user_message in ['🏠 Главное меню', '🔙 НАЗАД В ГЛАВНОЕ МЕНЮ']:
        logger.info(f"🚫 Сбор данных пропущен: '{user_message}' - навигация")
        return False
    
    # 🔥 Не собираем данные, если уже в процессе
    if is_data_collection_mode(user_id):
        logger.info(f"🚫 Сбор данных пропущен: пользователь {user_id} уже в режиме сбора")
        return False
    
    # 🔥 Не собираем данные, если есть ответ в базе знаний
    if find_knowledge_by_key(user_message):
        logger.info(f"🚫 Сбор данных пропущен: '{user_message}' найден в базе знаний")
        return False
    
    # 🔥 Не собираем данные для коротких/случайных сообщений
    if len(user_message.strip()) < 3:
        logger.info(f"🚫 Сбор данных пропущен: сообщение слишком короткое ({len(user_message)} символов)")
        return False
    
    # ✅ Проверяем, собраны ли данные пользователя
    init_user_progress(user_id)
    data_collected = user_progress[user_id].get('data_collected', False)
    logger.info(f"📊 Проверка пользователя {user_id}: data_collected={data_collected}")
    
    if data_collected:
        logger.info(f"🚫 Сбор данных пропущен: данные пользователя {user_id} уже собраны")
        return False  # Данные уже собраны
    
    # ✅ Инициируем сбор данных для новых пользователей при AI запросе
    logger.info(f"✅ СБОР ДАННЫХ АКТИВИРОВАН для пользователя {user_id}")
    return True

# ==================== ОБРАБОТЧИКИ СООБЩЕНИЙ ====================
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

@bot.message_handler(commands=['menu'])
def handle_menu_command(message):
    """Показывает главное меню"""
    user_id = message.from_user.id
    # Выходим из режима сбора данных при переходе в меню
    if is_data_collection_mode(user_id):
        logger.info(f"Пользователь {user_id} вышел из режима сбора данных через команду /menu")
        set_data_collection_mode(user_id, False)
    keyboard = create_menu('main')[0]
    send_safe_message(message.chat.id, "🏠 Главное меню:", reply_markup=keyboard)

@bot.message_handler(commands=['reset_profile'])
def handle_reset_profile(message):
    """Команда для сброса анкеты пользователя"""
    user_id = message.from_user.id
    logger.info(f"🔄 Сброс профиля для пользователя {user_id}")
    
    # Очищаем данные пользователя
    if user_id in user_data:
        old_data = user_data[user_id].copy()
        logger.info(f"🔄 Удаляем старые данные: {old_data}")
        del user_data[user_id]
    
    # Очищаем прогресс
    if user_id in user_progress:
        old_progress = user_progress[user_id].copy()
        logger.info(f"🔄 Удаляем старый прогресс: {old_progress}")
        del user_progress[user_id]
    
    # Выходим из режима сбора данных
    set_data_collection_mode(user_id, False)
    save_user_data()
    
    keyboard = create_menu('main')[0]
    send_safe_message(message.chat.id, "✅ Анкета сброшена! Теперь можете заполнить её заново.", reply_markup=keyboard)

@bot.message_handler(commands=['fill_profile'])
def handle_fill_profile(message):
    """Команда для принудительного заполнения анкеты"""
    user_id = message.from_user.id
    logger.info(f"📝 handle_fill_profile вызвана для {user_id}")
    
    # Проверяем, заполнена ли анкета корректно
    if is_user_profile_complete(user_id):
        logger.info(f"✅ Профиль {user_id} уже заполнен корректно")
        send_safe_message(message.chat.id, "✅ Ваш профиль уже заполнен корректно!")
        return
    
    logger.info(f"🔍 Проверяем валидность данных для {user_id}")
    # Проверяем, есть ли ошибки в данных
    is_valid, errors = validate_user_data(user_id)
    logger.info(f"🔍 Результат проверки: valid={is_valid}, errors={errors}")
    
    if not is_valid and errors:
        logger.info(f"❌ Найдены ошибки, запускаем исправление")
        # Исправляем некорректные данные
        error_step = fix_incorrect_data(user_id)
        logger.info(f"🔧 Исправление вернуло шаг: {error_step}")
        set_data_collection_mode(user_id, True)
        
        error_messages = {
            'city': "🔄 Обнаружена ошибка: город указан некорректно.\n\n🌍 В каком городе вы живете?",
            'financial': "🔄 Обнаружена ошибка в финансовом положении.\n\n💰 Как бы вы оценили свое финансовое положение?",
            'motivation': "🔄 Обнаружена ошибка в уровне мотивации.\n\n🎯 Насколько вы настроены на работу над собой?"
        }
        
        message_text = error_messages.get(error_step, "🔄 Давайте уточним некоторые данные.")
        logger.info(f"📤 Отправляем сообщение об ошибке: {message_text}")
        
        # Подбираем клавиатуру
        keyboard_map = {
            'financial': create_financial_keyboard(),
            'motivation': create_motivation_keyboard(),
            'city': create_main_menu_button()
        }
        keyboard = keyboard_map.get(error_step, create_main_menu_button())
        
        send_safe_message(message.chat.id, message_text, reply_markup=keyboard)
        return
    
    logger.info(f"📋 Анкета не заполнена, начинаем с начала")
    # Если анкета не заполнена вообще, начинаем с начала
    set_data_collection_mode(user_id, True)
    send_safe_message(message.chat.id, 
                     "📝 Давайте заполним вашу анкету для персонализированных рекомендаций!\n\n"
                     "Как вас зовут?",
                     reply_markup=create_main_menu_button())

@bot.message_handler(func=lambda message: message.text in ["✅ Все верно", "✏️ Исправить данные"])
def handle_data_confirmation(message):
    """Обработчик подтверждения данных анкеты"""
    user_id = message.from_user.id
    user_message = message.text.strip()
    
    if user_message == "✅ Все верно":
        # Переходим к настройке уведомлений
        notification_text = (
            "🎉 **ОТЛИЧНО!**\n\n"
            "Не будете ли вы против, если время от времени я буду присылать полезную информацию по долголетию?\n\n"
            "📬 **Как часто вы хотели бы получать уведомления?**"
        )
        keyboard = create_notification_frequency_keyboard()
        send_safe_message(message.chat.id, notification_text, reply_markup=keyboard)
        
    elif user_message == "✏️ Исправить данные":
        # Сбрасываем данные и начинаем заново
        if user_id in user_data:
            # Сохраняем telegram данные
            telegram_data = {
                'telegram_username': user_data[user_id].get('telegram_username'),
                'telegram_first_name': user_data[user_id].get('telegram_first_name'),
                'telegram_last_name': user_data[user_id].get('telegram_last_name')
            }
            user_data[user_id] = telegram_data
            user_data[user_id]['step'] = 'name'
        
        set_data_collection_mode(user_id, True)
        send_safe_message(message.chat.id, "📝 Давайте заполним анкету заново.\n\nКак вас зовут?", 
                         reply_markup=create_main_menu_button())

@bot.message_handler(func=lambda message: message.text in ["⏰ Раз в час", "📅 Раз в день", "📆 Раз в неделю", "🗓 Раз в месяц", "🚫 Никогда"])
def handle_notification_frequency(message):
    """Обработчик выбора частоты уведомлений"""
    user_id = message.from_user.id
    frequency = message.text.strip()
    
    # Сохраняем настройку уведомлений
    if user_id in user_data:
        user_data[user_id]['notification_frequency'] = frequency
        save_user_data()
    
    # Завершаем сбор данных
    response_text, keyboard = complete_data_collection(user_id)
    
    if frequency == "🚫 Никогда":
        thanks_text = (
            "✅ **Понятно!** Я не буду присылать уведомления.\n\n"
            f"{response_text}"
        )
    else:
        thanks_text = (
            f"✅ **Спасибо!** Буду присылать полезную информацию **{frequency.lower()}**.\n\n"
            f"{response_text}"
        )
    
    send_safe_message(message.chat.id, thanks_text, reply_markup=keyboard)

@bot.message_handler(func=lambda message: is_data_collection_mode(message.from_user.id))
def handle_data_collection(message):
    """Обработчик сбора данных пользователя"""
    user_id = message.from_user.id
    user = message.from_user
    user_message = message.text.strip()
    logger.info(f"Обработка данных от {user_id}: '{user_message}'")
    
    # Сохраняем telegram username и имя при первом обращении
    if user_id not in user_data:
        user_data[user_id] = {
            'telegram_username': user.username,
            'telegram_first_name': user.first_name,
            'telegram_last_name': user.last_name
        }
    
    if (message.text.startswith('/') or 
        user_message in ['🏠 Главное меню', '🔙 НАЗАД В ГЛАВНОЕ МЕНЮ'] or
        any(user_message in menu['buttons'] for menu in MENU_STRUCTURE.values())):
        logger.info(f"Пользователь {user_id} прервал сбор данных командой: '{user_message}'")
        set_data_collection_mode(user_id, False)
        keyboard, title = create_menu('main')
        send_safe_message(message.chat.id, "✅ Сбор данных прерван. Возвращаемся в главное меню:", reply_markup=keyboard)
        return
    response = collect_user_data_step_by_step(user_id, user_message)
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
    user_message = message.text.strip()
    logger.info(f"Получено сообщение от {user_id}: '{user_message}'")
    
    # 1. Проверка режима сбора данных - ПЕРВОЕ ДЕЛО
    if is_data_collection_mode(user_id):
        logger.info(f"Пользователь {user_id} в режиме сбора данных")
        handle_data_collection(message)
        return
    
    # 2. Обработка команд автора
    if handle_author_command(message):
        return
    
    # 3. Проверяем, является ли это кнопкой перехода в подменю (название меню из MENU_STRUCTURE)
    if user_message in MENU_STRUCTURE and user_message != 'main':
        logger.info(f"Переход в подменю: '{user_message}'")
        update_user_progress(user.id, 'menu_visited', user_message)
        keyboard, title = create_menu(user_message)
        send_safe_message(message.chat.id, title, reply_markup=keyboard)
        return
    
    # 4. Проверяем кнопку возврата в главное меню
    if user_message in ['🏠 Главное меню', '🔙 НАЗАД В ГЛАВНОЕ МЕНЮ']:
        logger.info("Нажата кнопка возврата в главное меню")
        keyboard, title = create_menu('main')
        send_safe_message(message.chat.id, title, reply_markup=keyboard)
        return
    
    # 5. Поиск в базе знаний (для кнопок с темами и обычных вопросов)
    knowledge = find_knowledge_by_key(user_message)
    if knowledge:
        logger.info(f"Найден ответ в базе знаний для: '{user_message}'")
        update_user_progress(user.id, 'topic_read', user_message)
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Отправляем полный текст сразу (как в expert bot)
        send_safe_message(
            message.chat.id,
            f"📋 **{user_message}**\n\n{knowledge}",
            parse_mode='Markdown'
        )
        return
    
    # 6. Если не нашли в базе - используем AI (всегда полный ответ без кнопки)
    logger.info(f"Используем AI для запроса: '{user_message}'")
    
    # Проверяем, нужно ли собрать данные пока AI думает
    if should_initiate_data_collection(user_id, user_message):
        logger.info(f"⏳ Запускаем сбор данных во время ожидания AI для пользователя {user_id}")
        set_data_collection_mode(user_id, True)
        send_safe_message(message.chat.id, "⏳ Пока AI готовит ответ, давайте завершим вашу анкету!\n\n📝 Как вас зовут?")
    
    # Вызываем AI (может занять время) - передаем chat_id для автоматического индикатора typing
    ai_response = ask_deepseek(user_message, chat_id=message.chat.id)
    
    # AI всегда отправляет полный ответ сразу (как в expert bot)
    send_safe_message(message.chat.id, ai_response)

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
def ensure_clean_start():
    """Проверяет и очищает предыдущие вебхуки"""
    try:
        # Проверяем, нет ли уже запущенного экземпляра
        if check_running_instance():
            return False
            
        # Создаем PID файл — не прерываем запуск, если не удалось создать (systemd может управлять процессом)
        if not create_pid_file():
            logger.warning("⚠️ Продолжаем запуск без PID файла (если вы используете systemd, настройте RuntimeDirectory или SEPLITSA_PID_FILE)")
            
        # Удаляем старый вебхук
        bot.remove_webhook()
        logger.info("✅ Вебхук удален")
        
        # Принудительно очищаем все апдейты
        bot.get_updates(offset=-1)
        logger.info("✅ Очередь обновлений очищена")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке состояния бота: {e}")
        remove_pid_file()  # Удаляем PID файл в случае ошибки
        return False

if __name__ == "__main__":
    try:
        # Проверяем, что бот не запущен от root
        ensure_not_root()
        
        # Загружаем данные при запуске
        load_user_data()
        knowledge = load_knowledge()
        
        if knowledge:
            logger.info(f"✅ База знаний загружена: {len(knowledge)} записей")
        else:
            logger.warning("❌ База знаний пуста или не загружена")
        
        # Проверяем и очищаем состояние бота
        if ensure_clean_start():
            logger.info("🚀 Запуск бота Сеплица...")
            
            # Устанавливаем флаг для корректного завершения
            bot.stop_bot = False
            
            # Запускаем поллинг с обработкой исключений
            while not bot.stop_bot:
                try:
                    bot.infinity_polling(timeout=10, long_polling_timeout=5)
                except Exception as e:
                    logger.error(f"❌ Ошибка в цикле поллинга: {e}")
                    if not bot.stop_bot:
                        logger.info("🔄 Перезапуск поллинга через 5 секунд...")
                        time.sleep(5)
        else:
            logger.error("❌ Не удалось запустить бота из-за ошибок инициализации")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал прерывания...")
        signal_handler(signal.SIGINT, None)
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        signal_handler(signal.SIGTERM, None)
