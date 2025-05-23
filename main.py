import asyncio
import logging
import json
import os
import random
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, Filter
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from datetime import datetime, timedelta
from dotenv import load_dotenv

# .env faylidan sozlamalarni yuklash
load_dotenv()

# Bot sozlamalari
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CODE = os.getenv("ADMIN_CODE", "Q1w2e3r4+")
DATA_FILE = "bot_data.json"
CHANNEL_ID = os.getenv("CHANNEL_ID", "@crm_tekshiruv")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Render'dan olinadigan URL
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", 8080))

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
router = Router()

# Global o'zgaruvchilar
user_lang = {}
user_data = {}
users = set()
blocked_users = set()
daily_users = {}
admin_state = {}
registered_users = {}
user_documents = {}
verification_codes = {}

# Logging sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ma'lumotlarni fayldan yuklash
def load_data():
    global users, blocked_users, daily_users, registered_users, user_documents
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                users = set(data.get("users", []))
                blocked_users = set(data.get("blocked_users", []))
                daily_users_raw = data.get("daily_users", {})
                daily_users = {key: set(value) for key, value in daily_users_raw.items()}
                registered_users = data.get("registered_users", {})
                user_documents = data.get("user_documents", {})
        except (json.JSONDecodeError, ValueError) as e:
            logging.error(f"Ma'lumotlarni yuklashda xatolik: {e}. Yangi fayl yaratilmoqda.")
            os.remove(DATA_FILE)
            users, blocked_users, daily_users, registered_users, user_documents = set(), set(), {}, {}, {}
    else:
        users, blocked_users, daily_users, registered_users, user_documents = set(), set(), {}, {}, {}

# Ma'lumotlarni faylga saqlash
def save_data():
    daily_users_serializable = {key: list(value) for key, value in daily_users.items()}
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "users": list(users),
                "blocked_users": list(blocked_users),
                "daily_users": daily_users_serializable,
                "registered_users": registered_users,
                "user_documents": user_documents
            }, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Ma'lumotlarni saqlashda xatolik: {e}")

