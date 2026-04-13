import sqlite3
import logging
import re
import chardet
import random



def search_in_db(phrase: str) -> list:
    with sqlite3.connect('db.sqlite') as con:
        cur = con.cursor()

        query = '''
            SELECT title, start_time, text
            FROM lines1
            WHERE text LIKE ?
            ORDER BY RANDOM()
            LIMIT 10
            '''

        search_pattern = f"%{phrase}%"
        cur.execute(query, (search_pattern,))
        results = cur.fetchall()
        return results



def create_table():
    with sqlite3.connect('db.sqlite') as con:
        cur = con.cursor()

        query = '''CREATE TABLE IF NOT EXISTS lines1 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    sequence_number INTEGER,
    start_time TEXT,
    end_time TEXT,
    text TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);'''
        cur.execute(query)
        con.commit()

    logging.info("Создана таблица lines1")



def get_random_quote(db_path: str = 'subtitles.db') -> tuple:
    with sqlite3.connect('db.sqlite') as con:
        cur = con.cursor()

        # Получаем случайный фильм и номер строки для начала контекста
        cur.execute('''
                SELECT title, sequence_number
                FROM lines1
                ORDER BY RANDOM()
                LIMIT 1
            ''')

        result = cur.fetchone()

        if not result:
            con.close()
            return None, None, []

        correct_title, start_line = result

        # Определяем диапазон строк для получения
        end_line = start_line + 1

        # Получаем последовательные строки из выбранного фильма
        cur.execute('''
                SELECT text
                FROM lines1
                WHERE title = ? AND sequence_number BETWEEN ? AND ?
                ORDER BY sequence_number
            ''', (correct_title, start_line, end_line))

        quote_lines = [row[0] for row in cur.fetchall()]

        # Если не удалось получить нужное количество строк (например, в конце фильма), берём сколько есть
        if len(quote_lines) < 3 and len(quote_lines) > 0:
            pass  # Используем то, что есть
        elif len(quote_lines) == 0:
            con.close()
            return None, None, []

        # Объединяем строки в одну цитату с переносами
        quote_text = '\n'.join(quote_lines)

        # Получаем 3 других случайных фильма (исключая правильный)
        cur.execute('''
            SELECT DISTINCT title
            FROM lines1
            WHERE title != ?
            ORDER BY RANDOM()
            LIMIT 3
        ''', (correct_title,))
        other_titles = [row[0] for row in cur.fetchall()]

        # Формируем список вариантов (перемешиваем с правильным)
        options = other_titles + [correct_title]
        random.shuffle(options)

        return quote_text, correct_title, options



def parse_srt(file_path, title):
    # Автоматически определяем кодировку файла
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        encoding = result['encoding'] or 'utf-8'  # запасная кодировка

    print(f"Определена кодировка: {encoding}")

    with open(file_path, 'r', encoding=encoding) as file:
        content = file.read()

    # Регулярное выражение для разбиения на блоки субтитров
    pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n([\s\S]*?)(?=\n*\d+\n|\Z)'
    matches = re.findall(pattern, content)

    parsed_subtitles = []
    for match in matches:
        sequence = int(match[0])
        start = match[1]
        end = match[2]
        text = match[3].strip().replace('\n', ' ')  # Объединяем строки текста в одну
        parsed_subtitles.append((title, sequence, start, end, text))
    return parsed_subtitles

def insert_to_db(subtitles, db_path='db.sqlite'):
    with sqlite3.connect(db_path) as con:
        cur = con.cursor()

        insert_query = '''
        INSERT INTO lines1 (title, sequence_number, start_time, end_time, text)
        VALUES (?, ?, ?, ?, ?)
        '''

        cur.executemany(insert_query, subtitles)
        con.commit()
    logging.info(f"Успешно добавлено {len(subtitles)} строк субтитров.")



if __name__ == '__main__':
    create_table()
    srt_file = r"C:\Users\1\Desktop\Сашина папка\субтитры\peaky.blinders.s06e01.1080p.bluray.x264-carved.srt"
    subtitles_data = parse_srt(srt_file, "Peaky Blinders (Острые козырьки)")
    insert_to_db(subtitles_data)


