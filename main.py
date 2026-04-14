from data import get_user_data, insert_data, update_data, select_data
from telebot import TeleBot
from config import BOT_TOKEN
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telebot import types
import data
import logging
from subtitles import search_in_db, get_random_quote
import requests
import threading
from datetime import datetime, timedelta
from personal_vocabulary import save_to_vocabulary_db, get_personal_vocabulary
from deep_translator import GoogleTranslator
import textwrap
import sqlite3

bot = TeleBot(BOT_TOKEN)


help_message = ('''Я — бот, который поможет Вам прокачать свой уровень знания английского языка с помощью просмотра фильмов.
Учить английский язык по любимым фильмам и сериалам — заманчивая идея: вы совмещаете приятное с полезным, наслаждаетесь захватывающим сюжетом, попутно усваивая новые слова и фразы.

Вот, что я умею:
/help - узнать обо мне и о моих способностях
/films - список фильмов для Вашего уровня
/add_to_watched_list - добавить фильм или сериал в список просмотренных
/watched_list - показать Ваш список просмотренных 
/description - напишите команду и название фильма или сериала, а я отправлю Вам его описание
/vocabulary - список полезной лексики по конкретному фильму
/search_phrase - помогает найти примеры употребления слов на английском языке в фильмах
/guess_film - игра "Угадай фильм по фразе"
/my_vocabulary - показать Ваш словарь
'''
                )

keyboard_remove = ReplyKeyboardRemove()


markup1 = ReplyKeyboardMarkup(resize_keyboard=True)
markup1.add(KeyboardButton('A1/A2'))
markup1.add(KeyboardButton('B1'))
markup1.add(KeyboardButton('B2'))
markup1.add(KeyboardButton('C1'))
@bot.message_handler(commands=['start'])
def bot_start(message):
    user_id = message.from_user.id
    username = message.from_user.first_name or "Пользователь"

    data.create_table()

    print(get_user_data(user_id))

    if get_user_data(user_id) is None:
    # Отправляем приветственное сообщение с предложением выбрать уровень
        welcome_message = (
            f"Привет, {username}!\n"
            "Давайте вместе прокачивать английский, наслаждаясь просмотром любимых фильмов, сериалов и даже мультфильмов в оригинале на английском языке.\n\n"
            "Для начала выберите свой уровень английского:\n"
            "- A1 (Beginner)/ A2 (Elementary)\n"
            "- B1 (Intermediate)\n"
            "- B2 (Upper-Intermediate)\n"
            "- C1 (Advanced)\n"
            "Просто напишите нужный уровень (например, B1)"
        )
        bot.send_message(message.chat.id, text=welcome_message, reply_markup=markup1)

        try:
            with open(r'levels.jpg', 'rb') as photo:
                bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo,
                    parse_mode='HTML'
                )
        except Exception as e:
            logging.info(f"Ошибка при отправлении фото: {e}")

    else:
        # Пользователь уже есть в системе
        welcome_message = (
            f"Привет, {username}!\n"
            "Вы уже в системе! Можете продолжать прокачивать английский с помощью фильмов и сериалов.\n\n"
            "Жмите /help, чтобы узнать больше обо мне и о моих способностях"
        )

        bot.send_message(message.chat.id, text=welcome_message)



genres = ["Мультсериал", "Мультфильм", "Комедия", "Детектив", "Драма", "Мелодрама", "Ужасы", "Фантастика", "Боевик"]


@bot.message_handler(func=lambda message: message.text.upper() in ['A1/A2', 'B1', 'B2', 'C1', 'C2'])
def set_level(message):
    chat_id = message.chat.id
    """Обработчик ввода уровня английского."""
    user_id = message.from_user.id
    level = message.text.strip().upper()

    if get_user_data(user_id) is None:
        insert_data(user_id,"level", level)
        bot.send_message(
            message.chat.id,
            text=f"✅ Ваш уровень установлен: {level}. Теперь я смогу подбирать контент под Ваш уровень!\n\n"
                 "Жмите /help, чтобы узнать больше обо мне и о моих способностях", reply_markup=keyboard_remove
        )
        select_data(user_id, "level")

    else:
        update_data(user_id, "level", level)
        bot.send_message(
            message.chat.id,
            text=f"✅ Ваш уровень изменён: {level}. Теперь я смогу подбирать контент под Ваш уровень!", reply_markup=keyboard_remove
        )

    # Сразу после установки уровня показываем выбор жанров
    show_genre_selection_menu(chat_id, genres)