# Tarjimalar
translations = {
    "uz": {
        "lang_name": "🇺🇿 O'zbekcha",
        "start": "🌐 Iltimos, tilni tanlang:",
        "welcome": "Assalomu alaykum! 👋\nSiz PBS IMPEX kompaniyasining rasmiy Telegram botidasiz. 🌍",
        "menu": ["📝 Ro'yxatdan o'tish", "📞 Operator", "🛠 Xizmatlar", "👤 Foydalanuvchi profili"],
        "registration_questions": [
            "1️⃣ Pasport yoki ID suratini yuklang (.jpg, .jpeg, .png, .pdf):",
            "2️⃣ Texpasport suratini yuklang (.jpg, .jpeg, .png, .pdf):",
            "3️⃣ Xalqaro yuk tashish litsenziyasini yuklang (.jpg, .jpeg, .png, .pdf):"
        ],
        "initial_questions": [
            "Ismingiz yoki familiyangiz?",
            "Telefon raqamingiz?"
        ],
        "confirm": "✅ Tasdiqlash",
        "retry": "🔄 O‘zgartirish",
        "home": "🏠 Bosh sahifa",
        "back": "🔙 Orqaga",
        "received": "✅ Ma'lumotlar qabul qilindi. Tez orada bog‘lanamiz!",
        "error_invalid_file": "❌ Noto‘g‘ri fayl formati! Faqat .jpg, .jpeg, .png yoki .pdf fayllar qabul qilinadi.",
        "error_phone": "❌ Telefon raqami noto‘g‘ri! Faqat raqamlar kiritilishi kerak. Qaytadan kiriting:",
        "error_phone_length": "❌ Telefon raqami 9 yoki 12 ta raqamdan iborat bo‘lishi kerak! Qaytadan kiriting:",
        "error_no_digits": "❌ Bu maydonda raqamlar ishlatilmasligi kerak! Qaytadan kiriting:",
        "services": "🛠 Xizmatlar",
        "admin_menu": ["📊 Statistika", "📢 Post", "🏠 Bosh sahifa"],
        "admin_code_prompt": "🔑 Admin paneliga kirish uchun kodni kiriting:",
        "admin_welcome": "👨‍💼 Admin paneliga xush kelibsiz! Quyidagi menyudan foydalaning:",
        "not_admin": "❌ Siz admin emassiz!",
        "stats": "📊 Statistika:\n1. Umumiy foydalanuvchilar soni: {total}\n2. Botni bloklaganlar soni: {blocked}\n3. Kunlik foydalanuvchilar soni: {daily}",
        "post_prompt": "📢 Post yozing (matn, rasm yoki video):",
        "post_confirm": "📢 Yuboriladigan post:\n\n{post}\n\nTasdiqlaysizmi?",
        "post_sent": "✅ Post {count} foydalanuvchiga yuborildi!",
        "profile": "👤 Foydalanuvchi profili:\nIsm/Familiya: {name}\nTelefon: {phone}",
        "verify_code": "Tasdiqlash kodi yuborildi: {code}\nIltimos, kodni kiriting:",
        "code_correct": "✅ Kod tasdiqlandi! Botga xush kelibsiz!",
        "code_incorrect": "❌ Noto‘g‘ri kod! Qaytadan kiriting:",
        "error_not_registered": "Iltimos, avval ism va telefon raqamingizni kiriting!"
    },
    "ru": {
        "lang_name": "🇷🇺 Русский",
        "start": "🌐 Пожалуйста, выберите язык:",
        "welcome": "Здравствуйте! 👋\nВы находитесь в официальном Telegram-боте компании PBS IMPEX. 🌍",
        "menu": ["📝 Регистрация", "📞 Оператор", "🛠 Услуги", "👤 Профиль пользователя"],
        "registration_questions": [
            "1️⃣ Загрузите скан паспорта или ID (.jpg, .jpeg, .png, .pdf):",
            "2️⃣ Загрузите скан транспортного паспорта (.jpg, .jpeg, .png, .pdf):",
            "3️⃣ Загрузите международную лицензию на перевозку грузов (.jpg, .jpeg, .png, .pdf):"
        ],
        "initial_questions": [
            "Ваше имя или фамилия?",
            "Ваш номер телефона?"
        ],
        "confirm": "✅ Подтвердить",
        "retry": "🔄 Изменить",
        "home": "🏠 Главное меню",
        "back": "🔙 Назад",
        "received": "✅ Данные получены. Мы скоро свяжемся с вами!",
        "error_invalid_file": "❌ Неверный формат файла! Принимаются только файлы .jpg, .jpeg, .png или .pdf.",
        "error_phone": "❌ Номер телефона неверный! Вводите только цифры. Повторите ввод:",
        "error_phone_length": "❌ Номер телефона должен содержать 9 или 12 цифр! Повторите ввод:",
        "error_no_digits": "❌ В этом поле нельзя использовать цифры! Повторите ввод:",
        "services": "🛠 Услуги",
        "admin_menu": ["📊 Статистика", "📢 Пост", "🏠 Главное меню"],
        "admin_code_prompt": "🔑 Введите код для входа в админ-панель:",
        "admin_welcome": "👨‍💼 Добро пожаловать в админ-панель! Используйте меню ниже:",
        "not_admin": "❌ Вы не администратор!",
        "stats": "📊 Статистика:\n1. Общее число пользователей: {total}\n2. Число заблокировавших бота: {blocked}\n3. Число пользователей за день: {daily}",
        "post_prompt": "📢 Напишите пост (текст, фото или видео):",
        "post_confirm": "📢 Пост для отправки:\n\n{post}\n\nПодтверждаете?",
        "post_sent": "✅ Пост отправлен {count} пользователям!",
        "profile": "👤 Профиль пользователя:\nИмя/Фамилия: {name}\nТелефон: {phone}",
        "verify_code": "Код подтверждения отправлен: {code}\nПожалуйста, введите код:",
        "code_correct": "✅ Код подтвержден! Добро пожаловать в бот!",
        "code_incorrect": "❌ Неверный код! Введите еще раз:",
        "error_not_registered": "Пожалуйста, сначала введите ваше имя и номер телефона!"
    },
    "en": {
        "lang_name": "🇬🇧 English",
        "start": "🌐 Please select a language:",
        "welcome": "Hello! 👋\nYou are in the official Telegram bot of PBS IMPEX. 🌍",
        "menu": ["📝 Registration", "📞 Contact Operator", "🛠 Services", "👤 User Profile"],
        "registration_questions": [
            "1️⃣ Upload a scan of your passport or ID (.jpg, .jpeg, .png, .pdf):",
            "2️⃣ Upload a scan of your transport passport (.jpg, .jpeg, .png, .pdf):",
            "3️⃣ Upload an international cargo transportation license (.jpg, .jpeg, .png, .pdf):"
        ],
        "initial_questions": [
            "Your name or surname?",
            "Your phone number?"
        ],
        "confirm": "✅ Confirm",
        "retry": "🔄 Edit",
        "home": "🏠 Home",
        "back": "🔙 Back",
        "received": "✅ Data received. We will contact you soon!",
        "error_invalid_file": "❌ Invalid file format! Only .jpg, .jpeg, .png, or .pdf files are accepted.",
        "error_phone": "❌ Invalid phone number! Only digits are allowed. Please try again:",
        "error_phone_length": "❌ Phone number must be 9 or 12 digits long! Please try again:",
        "error_no_digits": "❌ Digits are not allowed in this field! Please try again:",
        "services": "🛠 Services",
        "admin_menu": ["📊 Statistics", "📢 Post", "🏠 Home"],
        "admin_code_prompt": "🔑 Enter the code to access the Admin Panel:",
        "admin_welcome": "👨‍💼 Welcome to the Admin Panel! Use the menu below:",
        "not_admin": "❌ You are not an admin!",
        "stats": "📊 Statistics:\n1. Total users: {total}\n2. Users who blocked the bot: {blocked}\n3. Daily users: {daily}",
        "post_prompt": "📢 Write a post (text, photo, or video):",
        "post_confirm": "📢 Post to send:\n\n{post}\n\nConfirm?",
        "post_sent": "✅ Post sent to {count} users!",
        "profile": "👤 User Profile:\nName/Surname: {name}\nPhone: {phone}",
        "verify_code": "Verification code sent: {code}\nPlease enter the code:",
        "code_correct": "✅ Code verified! Welcome to the bot!",
        "code_incorrect": "❌ Incorrect code! Please try again:",
        "error_not_registered": "Please enter your name and phone number first!"
    }
}

