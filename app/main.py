import os
import telebot
from telebot import types
from app.modules.recommender import get_recommendations
from app.logs.logger import logger
from dotenv import load_dotenv

load_dotenv()
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))

user_states = {}

# ============
def send_instruction(message):
    """
        Отправка инструкции пользователю
    """
    instruction = (
        "<b>Инструкция:</b>\n\n"
        "Теперь вы можете вводить свои запросы.\n"
        "<u>Важно:</u> вводите запросы на английском языке.\n\n"
        "Например:\n"
        "— LLM use tools\n"
        "— LLM Training and Optimization\n"
        "— Prompt Engineering\n\n"
        "Бот проанализирует ваш запрос и выдаст подходящие статьи."
    )
    logger.info(f"Пользователю {message.chat.id} отправлена инструкция.")
    bot.send_message(message.chat.id, instruction, parse_mode="HTML")


# ============
def is_valid_query(chat_id, text: str) -> bool:
    """
        Проверка пользовательского запроса
    """
    if user_states.get(chat_id, False):
        logger.warning(f"Пользователь {chat_id} попытался отправить новый запрос до завершения предыдущего.")
        bot.send_message(chat_id, "Подождите, предыдущий запрос еще обрабатывается.")
        return False

    if text.startswith('/') and text[1:] not in ["start", "instruction", "help"]:
        logger.warning(f"Пользователь {chat_id} отправил неизвестную команду: {text}.")
        bot.send_message(chat_id, "Неизвестная команда. Введите /help для списка доступных команд.")
        return False

    if text.lower() == "инструкция":
        return False

    return True


# ============
def format_articles_message(articles: list[dict]) -> str:
    """
        Список статей
    """
    if not articles:
        return "<b>Результат:</b>\n\nНичего не найдено"

    msg_parts = []
    for ind, art in enumerate(articles, start=1):
        title = art.get("title", "Без названия")
        link = art.get("link", "")
        citations = art.get("info", {}).get("citation_count", 0)

        msg_parts.append(
            f"<b>{ind}. {title}</b>\n"
            f"<a href='{link}'>Ссылка на arXiv</a>\n"
            f"Число цитирований: {citations}\n\n"
        )

    return "<b>Результат:</b>\n\n" + "".join(msg_parts)


# ============
@bot.message_handler(commands=['start'])
def start_function(message):
    """ 
        Команда /start
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    button = types.KeyboardButton("Инструкция")
    markup.add(button)

    text = (
        f"<b>{message.from_user.first_name}</b>, добро пожаловать!\n\n"
        "Нажмите кнопку \"Инструкция\" или введите \"/instruction\", чтобы узнать, как начать работу."
    )

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="HTML",
        reply_markup=markup
    )


# ============
@bot.message_handler(commands=['instruction'])
def handle_instruction_command(message):
    """ 
        Команда /instruction
    """
    send_instruction(message)

@bot.message_handler(func=lambda msg: msg.text == "Инструкция")
def handle_instruction_button(message):
    """ 
        Кнопка "Инструкция"
    """
    send_instruction(message)


# ============
@bot.message_handler(commands=['help'])
def help_function(message):
    """
        Команда /help
    """
    logger.info(f"Пользователь {message.chat.id} запросил справку.")
    bot.send_message(
        message.chat.id,
        "Доступные команды:\n"
        "/start — начать заново\n"
        "/instruction — показать инструкцию\n"
        "/help — показать справку"
    )


# ============
@bot.message_handler(func=lambda msg: True)
def handle_user_query(message):
    """
        Обрваботка пользовательских запросов
    """
    chat_id = message.chat.id
    user_text = message.text.strip()
    if not is_valid_query(chat_id, user_text):
        return
    
    user_states[chat_id] = True
    logger.info(f"Получен запрос от пользователя {chat_id}: {user_text}")
    bot.send_message(
        chat_id,
        f"Вы ввели запрос: <b>{user_text}</b>\n\nОжидайте...",
        parse_mode="HTML"
    )

    try:
        articles = get_recommendations(user_text)
        logger.info(f"Запрос пользователя {chat_id} обработан успешно. Найдено статей: {len(articles)}")
        formatted_msg = format_articles_message(articles)
        bot.send_message(
            chat_id,
            formatted_msg,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.exception(f"Ошибка при обработке запроса от пользователя {chat_id}: {e}")
        bot.send_message(chat_id, "Непредвиденная ошибка при обработке вашего запроса.")
    finally:
        user_states[chat_id] = False


# ============
def set_bot_commands():
    """
        Установка списка доступных команд
    """
    commands = [
        telebot.types.BotCommand("start", "Начать заново"),
        telebot.types.BotCommand("instruction", "Показать инструкцию"),
        telebot.types.BotCommand("help", "Показать справку"),
    ]
    bot.set_my_commands(commands)


if __name__ == "__main__":
    set_bot_commands()
    logger.info("Начало работы бота.")
    bot.polling(non_stop=True)