def show_genre_selection_menu(chat_id, genres):
    # Получаем текущий выбор пользователя из БД
    saved_selection = select_data(chat_id, "genres")
    if saved_selection:
        try:
            selected_genres = set(saved_selection.split(','))
        except (ValueError, AttributeError):
            selected_genres = set()
    else:
        selected_genres = set()

    keyboard = types.InlineKeyboardMarkup()

    for genre in genres:
        status = "✅" if genre in selected_genres else "☐"
        # Используем сам жанр в callback_data — он же будет идентификатором
        button = types.InlineKeyboardButton(
            text=f"{status} {genre}",
            callback_data=f"genre:{genre}"
        )
        keyboard.add(button)

    # Кнопка подтверждения выбора
    confirm_button = types.InlineKeyboardButton("✅ Готово", callback_data="confirm_genres")
    keyboard.add(confirm_button)

    bot.send_message(chat_id, "Выберите жанры фильмов, которые Вы предпочитаете:", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith('genre:'))
def handle_genre_selection(call):
    chat_id = call.message.chat.id
    selected_genre = call.data.split(':', 1)[1]  # извлекаем жанр

    # Получаем текущий выбор из БД
    saved_selection = select_data(chat_id, "genres")
    if saved_selection:
        try:
            selected_genres = set(saved_selection.split(','))
        except (ValueError, AttributeError):
            selected_genres = set()
    else:
        selected_genres = set()

    # Добавляем/удаляем жанр из выбора
    if selected_genre in selected_genres:
        selected_genres.discard(selected_genre)
    else:
        selected_genres.add(selected_genre)

    # Сохраняем в БД как строку "Драма,Комедия,Ужасы"
    if selected_genres:
        save_value = ','.join(sorted(selected_genres))
    else:
        save_value = None  # или пустая строка — зависит от логики


    update_data(
        user_id=chat_id,
        column="genres",
        value=save_value
    )

    # Обновляем клавиатуру
    genres = ["Мультсериал", "Мультфильм", "Комедия", "Детектив", "Драма", "Мелодрама", "Ужасы", "Фантастика", "Боевик"]
    show_genre_selection_menu(chat_id, genres)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == 'confirm_genres')
def handle_genre_confirmation(call):
    chat_id = call.message.chat.id

    # Получаем финальный выбор из БД
    saved_selection = select_data(chat_id, "genres")
    if not saved_selection:
        bot.answer_callback_query(call.id, "Ничего не выбрано!", show_alert=True)
        return

    try:
        selected_genres = saved_selection.split(',')
    except (ValueError, AttributeError):
        bot.answer_callback_query(call.id, "Ошибка данных!", show_alert=True)
        return

    if selected_genres:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Вы выбрали жанры: {', '.join(selected_genres)}"
        )
    else:
        bot.answer_callback_query(call.id, "Ничего не выбрано!", show_alert=True)



@bot.message_handler(commands=['help'])
def bot_help(message):
    bot.send_message(message.chat.id,

                     text=help_message)