# Klaviaturalar
def get_language_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=translations["uz"]["lang_name"], callback_data="lang_uz")],
            [InlineKeyboardButton(text=translations["ru"]["lang_name"], callback_data="lang_ru")],
            [InlineKeyboardButton(text=translations["en"]["lang_name"], callback_data="lang_en")]
        ]
    )

def get_main_menu(lang):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=btn)] for btn in translations[lang]["menu"]],
        resize_keyboard=True
    )

def get_registration_nav(lang):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=translations[lang]["home"])],
            [KeyboardButton(text=translations[lang]["back"])]
        ],
        resize_keyboard=True
    )

def get_services_menu(lang):
    services_menu = {
        "uz": [
            [KeyboardButton(text="🚛 Logistika")],
            [KeyboardButton(text="🧾 Ruxsatnomalar va bojxona xizmatlari")],
            [KeyboardButton(text="🏢 Ma’muriyatchilik ishlari")],
            [KeyboardButton(text="📄 Sertifikatsiya")],
            [KeyboardButton(text=translations[lang]["home"])],
            [KeyboardButton(text=translations[lang]["back"])]
        ],
        "ru": [
            [KeyboardButton(text="🚛 Логистика")],
            [KeyboardButton(text="🧾 Разрешения и таможенные услуги")],
            [KeyboardButton(text="🏢 Административные услуги")],
            [KeyboardButton(text="📄 Сертификация")],
            [KeyboardButton(text=translations[lang]["home"])],
            [KeyboardButton(text=translations[lang]["back"])]
        ],
        "en": [
            [KeyboardButton(text="🚛 Logistics")],
            [KeyboardButton(text="🧾 Permits and Customs Services")],
            [KeyboardButton(text="🏢 Administrative Services")],
            [KeyboardButton(text="📄 Certification")],
            [KeyboardButton(text=translations[lang]["home"])],
            [KeyboardButton(text=translations[lang]["back"])]
        ]
    }
    return ReplyKeyboardMarkup(keyboard=services_menu[lang], resize_keyboard=True)

def get_admin_menu(lang):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=translations[lang]["admin_menu"][0])],
            [KeyboardButton(text=translations[lang]["admin_menu"][1])],
            [KeyboardButton(text=translations[lang]["admin_menu"][2])],
            [KeyboardButton(text=translations[lang]["back"])]
        ],
        resize_keyboard=True
    )

def get_confirm_buttons(lang):
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=translations[lang]["confirm"], callback_data="confirm_registration"),
            InlineKeyboardButton(text=translations[lang]["retry"], callback_data="retry_registration")
        ]]
    )

def get_profile_buttons(lang):
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=translations[lang]["confirm"], callback_data="confirm_profile"),
            InlineKeyboardButton(text=translations[lang]["retry"], callback_data="edit_profile")
        ]]
    )

def get_post_confirm_buttons(lang):
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=translations[lang]["confirm"], callback_data="confirm_post"),
            InlineKeyboardButton(text=translations[lang]["retry"], callback_data="retry_post")
        ]]
    )

# Botni ishga tushirishda buyruqlarni o'rnatish (chap burchakdagi tugmalar)
async def set_bot_commands():
    commands = [
        types.BotCommand(command="start", description="Botni qayta ishga tushirish"),
        types.BotCommand(command="lang", description="Tilni o'zgartirish"),
        types.BotCommand(command="admin", description="Admin paneliga kirish")
    ]
    await bot.set_my_commands(commands)

# Start komandasi
@router.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = str(message.from_user.id)
    today = datetime.now().date().isoformat()
    users.add(user_id)
    if today not in daily_users:
        daily_users[today] = set()
    daily_users[today].add(user_id)
    save_data()

    logger.info(f"Start command received for user_id: {user_id}")
    logger.info(f"Registered users: {registered_users}")
    
    # Har safar til tanlashdan boshlash uchun registered_users tekshiruvi o‘chiriladi
    logger.info(f"Showing language selection for user_id: {user_id}")
    await message.answer(translations["uz"]["start"], reply_markup=get_language_menu())
    
    if user_id in registered_users:
        lang = user_lang.get(user_id, "uz")
        logger.info(f"User {user_id} already registered, showing main menu in language: {lang}")
        await message.answer(translations[lang]["welcome"], reply_markup=get_main_menu(lang))
    else:
        logger.info(f"User {user_id} not registered, showing language selection")
        await message.answer(translations["uz"]["start"], reply_markup=get_language_menu())

