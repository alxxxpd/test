import sqlite3
import logging


def create_table_vocabulary():
    with sqlite3.connect('db.sqlite') as con:
        cur = con.cursor()

        query = '''CREATE TABLE IF NOT EXISTS vocabulary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    word TEXT,
    translation TEXT,
    title TEXT
);'''
        cur.execute(query)
        con.commit()

    logging.info("Создана таблица vocabulary")



def save_to_vocabulary_db(user_id, word, translation, title):
    with sqlite3.connect('db.sqlite') as con:
        cur = con.cursor()

        # Проверяем, существует ли уже такое слово для этого пользователя и фильма
        cur.execute('''
            SELECT id FROM vocabulary
            WHERE user_id = ? AND word = ? AND title = ?
        ''', (user_id, word, title))

        existing_word = cur.fetchone()

        if existing_word:
            return True
        else:
            # Слова нет — добавляем
            cur.execute('''
                INSERT INTO vocabulary (user_id, word, translation, title)
                VALUES (?, ?, ?, ?)
            ''', (user_id, word, translation, title))
            con.commit()
            return True



def get_personal_vocabulary(user_id):
    with sqlite3.connect('db.sqlite') as con:
        cur = con.cursor()

        cur.execute('''
            SELECT word, translation, title
            FROM vocabulary
            WHERE user_id = ?
            ORDER BY title, word
        ''', (user_id,))

        words = cur.fetchall()
        return words





if __name__ == '__main__':
    create_table_vocabulary()