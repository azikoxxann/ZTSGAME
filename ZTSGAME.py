import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
import threading
import logging
from dotenv import load_dotenv
import time
import random
from datetime import datetime, timedelta, timezone

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(asctime)s - %(message)s')

# Загружаем переменные окружения
load_dotenv()
TOKEN = os.getenv("API_TOKEN")
if not TOKEN:
    logging.error("Ошибка: API_TOKEN не найден в .env файле.")
    exit()
bot = telebot.TeleBot(TOKEN)

# Файл с данными игроков
data_file = 'players.json'

# Загружаем данные
if os.path.exists(data_file):
    with open(data_file, 'r') as f:
        players = json.load(f)
else:
    players = {}

# Создаем словарь для хранения времени последнего нажатия для каждого пользователя
last_click_time = {}

# Ежедневное количество топлива и лимит покупки билетов
DAILY_FUEL = 10000
DAILY_TICKET_LIMIT = 20

def save_data():
    try:
        with open(data_file, 'w') as f:
            json.dump(players, f, indent=4)
        logging.info("Данные успешно сохранены")
    except Exception as e:
        logging.error(f"Ошибка при сохранении данных: {e}")

def get_player(user_id):
    if str(user_id) not in players:
        players[str(user_id)] = {
            "balance": 0,
            "power": 1,
            "referrals": 0,
            "boost": False,
            "race_ticket": False,
            "fuel": DAILY_FUEL,
            "last_fuel_update": datetime.now(timezone.utc).isoformat(),
            "ticket_purchases": 0,
            "last_ticket_update": datetime.now(timezone.utc).isoformat()
        }
        logging.info(f"Создан новый игрок: {user_id}")
    return players[str(user_id)]

def update_fuel_and_tickets(player):
    last_fuel_update = datetime.fromisoformat(player["last_fuel_update"])
    last_ticket_update = datetime.fromisoformat(player["last_ticket_update"])
    now = datetime.now(timezone.utc)
    
    if (now - last_fuel_update).days >= 1:
        player["fuel"] = DAILY_FUEL
        player["last_fuel_update"] = now.isoformat()
        logging.info(f"Топливо обновлено для игрока {player}")
    
    if (now - last_ticket_update).days >= 1:
        player["ticket_purchases"] = 0
        player["last_ticket_update"] = now.isoformat()
        logging.info(f"Лимит покупок билетов обновлен для игрока {player}")

def get_main_keyboard(user_id):
    player = get_player(user_id)
    update_fuel_and_tickets(player)
    if not player:
        return None, "Ошибка: Не удалось получить данные игрока."
    upgrade_cost = player["power"] * 10
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🚀 Газ в пол!", callback_data='earn'))
    keyboard.add(InlineKeyboardButton("🛠 Апгрейды", callback_data='upgrade'))
    keyboard.add(InlineKeyboardButton("🛒 Магазин", callback_data='shop'))
    keyboard.add(InlineKeyboardButton("🏎 Гонки", callback_data='race'))
    stats = f"💰 Баланс: {player['balance']} | 🚛 Мощность: {player['power']}\n🔧 Стоимость улучшения: {upgrade_cost} монет\n⚡ Буст активен: {'✅' if player['boost'] else '❌'} | 🎟 Билет на гонки: {'✅' if player['race_ticket'] else '❌'}\n⛽ Топливо: {player['fuel']} | 🛒 Покупок билетов: {player['ticket_purchases']}/{DAILY_TICKET_LIMIT}"
    return keyboard, stats

def is_cooldown_over(user_id, cooldown=1.5):
    current_time = time.time()
    if user_id in last_click_time:
        elapsed_time = current_time - last_click_time[user_id]
        if elapsed_time < cooldown:
            return False
    last_click_time[user_id] = current_time
    return True

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    logging.info(f"Пользователь {user_id} начал игру")
    get_player(user_id)
    save_data()
    keyboard, stats = get_main_keyboard(user_id)
    bot.send_message(user_id, f"🚛 Добро пожаловать в *Тап Монеты: Зона Трака*!\nТапай кнопку, зарабатывай монеты и прокачивай трак!\n\n{stats}", parse_mode='Markdown', reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == 'earn')
def earn_money(call):
    user_id = call.message.chat.id
    if not is_cooldown_over(user_id):
        bot.answer_callback_query(call.id, "⏳ Подожди немного перед следующим нажатием!")
        return
    player = get_player(user_id)
    update_fuel_and_tickets(player)
    if player["fuel"] <= 0:
        bot.answer_callback_query(call.id, "❌ Топливо закончилось! Попробуй завтра.")
        return
    earnings = player["power"] * (2 if player["boost"] else 1)
    if player["fuel"] < earnings:
        earnings = player["fuel"]
    player["balance"] += earnings
    player["fuel"] -= earnings
    logging.info(f"Игрок {user_id} заработал {earnings} монет и потратил {earnings} топлива")
    save_data()
    keyboard, stats = get_main_keyboard(user_id)
    bot.answer_callback_query(call.id, f"💰 Ты заработал {earnings} монет!")
    bot.edit_message_text(f"🚛 *Тап Монеты: Зона Трака*\n\n{stats}", user_id, call.message.message_id, parse_mode='Markdown', reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == 'shop')
def shop(call):
    user_id = call.message.chat.id
    if not is_cooldown_over(user_id):
        bot.answer_callback_query(call.id, "⏳ Подожди немного перед следующим нажатием!")
        return
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⚡ Купить буст (100 монет)", callback_data='buy_boost'))
    keyboard.add(InlineKeyboardButton("🎟 Купить билет (200 монет)", callback_data='buy_ticket'))
    keyboard.add(InlineKeyboardButton("⬅ Назад", callback_data='back'))
    logging.info(f"Игрок {user_id} открыл магазин")
    bot.edit_message_text("🛒 Магазин:\nВыберите товар:", user_id, call.message.message_id, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == 'buy_boost')