# Lang komandasi (Tilni o'zgartirish)
@router.message(Command("lang"))
async def lang_handler(message: types.Message):
    user_id = str(message.from_user.id)
    logger.info(f"Lang command received for user_id: {user_id}")
    await message.answer(translations["uz"]["start"], reply_markup=get_language_menu())

# Admin komandasi
@router.message(Command("admin"))
async def admin_handler(message: types.Message):
    user_id = str(message.from_user.id)
    lang = user_lang.get(user_id, "uz")
    admin_state[user_id] = {"awaiting_code": True}
    logger.info(f"Admin command received for user_id: {user_id}")
    await message.answer(translations[lang]["admin_code_prompt"], reply_markup=get_registration_nav(lang))

@router.callback_query(F.data.startswith("lang_"))
async def handle_language_selection(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    lang = callback.data.split("_")[1]
    user_lang[user_id] = lang

    logger.info(f"Language selected for user_id: {user_id}, language: {lang}")
    logger.info(f"Registered users check: {user_id in registered_users}")

    if user_id in registered_users:
        logger.info(f"User {user_id} already registered, showing main menu")
        await callback.message.edit_text(translations[lang]["welcome"], reply_markup=get_main_menu(lang))
    else:
        logger.info(f"User {user_id} not registered, initiating registration process")
        user_data[user_id] = {"initial_step": 0, "initial_answers": {}, "awaiting_code": False}
        await callback.message.edit_text(translations[lang]["welcome"], reply_markup=None)
        logger.info(f"Calling ask_initial_question for user_id: {user_id}")
        await ask_initial_question(user_id)
    
    await callback.answer()

async def ask_initial_question(user_id):
    lang = user_lang.get(user_id, "uz")
    logger.info(f"ask_initial_question called for user_id: {user_id}, lang: {lang}")
    
    if user_id not in user_data:
        logger.error(f"User {user_id} not found in user_data, resetting")
        user_data[user_id] = {"initial_step": 0, "initial_answers": {}, "awaiting_code": False}
    
    step = user_data[user_id]["initial_step"]
    logger.info(f"Current step for user_id {user_id}: {step}")
    
    if step < len(translations[lang]["initial_questions"]):
        logger.info(f"Asking question {step} to user_id: {user_id}")
        await bot.send_message(user_id, translations[lang]["initial_questions"][step], reply_markup=None)
    elif not user_data[user_id].get("awaiting_code"):
        code = str(random.randint(1000, 9999))
        verification_codes[user_id] = code
        user_data[user_id]["awaiting_code"] = True
        logger.info(f"Sending verification code {code} to user_id: {user_id}")
        await bot.send_message(user_id, translations[lang]["verify_code"].format(code=code), reply_markup=None)
    else:
        logger.info(f"User {user_id} already in verification stage, awaiting code")
        await verify_code(user_id)

async def handle_initial_answer(message: types.Message):
    user_id = str(message.from_user.id)
    lang = user_lang.get(user_id, "uz")
    text = message.text

    logger.info(f"Handling initial answer from user_id: {user_id}, text: {text}")

    if user_id not in user_data:
        logger.error(f"User {user_id} not found in user_data during handle_initial_answer")
        return

    if user_data[user_id].get("awaiting_code"):
        logger.info(f"User {user_id} in verification stage, checking code: {text}")
        if text == verification_codes.get(user_id):
            registered_users[user_id] = user_data[user_id]["initial_answers"]
            save_data()
            logger.info(f"User {user_id} verified successfully")
            await message.answer(translations[lang]["code_correct"], reply_markup=get_main_menu(lang))
            user_data.pop(user_id)
            verification_codes.pop(user_id, None)
        else:
            logger.info(f"User {user_id} entered incorrect code: {text}")
            await message.answer(translations[lang]["code_incorrect"], reply_markup=None)
        return

    step = user_data[user_id]["initial_step"]
    logger.info(f"Processing step {step} for user_id: {user_id}")

    if step == 1:
        cleaned_text = text.replace("+", "").replace(" ", "")
        if not cleaned_text.isdigit():
            logger.info(f"Invalid phone number from user_id: {user_id}")
            await message.answer(translations[lang]["error_phone"], reply_markup=None)
            return
        if len(cleaned_text) not in [9, 12]:
            logger.info(f"Phone number length invalid for user_id: {user_id}")
            await message.answer(translations[lang]["error_phone_length"], reply_markup=None)
            return
    elif step == 0:
        if any(char.isdigit() for char in text):
            logger.info(f"Name contains digits for user_id: {user_id}")
            await message.answer(translations[lang]["error_no_digits"], reply_markup=None)
            return

    question = translations[lang]["initial_questions"][step]
    user_data[user_id]["initial_answers"][question] = text
    user_data[user_id]["initial_step"] += 1
    logger.info(f"Answer saved for user_id: {user_id}, proceeding to next step")
    await ask_initial_question(user_id)

# Ro'yxatdan o'tish jarayoni
@router.message(F.text.in_(["📝 Ro'yxatdan o'tish", "📝 Регистрация", "📝 Registration"]))
async def start_registration(message: types.Message):
    user_id = str(message.from_user.id)
    lang = user_lang.get(user_id, "uz")
    logger.info(f"Starting registration for user_id: {user_id}")
    if user_id not in registered_users:
        logger.info(f"User {user_id} not registered, prompting to register")
        await message.answer(translations[lang]["error_not_registered"], reply_markup=get_main_menu(lang))
        return
    user_data[user_id] = {"step": 0, "documents": {}, "file_types": {}}
    await ask_registration_question(user_id)

async def ask_registration_question(user_id):
    lang = user_lang.get(user_id, "uz")
    step = user_data[user_id]["step"]
    if step < len(translations[lang]["registration_questions"]):
        await bot.send_message(user_id, translations[lang]["registration_questions"][step], reply_markup=get_registration_nav(lang))
    else:
        await show_registration_summary(user_id)

@router.message(F.document | F.photo)
async def handle_document(message: types.Message):
    user_id = str(message.from_user.id)
    lang = user_lang.get(user_id, "uz")
    if user_id not in user_data or "step" not in user_data[user_id]:
        return
    step = user_data[user_id]["step"]
    file_id = None
    file_type = None
    if message.document:
        if message.document.mime_type not in ["application/pdf", "image/jpeg", "image/png"]:
            await message.answer(translations[lang]["error_invalid_file"])
            return
        file_id = message.document.file_id
        file_type = "document"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    if file_id:
        user_data[user_id]["documents"][step] = file_id
        user_data[user_id]["file_types"][step] = file_type
        user_data[user_id]["step"] += 1
        await ask_registration_question(user_id)

async def show_registration_summary(user_id):
    lang = user_lang.get(user_id, "uz")
    summary = "📝 Yuklangan hujjatlar:\n"
    for i, doc in user_data[user_id]["documents"].items():
        summary += f"{translations[lang]['registration_questions'][i]}\n"
    await bot.send_message(user_id, summary, reply_markup=get_confirm_buttons(lang))

@router.callback_query(F.data == "confirm_registration")
async def confirm_registration(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    lang = user_lang.get(user_id, "uz")
    documents = user_data[user_id]["documents"]
    file_types = user_data[user_id]["file_types"]
    
    message_text = f"📝 Yangi ro'yxatdan o'tgan foydalanuvchi: @{callback.from_user.username}\n"
    if user_id in registered_users:
        initial_data = registered_users[user_id]
        name_key = translations[lang]["initial_questions"][0]
        phone_key = translations[lang]["initial_questions"][1]
        message_text += f"Ism/Familiya: {initial_data.get(name_key, 'Nomalum')}\n"
        message_text += f"Telefon: {initial_data.get(phone_key, 'Nomalum')}\n"

    for i, doc in documents.items():
        file_type = file_types[i]
        if file_type == "photo":
            await bot.send_photo(CHANNEL_ID, doc, caption=f"{translations[lang]['registration_questions'][i]}")
        elif file_type == "document":
            await bot.send_document(CHANNEL_ID, doc, caption=f"{translations[lang]['registration_questions'][i]}")
    await bot.send_message(CHANNEL_ID, message_text)

    await callback.message.answer(translations[lang]["received"], reply_markup=get_main_menu(lang))
    user_data.pop(user_id, None)

@router.callback_query(F.data == "retry_registration")
async def retry_registration(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    lang = user_lang.get(user_id, "uz")
    user_data[user_id] = {"step": 0, "documents": {}, "file_types": {}}
    await ask_registration_question(user_id)

# Asosiy menyu va funksiyalar
@router.message(F.text)
async def handle_language_and_menu(message: types.Message):
    user_id = str(message.from_user.id)
    lang = user_lang.get(user_id, "uz")
    logger.info(f"Foydalanuvchi {user_id} yubordi: {message.text}")

    today = datetime.now().date().isoformat()
    if today not in daily_users:
        daily_users[today] = set()
    daily_users[today].add(user_id)
    save_data()

    if user_id in user_data and "initial_step" in user_data[user_id]:
        logger.info(f"User {user_id} in initial registration phase")
        await handle_initial_answer(message)
        return

    if message.text == translations[lang]["home"]:
        admin_state.pop(user_id, None)
        user_data.pop(user_id, None)
        await message.answer(translations[lang]["welcome"], reply_markup=get_main_menu(lang))
        return

    elif message.text == translations[lang]["menu"][1]:
        operator_info = {
            "uz": """<b>«PBS IMPEX» XK</b>
🏢 Manzil: Toshkent shahri, Nukus ko‘chasi, 3 uy
📞 Telefon: +99871 2155638
👨‍💼 Sale menedjer: Mohirjon Rustamov
📱 +99891 166-75-36
✉️ E-mail: office@pbs-impex.uz
🌐 Web: https://pbs-impex.uz/""",
            "ru": """<b>«PBS IMPEX» ЧП</b>
🏢 Адрес: г. Ташкент, улица Нукус, дом 3
📞 Телефон: +99871 2155638
👨‍💼 Менеджер по продажам: Мохиржон Рустамов
📱 +99891 166-75-36
✉️ E-mail: office@pbs-impex.uz
🌐 Сайт: https://pbs-impex.uz/""",
            "en": """<b>«PBS IMPEX» LLC</b>
🏢 Address: Nukus street 3, Tashkent
📞 Phone: +99871 2155638
👨‍💼 Sales Manager: Mohirjon Rustamov
📱 +99891 166-75-36
✉️ E-mail: office@pbs-impex.uz
🌐 Website: https://pbs-impex.uz/"""
        }
        await message.answer(operator_info[lang], reply_markup=get_main_menu(lang), parse_mode="HTML")
        return

    elif message.text == translations[lang]["menu"][2]:
        await message.answer(translations[lang]["services"], reply_markup=get_services_menu(lang))
        return

    elif message.text == translations[lang]["menu"][3]:
        if user_id in registered_users:
            initial_data = registered_users[user_id]
            name_key = translations[lang]["initial_questions"][0]
            phone_key = translations[lang]["initial_questions"][1]
            profile_text = translations[lang]["profile"].format(
                name=initial_data.get(name_key, "Nomalum"),
                phone=initial_data.get(phone_key, "Nomalum")
            )
            await message.answer(profile_text, reply_markup=get_profile_buttons(lang))
        else:
            await message.answer(translations[lang]["error_not_registered"], reply_markup=get_main_menu(lang))
        return

    elif user_id in admin_state and admin_state[user_id].get("awaiting_code"):
        if message.text == ADMIN_CODE:
            admin_state[user_id] = {"in_admin": True}
            await message.answer(translations[lang]["admin_welcome"], reply_markup=get_admin_menu(lang))
        else:
            admin_state.pop(user_id, None)
            await message.answer(translations[lang]["not_admin"], reply_markup=get_main_menu(lang))
        return

    elif user_id in admin_state and admin_state[user_id].get("in_admin"):
        if message.text == translations[lang]["admin_menu"][0]:
            today = datetime.now().date().isoformat()
            stats_text = translations[lang]["stats"].format(
                total=len(users),
                blocked=len(blocked_users),
                daily=len(daily_users.get(today, set()))
            )
            await message.answer(stats_text, reply_markup=get_admin_menu(lang))
        elif message.text == translations[lang]["admin_menu"][1]:
            admin_state[user_id] = {
                "in_admin": True,
                "awaiting_post": True,
                "post_content": {"text": None, "photo": None, "video": None}
            }
            await message.answer(translations[lang]["post_prompt"], reply_markup=get_registration_nav(lang))
        elif message.text == translations[lang]["admin_menu"][2]:
            admin_state.pop(user_id, None)
            await message.answer(translations[lang]["welcome"], reply_markup=get_main_menu(lang))
        elif message.text == translations[lang]["back"]:
            admin_state[user_id] = {"in_admin": True}
            await message.answer(translations[lang]["admin_welcome"], reply_markup=get_admin_menu(lang))
        return

    elif message.text in ["🚛 Logistika", "🚛 Логистика", "🚛 Logistics"]:
        logistics_text = {
            "uz": """✅ <b>Logistika xizmati</b>
• Malakali maslahat berish
• Transport vositalarining qulay kombinatsiyasi (avia, avto, temir yo‘l, suv) asosida optimal yo‘nalish ishlab chiqish
• Xarajatlarni hisoblash
• Kerakli hujjatlarni rasmiylashtirish
• Sug‘urta shartlarini qulaylashtirish
• Yuk tashish bosqichlari bo‘yicha hisobot berish
• Hilma-hil mamlakatlardan kelgan yuklarni reeksport mamlakatida to‘plash
• \"Eshikdan eshikgacha\" xizmati
• Toshkent va O‘zbekiston bo‘ylab shaxsiy transportda yuk tashish (5 tonna/20 kub; 1.5 tonna/14 kub)
• Texnik Iqtisodiy Asos shartlariga asosan yuk tashishni tashkil etish""",
            "ru": """✅ <b>Логистические услуги</b>
• Консультации от специалистов
• Оптимальный маршрут с учетом различных видов транспорта (авиа, авто, жд, морской)
• Расчет затрат
• Оформление всех необходимых документов
• Упрощение условий страхования
• Отчетность по каждому этапу перевозки
• Консолидация грузов из разных стран в стране реэкспорта
• Услуга \"от двери до двери\"
• Перевозки по Ташкенту и всей Узбекистану (5 тонн/20 куб; 1.5 тонн/14 куб)
• Организация перевозок на основе ТЭО""",
            "en": """✅ <b>Logistics Service</b>
• Professional consulting
• Optimal route planning using air, road, rail, and sea transport
• Cost calculation
• Document processing
• Simplified insurance terms
• Reporting for each transport stage
• Consolidation of goods from different countries in re-export country
• Door-to-door service
• Local transport across Tashkent and Uzbekistan (5 ton/20 m³; 1.5 ton/14 m³)
• Full logistics based on feasibility studies"""
        }
        await message.answer(logistics_text[lang], parse_mode="HTML", reply_markup=get_services_menu(lang))
        return

    elif message.text in ["🧾 Ruxsatnomalar va bojxona xizmatlari", "🧾 Разрешения и таможенные услуги", "🧾 Permits and Customs Services"]:
        customs_text = {
            "uz": """✅ <b>Ruxsatnomalar va bojxona xizmatlari</b>
• Tashqi savdo shartnomalarini tuzishda maslahat va ularni ro‘yxatdan o‘tkazish
• TIF TN kodi asosida ekspert xulosasi va bojxona moslashtirish
• Import/eksportdagi xarajatlar bo‘yicha ma’lumot
• Yuk hujjatlarini olish, raskreditovka qilish, bojxonada ro‘yxatga olish
• Bojxona xizmatlarini bojxona skladigacha yoki kerakli manzilgacha yetkazish
• Skladga qo‘yish va nazorat qilish
• Bojxona deklaratsiyasini tayyorlash""",
            "ru": """✅ <b>Разрешения и таможенные услуги</b>
• Консультации по внешнеторговым контрактам и их регистрация
• Экспертное заключение по ТН ВЭД и согласование с таможней
• Информация по затратам на импорт/экспорт
• Получение документов, раскредитовка, регистрация, сопровождение
• Таможенные услуги до склада или по нужному адресу
• Хранение и контроль на складе
• Подготовка таможенной декларации""",
            "en": """✅ <b>Permits and Customs Services</b>
• Consulting on foreign trade contracts and registration
• Expert opinion based on HS Code and customs approval
• Info on import/export costs
• Document handling, clearance, customs registration
• Customs service delivery to warehouse or specified address
• Storage and monitoring
• Preparation of customs declaration"""
        }
        await message.answer(customs_text[lang], parse_mode="HTML", reply_markup=get_services_menu(lang))
        return

    elif message.text in ["🏢 Ma’muriyatchilik ishlari", "🏢 Административные услуги", "🏢 Administrative Services"]:
        admin_text = {
            "uz": """✅ <b>Ma’muriyatchilik ishlari</b>
• Mijozlarimiz tovariga buyurtma va talabnomalarni joylashtirish
• Tovarni sotib olish shartnomalarini muvofiqlashtirish
• Yetkazib berish muddati, narxi va xarakteristikasini moslashtirish
• Tovar va transport hujjatlarini muvofiqlashtirish
• Invoyslarni olish va tekshirish
• \"Back orders\" holatini nazorat qilish
• Buyurtmalarni yig‘ish va jo‘natish""",
            "ru": """✅ <b>Административные услуги</b>
• Размещение заказов и заявок на товары клиентов
• Согласование контрактов на закупку
• Согласование сроков, цены и характеристик поставки
• Согласование товарных и транспортных документов
• Получение и проверка инвойсов
• Контроль \"Back orders\"
• Сбор и отправка заказов""",
            "en": """✅ <b>Administrative Services</b>
• Placing orders and requests for client goods
• Coordinating purchase contracts
• Adjusting delivery time, price, and specifications
• Coordinating goods and transport documents
• Receiving and verifying invoices
• Controlling \"Back orders\"
• Collecting and dispatching orders"""
        }
        await message.answer(admin_text[lang], parse_mode="HTML", reply_markup=get_services_menu(lang))
        return

    elif message.text in ["📄 Sertifikatsiya", "📄 Сертификация", "📄 Certification"]:
        cert_text = {
            "uz": """✅ <b>Sertifikatsiya</b>
• Tovar uchun har xil sertifikatlarni olish (kerak bo‘lganda)
• Akkreditatsiyaga ega laboratoriyalardan sinov protokollarini va xulosalarni olish
• Yukni olib kirish yoki olib chiqish uchun kerakli ruxsat xatlarini olish
• O‘lchash vositalarini metrologik attestatsiyadan o‘tkazish
• Tovarning soni va sifati uchun ekspertiza va inspeksiya
• Sertifikatsiya uchun namunalarni tanlab olishni tashkillashtirish""",
            "ru": """✅ <b>Сертификация</b>
• Получение различных сертификатов для товаров (при необходимости)
• Получение протоколов испытаний и заключений из аккредитованных лабораторий
• Получение разрешений на ввоз или вывоз груза
• Метрологическая аттестация измерительных средств
• Экспертиза и инспекция количества и качества товара
• Организация отбора образцов для сертификации""",
            "en": """✅ <b>Certification</b>
• Obtaining various product certificates (if needed)
• Getting test reports and conclusions from accredited laboratories
• Obtaining permits for cargo import or export
• Metrological certification of measuring instruments
• Product quantity and quality inspection
• Organizing sample selection for certification"""
        }
        await message.answer(cert_text[lang], parse_mode="HTML", reply_markup=get_services_menu(lang))
        return

    elif message.text == translations[lang]["back"]:
        await message.answer(translations[lang]["welcome"], reply_markup=get_main_menu(lang))
        return

# Profil tugmalari
@router.callback_query(F.data == "confirm_profile")
async def confirm_profile(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    lang = user_lang.get(user_id, "uz")
    await callback.message.delete()
    await bot.send_message(user_id, translations[lang]["welcome"], reply_markup=get_main_menu(lang))

@router.callback_query(F.data == "edit_profile")
async def edit_profile(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    lang = user_lang.get(user_id, "uz")
    user_data[user_id] = {"initial_step": 0, "initial_answers": {}, "awaiting_code": False}
    await callback.message.delete()
    await ask_initial_question(user_id)

# Admin post filtiri
class IsAwaitingPost(Filter):
    async def __call__(self, message: types.Message) -> bool:
        user_id = str(message.from_user.id)
        return admin_state.get(user_id, {}).get("awaiting_post", False)

@router.message(IsAwaitingPost(), F.text | F.photo | F.video)
async def handle_admin_post(message: types.Message):
    user_id = str(message.from_user.id)
    lang = user_lang.get(user_id, "uz")

    if message.text == translations[lang]["back"]:
        admin_state[user_id] = {"in_admin": True}
        await message.answer(translations[lang]["admin_welcome"], reply_markup=get_admin_menu(lang))
        return

    if message.text:
        admin_state[user_id]["post_content"]["text"] = message.text
    elif message.photo:
        admin_state[user_id]["post_content"]["photo"] = message.photo[-1].file_id
    elif message.video:
        admin_state[user_id]["post_content"]["video"] = message.video.file_id

    await show_post_preview(user_id, message)

async def show_post_preview(user_id, message: types.Message):
    lang = user_lang.get(user_id, "uz")
    post_content = admin_state[user_id]["post_content"]
    preview_text = translations[lang]["post_confirm"].format(post=post_content["text"] or "Matn yo‘q")

    if post_content["photo"]:
        await bot.send_photo(user_id, post_content["photo"], caption=post_content["text"] or "", reply_markup=get_post_confirm_buttons(lang))
    elif post_content["video"]:
        await bot.send_video(user_id, post_content["video"], caption=post_content["text"] or "", reply_markup=get_post_confirm_buttons(lang))
    elif post_content["text"]:
        await bot.send_message(user_id, preview_text, reply_markup=get_post_confirm_buttons(lang))
    else:
        await bot.send_message(user_id, "❌ Hech qanday kontent kiritilmadi!", reply_markup=get_registration_nav(lang))

@router.callback_query(F.data == "confirm_post")
async def confirm_post(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    lang = user_lang.get(user_id, "uz")
    post_content = admin_state[user_id]["post_content"]
    sent_count = 0

    for uid in users:
        if uid not in blocked_users:
            try:
                if post_content["photo"]:
                    await bot.send_photo(uid, post_content["photo"], caption=post_content["text"] or "")
                elif post_content["video"]:
                    await bot.send_video(uid, post_content["video"], caption=post_content["text"] or "")
                elif post_content["text"]:
                    await bot.send_message(uid, post_content["text"])
                sent_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Post yuborishda xatolik: {e}")
                blocked_users.add(uid)
                save_data()

    await callback.message.delete()
    await bot.send_message(user_id, translations[lang]["post_sent"].format(count=sent_count), reply_markup=get_admin_menu(lang))
    admin_state[user_id] = {"in_admin": True}

@router.callback_query(F.data == "retry_post")
async def retry_post(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    lang = user_lang.get(user_id, "uz")
    admin_state[user_id] = {
        "in_admin": True,
        "awaiting_post": True,
        "post_content": {"text": None, "photo": None, "video": None}
    }
    await callback.message.delete()
    await bot.send_message(user_id, translations[lang]["post_prompt"], reply_markup=get_registration_nav(lang))

# Webhook server
async def on_startup():
    load_data()
    await set_bot_commands()  # Bot buyruqlarini o'rnatish
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await bot.set_webhook(url=WEBHOOK_URL)
    logging.info(f"Webhook set to {WEBHOOK_URL}")

async def on_shutdown():
    await bot.delete_webhook()
    await bot.session.close()
    logging.info("Bot shutdown")

async def main():
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
    await site.start()

    try:
        await asyncio.Event().wait()  # Keep the server running
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
