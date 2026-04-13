import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

db_path = r'C:\Users\1\PycharmProjects\PythonProject\.venv\db.sqlite'