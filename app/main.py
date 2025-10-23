import telebot
from telebot import types
from settings import TOKEN

bot = telebot.TeleBot(TOKEN)

def send_instruction(message):
    """
        Отправка инструкции пользователю
    """
    instruction = (
        "<b>Инструкция:</b>\n\n"
        "Теперь вы можете вводить свои запросы прямо сюда.\n"
        "<u>Важно:</u> вводите запросы на английском языке.\n\n"
        "Например:\n"
        "— LLM use tools\n"
        "— LLM Training and Optimization\n"
        "— Prompt Engineering\n\n"
        "Бот проанализирует ваш запрос и выдаст подходящие статьи."
    )
    bot.send_message(message.chat.id, instruction, parse_mode="HTML")


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
        Обработка пользовательских запросов
    """
    user_text = message.text.strip()
    bot.send_message(message.chat.id, f"Вы ввели запрос: <b>{user_text}</b>", parse_mode="HTML")


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
    bot.polling(non_stop=True)