@bot.message_handler(commands=['films'])
def show_films(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Проверяем регистрацию пользователя
    if get_user_data(user_id) is None:
        bot.send_message(chat_id, "Сначала зарегистрируйтесь — отправьте /start")
        return

    # Получаем уровень пользователя из его профиля
    user_level = select_data(user_id, "level")
    if not user_level:
        bot.send_message(
            chat_id,
            "Сначала укажите свой уровень английского (например, напишите B1)."
        )
        return

    # Фильтруем фильмы по уровню и жанрам пользователя
    matching_films = []
    for film in data.films:
        # Проверяем, содержит ли уровень фильма текущий уровень пользователя
        if user_level not in film['level']:
            continue

        # Получаем предпочитаемые жанры пользователя из БД и преобразуем в список
        user_genres_str = select_data(user_id, "genres")
        if not user_genres_str or user_genres_str.strip() == '':
            # Если жанры не выбраны или строка пустая, добавляем фильм
            matching_films.append(film)
            continue

        user_genres = [genre.strip().lower() for genre in user_genres_str.split(',')]

        # Проверяем пересечение жанров фильма с предпочитаемыми жанрами пользователя
        film_genres = film.get('genre', [])  # предполагаем, что жанр может быть списком или строкой

        # Обрабатываем случай, когда жанр — строка с несколькими жанрами через запятую
        if isinstance(film_genres, str):
            # Разделяем строку на отдельные жанры и приводим к нижнему регистру
            film_genres = [g.strip().lower() for g in film_genres.split(',')]
        elif isinstance(film_genres, list):
            # Если это список, приводим все элементы к нижнему регистру и убираем пробелы
            film_genres = [g.strip().lower() for g in film_genres]
        else:
            # На всякий случай — пустой список, если формат неожиданный
            film_genres = []

        # Проверяем пересечение жанров
        if any(genre in user_genres for genre in film_genres):
            matching_films.append(film)

    # Если подходящих фильмов нет
    if not matching_films:
        matching_films = []
        for film in data.films:
            # Проверяем, содержит ли уровень фильма текущий уровень пользователя
            if user_level in film['level']:
                matching_films.append(film)

    # Формируем общее сообщение
    response = f"<b>🎬 Фильмы для уровня {user_level}</b>\n\n"

    # Создаём общую клавиатуру
    keyboard = types.InlineKeyboardMarkup()

    for idx, film in enumerate(matching_films, start=1):
        # Добавляем информацию о фильме в текст
        response += (
            f"<b>{idx}. Название:</b> {film['title']}\n"
            f"<b>Жанр:</b> {film['genre']}\n"
            f"<b>Рейтинг IMDb:</b> {film['imdb_rating']}\n"
        )

        title =film['title'].split(' ')[0].strip()
        # Создаём кнопку для этого фильма
        button = types.InlineKeyboardButton(
            text=f"📋 Описание фильма {idx}",
            callback_data=f"film_desc:{title}"
        )
        keyboard.add(button)  # каждая кнопка на отдельной строке
        response += "\n"  # разделитель между фильмами

    # Отправляем одно сообщение с общей клавиатурой
    bot.send_message(
        chat_id,
        response,
        reply_markup=keyboard,
        parse_mode='HTML'
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('film_desc:'))
def show_film_description(call):
    film = call.data.split(':', 1)[1]

    response = get_film_description(film)

    keyboard = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton("◀️ Назад к списку фильмов", callback_data="back_to_films")
    keyboard.add(back_button)

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=response,
        parse_mode='HTML',
        reply_markup=keyboard
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == 'back_to_films')
def back_to_films_list(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    # Получаем уровень пользователя из его профиля
    user_level = select_data(user_id, "level")
    if not user_level:
        bot.send_message(
            chat_id,
            "Сначала укажите свой уровень английского (например, напишите B1)."
        )
        return

    # Фильтруем фильмы по уровню и жанрам пользователя
    matching_films = []
    for film in data.films:
        # Проверяем, содержит ли уровень фильма текущий уровень пользователя
        if user_level not in film['level']:
            continue

        # Получаем предпочитаемые жанры пользователя из БД и преобразуем в список
        user_genres_str = select_data(user_id, "genres")
        if not user_genres_str or user_genres_str.strip() == '':
            # Если жанры не выбраны или строка пустая, добавляем фильм
            matching_films.append(film)
            continue

        user_genres = [genre.strip().lower() for genre in user_genres_str.split(',')]

        # Проверяем пересечение жанров фильма с предпочитаемыми жанрами пользователя
        film_genres = film.get('genre', [])  # предполагаем, что жанр может быть списком или строкой

        # Обрабатываем случай, когда жанр — строка с несколькими жанрами через запятую
        if isinstance(film_genres, str):
            # Разделяем строку на отдельные жанры и приводим к нижнему регистру
            film_genres = [g.strip().lower() for g in film_genres.split(',')]
        elif isinstance(film_genres, list):
            # Если это список, приводим все элементы к нижнему регистру и убираем пробелы
            film_genres = [g.strip().lower() for g in film_genres]
        else:
            # На всякий случай — пустой список, если формат неожиданный
            film_genres = []

        # Проверяем пересечение жанров
        if any(genre in user_genres for genre in film_genres):
            matching_films.append(film)

    # Если подходящих фильмов нет
    if not matching_films:
        matching_films = []
        for film in data.films:
            # Проверяем, содержит ли уровень фильма текущий уровень пользователя
            if user_level in film['level']:
                matching_films.append(film)

    # Формируем общее сообщение
    response = f"<b>🎬 Фильмы для уровня {user_level}</b>\n\n"

    # Создаём общую клавиатуру
    keyboard = types.InlineKeyboardMarkup()

    for idx, film in enumerate(matching_films, start=1):
        # Добавляем информацию о фильме в текст
        response += (
            f"<b>{idx}. Название:</b> {film['title']}\n"
            f"<b>Жанр:</b> {film['genre']}\n"
            f"<b>Рейтинг IMDb:</b> {film['imdb_rating']}\n"
        )

        title = film['title'].split(' ')[0].strip()
        # Создаём кнопку для этого фильма
        button = types.InlineKeyboardButton(
            text=f"📋 Описание фильма {idx}",
            callback_data=f"film_desc:{title}"
        )
        keyboard.add(button)  # каждая кнопка на отдельной строке
        response += "\n"  # разделитель между фильмами

    # Обновляем сообщение — показываем список фильмов вместо описания
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=response,
        reply_markup=keyboard,
        parse_mode='HTML'
    )