def buy_boost(call):
    user_id = call.message.chat.id
    if not is_cooldown_over(user_id):
        bot.answer_callback_query(call.id, "⏳ Подожди немного перед следующим нажатием!")
        return
    player = get_player(user_id)
    if player["balance"] >= 100:
        player["balance"] -= 100
        player["boost"] = True
        logging.info(f"Игрок {user_id} купил буст")
        save_data()
        bot.answer_callback_query(call.id, "⚡ Буст активирован на 1 минуту!")
        threading.Timer(60, disable_boost, [user_id]).start()
    else:
        logging.warning(f"Игроку {user_id} не хватило монет на буст")
        bot.answer_callback_query(call.id, "❌ Не хватает монет!")

def disable_boost(user_id):
    players[str(user_id)]["boost"] = False
    save_data()
    logging.info(f"Буст отключен у игрока {user_id}")

@bot.callback_query_handler(func=lambda call: call.data == 'back')
def back_to_main(call):
    user_id = call.message.chat.id
    if not is_cooldown_over(user_id):
        bot.answer_callback_query(call.id, "⏳ Подожди немного перед следующим нажатием!")
        return
    keyboard, stats = get_main_keyboard(user_id)
    logging.info(f"Игрок {user_id} вернулся на главный экран")
    bot.edit_message_text(f"🚛 *Тап Монеты: Зона Трака*\n\n{stats}", user_id, call.message.message_id, parse_mode='Markdown', reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == 'upgrade')
def upgrade_menu(call):
    user_id = call.message.chat.id
    if not is_cooldown_over(user_id):
        bot.answer_callback_query(call.id, "⏳ Подожди немного перед следующим нажатием!")
        return
    player = get_player(user_id)
    upgrade_cost = player["power"] * 10

    if player["balance"] >= upgrade_cost:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(f"Улучшить (Стоимость: {upgrade_cost})", callback_data='confirm_upgrade'))
        keyboard.add(InlineKeyboardButton("⬅ Назад", callback_data='back'))
        bot.edit_message_text(f" Апгрейды:\nВаша текущая мощность: {player['power']}\nУлучшить мощность?", user_id, call.message.message_id, reply_markup=keyboard)
    else:
        bot.answer_callback_query(call.id, "❌ Не хватает монет!")

@bot.callback_query_handler(func=lambda call: call.data == 'confirm_upgrade')
def confirm_upgrade(call):
    user_id = call.message.chat.id
    if not is_cooldown_over(user_id):
        bot.answer_callback_query(call.id, "⏳ Подожди немного перед следующим нажатием!")
        return
    player = get_player(user_id)
    upgrade_cost = player["power"] * 10
    player["balance"] -= upgrade_cost
    player["power"] += 1
    save_data()
    keyboard, stats = get_main_keyboard(user_id)
    bot.edit_message_text(f" *Тап Монеты: Зона Трака*\n\n{stats}", user_id, call.message.message_id, parse_mode='Markdown', reply_markup=keyboard)
    bot.answer_callback_query(call.id, " Мощность улучшена!")

@bot.callback_query_handler(func=lambda call: call.data == 'race')
def race(call):
    user_id = call.message.chat.id
    if not is_cooldown_over(user_id):
        bot.answer_callback_query(call.id, "⏳ Подожди немного перед следующим нажатием!")
        return
    player = get_player(user_id)

    if not player["race_ticket"]:
        bot.answer_callback_query(call.id, "❌ Нет билета на гонки!")
        return

    if player["balance"] < 200:
        bot.answer_callback_query(call.id, "❌ Не хватает монет для участия!")
        return

    player["balance"] -= 200
    player["race_ticket"] = False  # Используем билет
    save_data()

    if random.choice([True, False]):  # Рандомный выбор: True - победа, False - поражение
        player["balance"] += 400  # Выигрыш: возвращаем 200 + 200 призовых
        result_message = " Вы победили! +200 монет!"
    else:
        result_message = " Вы проиграли! -200 монет!"

    save_data()
    keyboard, stats = get_main_keyboard(user_id)
    bot.edit_message_text(f" *Тап Монеты: Зона Трака*\n\n{result_message}\n\n{stats}", user_id, call.message.message_id, parse_mode='Markdown', reply_markup=keyboard)
    bot.answer_callback_query(call.id, result_message)

@bot.callback_query_handler(func=lambda call: call.data == 'buy_ticket')
def buy_ticket(call):
    user_id = call.message.chat.id
    if not is_cooldown_over(user_id):
        bot.answer_callback_query(call.id, "⏳ Подожди немного перед следующим нажатием!")
        return
    player = get_player(user_id)
    update_fuel_and_tickets(player)
    if player["ticket_purchases"] >= DAILY_TICKET_LIMIT:
        bot.answer_callback_query(call.id, "❌ Лимит покупок билетов на сегодня исчерпан!")
        return
    if player["balance"] >= 200:
        player["balance"] -= 200
        player["race_ticket"] = True
        player["ticket_purchases"] += 1
        save_data()
        bot.answer_callback_query(call.id, " Билет куплен!")
        keyboard, stats = get_main_keyboard(user_id)
        bot.edit_message_text(f" *Тап Монеты: Зона Трака*\n\n{stats}", user_id, call.message.message_id, parse_mode='Markdown', reply_markup=keyboard)
    else:
        bot.answer_callback_query(call.id, "❌ Не хватает монет!")

bot.polling(none_stop=True)