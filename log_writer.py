"""
log_writer.py — Запись поисковых запросов в MongoDB.

Этот модуль отвечает за ЛОГИРОВАНИЕ поисковых запросов пользователя.
Каждый запрос (ключевое слово или жанр+год) сохраняется как документ
в коллекции MongoDB. Формат документа:

    {
      "timestamp":   "2025-01-15T14:30:00",   # ISO 8601 строка
      "search_type": "keyword",                # тип запроса
      "params":      {"keyword": "cat"}        # параметры запроса
    }

Паттерн Lazy Singleton:
  Подключение к MongoDB (_client) создаётся ОДИН раз при первом обращении.
  Это экономит ресурсы — не создаём соединение, пока оно не нужно.
  Переменная _client хранится на уровне модуля (глобально).
"""

import os  # Для доступа к переменным окружения
from datetime import datetime  # Для получения текущего времени

from dotenv import load_dotenv  # Загрузка .env файла
from pymongo import MongoClient  # Клиент MongoDB
from pymongo.collection import Collection  # Тип коллекции (для аннотаций)

# Загружаем переменные окружения из .env
load_dotenv()

# Глобальная переменная для Lazy Singleton паттерна.
# None означает, что подключение ещё не создано.
# После первого вызова get_collection() здесь будет объект MongoClient.
_client: MongoClient | None = None


def get_collection() -> Collection:
    """
    Возвращает коллекцию MongoDB, создавая подключение при первом вызове.

    Паттерн Lazy Singleton:
      1. Проверяем: _client is None? → подключение ещё не создано.
      2. Если None — создаём MongoClient (одно TCP-соединение на всё приложение).
      3. global _client — указываем Python, что меняем глобальную переменную,
         а не создаём локальную с таким же именем.

    MONGO_URI из .env содержит строку подключения, например:
      mongodb://user:password@mongo.server.de:27017

    Returns:
        Collection — объект коллекции pymongo для вставки/чтения документов
    """
    global _client  # Без global присвоение создаст ЛОКАЛЬНУЮ переменную _client
    if _client is None:
        # MongoClient — пул соединений. Создаётся один раз, используется многократно.
        _client = MongoClient(os.getenv('MONGO_URI'))
    # Получаем базу данных по имени из переменной окружения
    db = _client[os.getenv('MONGO_DB', '')]
    # Получаем коллекцию (аналог таблицы в SQL) по имени
    return db[os.getenv('MONGO_COLLECTION', '')]


def log_search(search_type: str, params: dict) -> None:
    """
    Записывает один поисковый запрос в MongoDB.

    Вызывается из main.py → _paginate() при первой странице результатов.

    insert_one() — вставляет один документ (словарь) в коллекцию.
    MongoDB автоматически добавит поле _id (ObjectId).

    isoformat(timespec='seconds') — формат ISO 8601 без микросекунд:
      '2025-01-15T14:30:00' вместо '2025-01-15T14:30:00.123456'

    try/except Exception: pass — если MongoDB недоступна, ошибка МОЛЧА
    игнорируется. Приложение продолжает работать — поиск важнее логов.

    Args:
        search_type: тип поиска ('keyword' или 'genre_year')
        params: параметры запроса, например {'keyword': 'cat'}
                или {'genre': 'Comedy', 'year_from': 2000, 'year_to': 2010}
    """
    try:
        get_collection().insert_one({
            # datetime.now() — текущее время, .isoformat() — строка ISO 8601
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            'search_type': search_type,  # 'keyword' или 'genre_year'
            'params': params,            # Словарь с параметрами поиска
        })
    except Exception:
        # Молча игнорируем ошибку — логирование не должно ломать поиск
        pass