film_dict = {}
for film in data.films:
    short_title = film["title"].split(',')[0].strip().lower()
    film_dict[short_title] = film

def get_film_description(film_title: str) -> str:
    """
    Ищет фильм по названию (до запятой) и возвращает его описание.
    Если фильм не найден, возвращает сообщение об ошибке.
    """
    for film in data.films:
        # Извлекаем короткое название (до запятой)
        short_title = film["title"].split(',')[0].strip().lower()

        # Сравниваем с искомым названием (приводим к нижнему регистру для сравнения)
        if film_title.lower().strip() in short_title:
            return film["description"]

    return "Фильм не найден в базе данных."




def get_user_watched_list(user_id: int) -> list:
    try:
        result = select_data(user_id, "watched_list")

        return [film.strip() for film in result.split(',') if film.strip()]

    except Exception as e:
        logging.error(f"Ошибка при получении watched_list для user_id={user_id}: {e}")
        return []


def update_watched_list(user_id: int, new_film):
    existing_list = get_user_watched_list(user_id)
    print(existing_list)
    existing_list.append(new_film)
    print(existing_list)

    # Преобразуем в строку через запятую
    list_str = ', '.join(existing_list)

    try:
        update_data(user_id, "watched_list", list_str)
        print(existing_list)
    except Exception as e:
        logging.error(f"Ошибка при обновлении watched_list для user_id={user_id}: {e}")

markup4 = ReplyKeyboardMarkup(resize_keyboard=True)
markup4.add(KeyboardButton('/watched_list'))
@bot.message_handler(commands=['add_to_watched_list'])
def add_to_watched_list(message):
    user_id = message.from_user.id

    if get_user_data(user_id) is None:
        bot.send_message(chat_id, "Сначала зарегистрируйтесь — отправьте /start")
        return

    user_level = select_data(user_id, "level")
    if not user_level:
        bot.send_message(
            chat_id,
            "Сначала укажите свой уровень английского (например, напишите B1)."
        )
        return

    matching_films = []
    for film in data.films:
        # Проверяем, содержит ли уровень фильма текущий уровень пользователя
        if user_level in film['level']:
            matching_films.append(film)

    buttons = []
    for film in matching_films:
        short_title = film["title"].split(',')[0].strip()
        buttons.append(KeyboardButton(text=short_title))

    markup3 =  ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for button in buttons:
        markup3.add(button)

    msg = bot.reply_to(message, "Напишите название фильма, мультфильма или сериала из списка, который вы уже посмотрели, или просто выберите его на клавиатуре", reply_markup=markup3)
    bot.register_next_step_handler(msg, add_to_watched_list2)


def add_to_watched_list2(message):
    user_id = message.from_user.id
    film_title = message.text

    found = next((item for item in data.films if item["title"].split(',')[0] == film_title), None)
    if not found:
        bot.send_message(user_id, "Упс, кажется, этого фильма нет в моем списке. Пожалуйста, напишите название фильма из списка")
        return

    list = select_data(user_id, "watched_list")
    if list:
        if film_title in list:
            bot.send_message(
                message.chat.id,
                f"✅ Фильм «{film_title}» уже в Вашем списке просмотренных!", reply_markup=markup4
            )
            return

    # Добавляем фильм в список
    update_watched_list(user_id, film_title)

    bot.send_message(
        message.chat.id,
        f"✅ Фильм «{film_title}» добавлен в ваш список просмотренных!", reply_markup=markup4
    )


@bot.message_handler(commands=["watched_list"])
def watched_list(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if get_user_data(user_id) is None:
        bot.send_message(chat_id, "Сначала зарегистрируйтесь — отправьте /start")
        return

    watched_list = get_user_watched_list(user_id)

    if watched_list:
        numbered_list = "\n\n".join(
        f"<b>{i}.</b> {film}" for i, film in enumerate(watched_list, 1)
        )
        message_text = f"🎬 Ваш список просмотренных фильмов:\n\n{numbered_list}"
    else:
        message_text = "Вы пока не добавили ни одного фильма."

    bot.send_message(user_id, message_text, parse_mode='HTML')



@bot.message_handler(commands=["search_phrase"])
def search_phrase(message):
    try:
        response = requests.get("https://api.telegram.org", timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Проблема с соединением: {e}")

    user_id = message.from_user.id
    msg = bot.reply_to(message,"Напишите слово или фразу на английском, а я отправлю Вам их использование в фильмах.", reply_markup=keyboard_remove)
    bot.register_next_step_handler(msg, phrase)


def phrase(message):
    user_id = message.from_user.id
    phrase = message.text

    results = search_in_db(phrase)

    if results:
        # Форматируем ответ: заголовок, время, контекст
        response_lines = []
        response_lines.append(f"🔍 Примеры употребления фразы '{phrase}':\n")

        for i, (title, start_time, text) in enumerate(results, 1):
            # Форматируем время — убираем миллисекунды для красоты (оставляем HH:MM:SS)
            formatted_time = start_time.split(',')[0]  # например, "00:01:23,456" → "00:01:23"

            # Добавляем номер примера, заголовок, время и текст с отступами
            example = (
                f"<b>{i}.</b> 🎥 <i>{title}</i>\n"
                f"⏰ {formatted_time}\n"
                f"💬 {text}\n"
                f"{'-' * 40}"  # разделитель между примерами
            )
            response_lines.append(example)

        response = "\n".join(response_lines)
    else:
        response = f"Фраза '{phrase}' не найдена в субтитрах."

    bot.send_message(user_id, response, parse_mode='HTML')



def get_vocabulary(film_title: str) -> str:
    """
    Ищет фильм по названию (до запятой) и возвращает его описание.
    Если фильм не найден, возвращает сообщение об ошибке.
    """
    for film in data.films:
        # Извлекаем короткое название (до запятой)
        short_title = film["title"].split(',')[0].strip().lower()

        # Сравниваем с искомым названием (приводим к нижнему регистру для сравнения)
        if film_title.lower().strip() in short_title:
            return film["vocabulary"]

    return "Фильм не найден в базе данных."



markup3 = ReplyKeyboardMarkup(resize_keyboard=True)
markup3.add(KeyboardButton('/my_vocabulary'))
@bot.message_handler(commands=["vocabulary"])
def send_vocabulary(message):
    user_level = select_data(message.from_user.id, "level")

    matching_films = []
    for film in data.films:
        # Проверяем, содержит ли уровень фильма текущий уровень пользователя
        if user_level in film['level']:
            matching_films.append(film)

    buttons = []
    for film in matching_films:
        short_title = film["title"].split(',')[0].strip()
        buttons.append(KeyboardButton(text=short_title))

    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for button in buttons:
        markup.add(button)

    msg = bot.send_message(message.chat.id, "Напишите название фильма или сериала из списка или просто выберите его на клавиатуре, и я отправлю Вам список слов, которые могут быть полезны для Вас.", reply_markup=markup)
    bot.register_next_step_handler(msg, process_next_step)


user_selections = {}
def process_next_step(message):
    user_id = message.from_user.id
    movie_title = message.text
    has_match = any(movie_title.lower() in film.lower() for film in film_dict.keys())

    if has_match:
        vocabulary = get_vocabulary(movie_title)

        # Разделяем строку на отдельные строки по символу переноса строки
        words_list = vocabulary.strip().split('\n')

        user_selections[user_id] = {
            'words_list': words_list,
            'movie_title': movie_title
        }

        result_lines = []
        result_lines.append(f"📚 Словарный запас фильма '{movie_title}':")
        result_lines.append("")
        for i, word in enumerate(words_list, start=1):
            result_lines.append(f"   {i}. {word}")

        result_lines.append("")
        result_lines.append("Напишите через запятую номера слов, если хотите добавить их в личный словарь:")
        response = "\n".join(result_lines)


        msg = bot.send_message(
            message.chat.id,
            response,
            parse_mode='HTML'
        )

        bot.register_next_step_handler(msg, handle_word_selection)
    else:
        bot.send_message(
            message.chat.id,
            "Фильм не найден. Попробуйте ещё раз.")


def handle_word_selection(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Получаем выбор пользователя
    selection_text = message.text.strip()

    try:
        # Парсим номера: разделяем по запятым, убираем пробелы, преобразуем в числа
        selected_indices = [int(num.strip()) - 1 for num in selection_text.split(',')]
    except ValueError:
        bot.reply_to(message, "Пожалуйста, введите корректные номера через запятую, например: 1,3,5")
        return

    # Получаем данные пользователя
    user_data = user_selections[user_id]
    words_list = user_data['words_list']
    movie_title = user_data['movie_title']

    # Проверяем корректность номеров
    valid_indices = []
    invalid_indices = []

    for idx in selected_indices:
        if 0 <= idx < len(words_list):
            valid_indices.append(idx)
        else:
            invalid_indices.append(idx + 1)  # +1 для отображения пользователю

    # Сообщаем о некорректных номерах, если есть
    if invalid_indices:
        invalid_str = ', '.join(map(str, invalid_indices))
        bot.reply_to(message, f"Номера {invalid_str} некорректны. Пожалуйста, выберите номера из списка.")
        return

    # Обрабатываем выбранные слова
    added_count = 0
    for idx in valid_indices:
        word_pair = words_list[idx]

        # Разделяем слово и перевод (предполагаем формат "слово — перевод")
        if ' — ' in word_pair:
            word, translation = word_pair.split(' — ', 1)
        else:
            # Если формат не соответствует, берём всю строку как слово, перевод пустой
            word = word_pair
            translation = ''

        # Сохраняем в БД
        save_to_vocabulary_db(user_id, word, translation, movie_title)
        added_count += 1

        # Удаляем временные данные
        del user_selections[user_id]

        # Отправляем подтверждение
        bot.reply_to(message, f"✅ Успешно добавлено {added_count} слов в ваш личный словарь!", reply_markup=markup3)

    else:
        return

@bot.message_handler(commands=['my_vocabulary'])
def show_personal_vocabulary(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Получаем слова пользователя из БД
    words = get_personal_vocabulary(user_id)

    if not words:
        bot.send_message(
            chat_id,
            "📖 Ваш личный словарь пуст."
        )
        return

    # Форматируем вывод
    formatted_list = format_personal_vocabulary(words)

    bot.send_message(chat_id, formatted_list, parse_mode='HTML')


def format_personal_vocabulary(words):
    """Форматирует словарь в красивый список с группировкой по фильмам"""
    from collections import defaultdict

    # Группируем слова по фильмам
    films_dict = defaultdict(list)
    for word, translation, title in words:
        films_dict[title].append((word, translation))

    result_lines = []
    result_lines.append("📖 <b>Ваш личный словарь</b>\n")

    total_words = 0

    for title, word_pairs in films_dict.items():
        result_lines.append(f"🎬 <b>{title}</b> ({len(word_pairs)} слов)")

        for i, (word, translation) in enumerate(word_pairs, start=1):
            result_lines.append(f"   {i}. <i>{word}</i> — {translation}")

        total_words += len(word_pairs)
        result_lines.append("")  # пустая строка между фильмами

    # Убираем последнюю пустую строку
    if result_lines and result_lines[-1] == "":
        result_lines.pop()

    # Добавляем итоговую статистику
    result_lines.append(f"\n📊 <b>Всего слов:</b> {total_words}")

    return "\n".join(result_lines)



def translate_word(word, source_lang='en', dest_lang='ru'):
    try:
        translator = GoogleTranslator(source=source_lang, target=dest_lang)
        translation = translator.translate(word)
        return translation
    except Exception as e:
        print(f"Ошибка перевода: {e}")
        return None

@bot.message_handler(commands=['translation'])
def get_word(message):
    chat_id = message.chat.id

    msg = bot.send_message(
        chat_id,
        "📝 Введите слово или фразу на английском языке, а я отправлю Вам перевод на русский:"
    )

    bot.register_next_step_handler(msg, send_translation)

def send_translation(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    word = message.text.strip()

    if not word:
        bot.reply_to(message, "Пожалуйста, введите корректное слово.")
        return

    translation = translate_word(word)

    if translation:
        keyboard4 = types.InlineKeyboardMarkup()
        add_button = types.InlineKeyboardButton(
            text="Добавить в мой словарь",
            callback_data=f"add_to_vocab:{word}"
        )
        keyboard4.add(add_button)

        bot.send_message(chat_id, translation, reply_markup=keyboard4, parse_mode='HTML')
        bot.send_message(chat_id, "Перевести ещё слово - /translation", reply_markup=markup3)

    else:
        bot.send_message(chat_id, "Кажется, произошла какая-то ошибка. Нажмите на /translation снова и попробуйте ввести слово/фразу правильно.", parse_mode='HTML')


@bot.callback_query_handler(func=lambda call: call.data.startswith('add_to_vocab:'))
def handle_add_to_vocabulary(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    word = call.data.split(':', 1)[1]
    translation = translate_word(word)

    words = get_personal_vocabulary(user_id)

    for word1, translation1, title in words:
        if word1.lower().strip() == word.lower():
            bot.answer_callback_query(
                call.id,
                "🚫 Это слово уже есть в вашем словаре!",
                show_alert=True
            )
            return


    save_to_vocabulary_db(user_id, word, translation, "-")

    bot.answer_callback_query(
        call.id,
        "✅ Слово успешно добавлено в ваш словарь!",
        show_alert=True
    )



user_games = {}
def start_new_round(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    """Запускает новый раунд игры"""
    quote_text, correct_title, options = get_random_quote()

    MAX_LENGTH = 100
    if len(quote_text) > MAX_LENGTH:
        quote_text = textwrap.shorten(quote_text, width=MAX_LENGTH, placeholder="…")

    if not quote_text:
        bot.send_message(chat_id, "Не удалось загрузить цитату. Попробуйте ещё раз.")
        return False

    # Создаём клавиатуру с вариантами
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for option in options:
        keyboard.add(KeyboardButton(option))

    # Сохраняем данные игры
    if user_id not in user_games:
        user_games[user_id] = {'score': 0, 'round': 0}

    # Отменяем предыдущий таймер, если он есть
    cancel_previous_timer(user_id)

    user_games[user_id]['correct_answer'] = correct_title
    user_games[user_id]['round'] += 1
    user_games[user_id]['start_time'] = datetime.now()
    user_games[user_id]['quote_text'] = quote_text
    # Сохраняем таймер в данных пользователя
    timer = threading.Timer(30, time_up, args=[user_id, chat_id])
    user_games[user_id]['timer'] = timer
    timer.start()

    # Отправляем цитату и клавиатуру
    bot.send_message(
        chat_id,
        f"🎬 Раунд {user_games[user_id]['round']}/5\n"
        f"Очки: {user_games[user_id]['score']}\n\n"
        f"Угадайте фильм по цитате:\n\n<i>{quote_text}</i>\n\n"
        f"Выберите правильный вариант (у вас 30 секунд):",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    return True

def cancel_previous_timer(user_id):
    """Отменяет предыдущий таймер, если он существует"""
    if user_id in user_games and 'timer' in user_games[user_id]:
        user_games[user_id]['timer'].cancel()
        # Удаляем таймер из данных
        del user_games[user_id]['timer']

def time_up(user_id, chat_id):
    """Вызывается, когда время на ответ истекло"""
    # Проверяем, существует ли пользователь в данных и есть ли активный таймер
    if user_id in user_games and user_games[user_id].get('correct_answer'):
        correct_answer = user_games[user_id]['correct_answer']
        bot.send_message(
            chat_id,
            f"⏰ Время вышло! Правильный ответ: '{correct_answer}'\n\n"
            f"Начните новую игру командой /guess_film",
            reply_markup=types.ReplyKeyboardRemove()
        )
        # Сбрасываем игру
        if user_id in user_games:
            del user_games[user_id]


@bot.message_handler(commands=["guess_film"])
def guess_film(message):
    # Начинаем новую игру (5 раундов)
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Инициализируем данные игры
    user_games[user_id] = {'score': 0, 'round': 0}

    start_new_round(message)


@bot.message_handler(func=lambda message: True)
def handle_guess_answer(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Проверяем, есть ли активная игра
    if user_id not in user_games:
        return

    game_data = user_games[user_id]
    correct_answer = game_data.get('correct_answer')

    if not correct_answer:
        # Раунд уже завершён (например, по таймауту)
        return

    # Проверяем время ответа
    time_elapsed = datetime.now() - game_data['start_time']
    if time_elapsed > timedelta(seconds=30):
        bot.send_message(
            chat_id,
            f"⏰ Время на ответ истекло! Правильный ответ: '{correct_answer}'\n\n"
            "Начните новую игру командой /guess_film",
            reply_markup=types.ReplyKeyboardRemove()
        )
        if user_id in user_games:
            del user_games[user_id]
        return

    user_answer = message.text

    # Проверяем ответ
    if user_answer == correct_answer:
        game_data['score'] += 1
        response = f"🎉 Верно! Это действительно '{correct_answer}'! +1 очко"
    else:
        response = f"❌ Неверно. Правильный ответ: '{correct_answer}'"

    # Убираем клавиатуру
    keyboard_remove = ReplyKeyboardRemove()

    # Завершаем раунд или начинаем следующий
    if game_data['round'] >= 5:
        bot.send_message(chat_id, response, reply_markup=keyboard_remove)

        # Игра завершена — показываем результат
        final_score = game_data['score']
        result_message = (
            f"🏆 Игра завершена!\n\n"
            f"Ваш результат: {final_score}/5 правильных ответов\n\n"
            f"Отличная работа! Хотите сыграть ещё раз?\n"
            f"Нажмите /guess_film для новой игры"
        )
        bot.send_message(chat_id, result_message)
        # Удаляем данные игры
        if user_id in user_games:
            del user_games[user_id]
    else:
        # Отправляем результат текущего раунда
        bot.send_message(chat_id, response, reply_markup=keyboard_remove)

        # Начинаем следующий раунд через 2 секунды
        def next_round():
            start_new_round(message)

        threading.Timer(2, next_round).start()


@bot.message_handler(commands=['getusersfile'])
def get_users_as_file(message):
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Получаем данные с колонками
        cur.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cur.fetchall()]

        cur.execute("SELECT * FROM users")
        rows = cur.fetchall()

        if not rows:
            bot.send_message(message.chat.id, "Таблица 'users' пуста.")
            conn.close()
            return

        # Создаём текстовый файл
        filename = "users_data.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("=== Таблица 'users' ===\n\n")
            f.write(" | ".join(columns) + "\n")
            f.write("-" * len(" | ".join(columns)) + "\n")

            for row in rows:
                f.write(" | ".join(str(cell) for cell in row) + "\n")

        # Отправляем файл
        with open(filename, "rb") as file:
            bot.send_document(message.chat.id, file, caption="Данные таблицы 'users'")

        conn.close()
        os.remove(filename)  # удаляем временный файл

    except sqlite3.Error as e:
        bot.send_message(message.chat.id, f"Ошибка БД: {e}")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")





bot.polling()



from flask import Flask
import threading

app = Flask(__name__)

@app.route('/health')
def health_check():
    return 'Bot is alive!'

# Запускаем сервер в отдельном потоке
def run_flask():
    app.run(host='0.0.0.0', port=10000)

flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()
