"""
log_stats.py — Статистика поисковых запросов из MongoDB.

Этот модуль ЧИТАЕТ данные из MongoDB (в отличие от log_writer, который ПИШЕТ).
Предоставляет две функции:

  1. get_popular_queries() — топ-N самых частых запросов (через aggregation pipeline)
  2. get_recent_queries()  — последние N запросов (через find + sort + limit)

Импортирует get_collection() из log_writer.py, чтобы использовать
ту же самую коллекцию MongoDB (тот же Lazy Singleton подключение).
"""

from log_writer import get_collection  # Переиспользуем подключение из log_writer


def get_popular_queries(top_n: int = 5) -> list[dict]:
    """
    Возвращает топ-N самых частых поисковых запросов.

    Использует MongoDB Aggregation Pipeline — цепочку стадий обработки данных.
    Каждая стадия получает документы от предыдущей и передаёт результат дальше.

    Стадии pipeline:
      1. $group — группировка документов по уникальной комбинации (search_type + params).
         _id задаёт ключ группировки (как GROUP BY в SQL).
         count: {$sum: 1} — считает количество документов в каждой группе.

      2. $sort {count: -1} — сортируем группы по убыванию популярности.
         -1 означает DESC (от большего к меньшему).

      3. $limit top_n — берём только первые N самых популярных.

    Args:
        top_n: количество результатов (по умолчанию 5)

    Returns:
        Список словарей: [{'search_type': 'keyword', 'params': {...}, 'count': 42}, ...]
        Пустой список [] при ошибке подключения к MongoDB.
    """
    try:
        # Получаем объект коллекции pymongo — через него отправляем запросы к MongoDB.
        # get_collection() возвращает pymongo.collection.Collection.
        collection = get_collection()

        # Pipeline — список стадий (словарей). MongoDB выполняет их последовательно.
        pipeline: list[dict] = [
            # Стадия 1: Группировка по (search_type, params) — подсчёт количества
            {"$group": {
                "_id": {"search_type": "$search_type", "params": "$params"},
                "count": {"$sum": 1},  # $sum: 1 — прибавляет 1 за каждый документ
            }},
            # Стадия 2: Сортировка по count (самые популярные — первые)
            {"$sort": {"count": -1}},
            # Стадия 3: Ограничение количества результатов
            {"$limit": top_n},
        ]

        # collection.aggregate(pipeline) возвращает CommandCursor — итератор.
        # Это НЕ список, а генератор: документы приходят по одному из MongoDB.
        # Перебираем его в цикле for, чтобы собрать нужные поля в свой формат.
        results: list[dict] = []
        for doc in collection.aggregate(pipeline):
            # doc — один документ-результат из pipeline.
            # doc['_id'] — это словарь {'search_type': '...', 'params': {...}},
            # потому что мы задали _id как {search_type: ..., params: ...} в $group.
            results.append({
                'search_type': doc['_id']['search_type'], #
                'params': doc['_id']['params'], # _id ключ группировки, содержит search_type и params
                'count': doc['count'], # количество запросов в этой группе (из $group stage)
            })
        return results
    except Exception:
        # Если MongoDB недоступна — возвращаем пустой список (приложение не падает)
        return []


def get_recent_queries(last_n: int = 5) -> list[dict]:
    """
    Возвращает последние N поисковых запросов (без дедупликации).

    В отличие от get_popular_queries(), здесь НЕТ aggregation pipeline.
    Используется простая цепочка методов pymongo:

      collection.find()             — получить все документы (аналог SELECT *)
                .sort('timestamp', -1)  — отсортировать по убыванию (-1 = DESC)
                .limit(last_n)          — ограничить количество (аналог LIMIT в SQL)

    Каждый метод возвращает курсор, поэтому вызовы можно объединять цепочкой.

    Args:
        last_n: количество последних запросов (по умолчанию 5)

    Returns:
        Список словарей: [{'search_type': '...', 'params': {...}, 'timestamp': '...'}, ...]
        Пустой список [] при ошибке подключения к MongoDB.
    """
    try:
        # get_collection() — функция из log_writer.py, возвращает объект
        # pymongo.collection.Collection. Использует Lazy Singleton — если MongoClient
        # уже создан, просто возвращает ту же коллекцию.
        collection = get_collection()

        # Собираем результаты в список вручную (для контроля формата данных).
        # Можно было бы использовать list comprehension, но цикл нагляднее.
        results: list[dict] = []

        # Цепочка вызовов pymongo (Method Chaining):
        #   .find()           — возвращает Cursor (все документы коллекции)
        #   .sort('timestamp', -1) — сортировка: -1 = по убыванию (новые первые)
        #   .limit(last_n)    — максимум last_n документов
        # Результат — Cursor (итератор), перебираем его в for.
        for doc in collection.find().sort('timestamp', -1).limit(last_n):
            # Из каждого документа берём только нужные поля (без _id и прочего)
            results.append({
                'search_type': doc['search_type'],  # 'keyword' или 'genre_year'
                'params': doc['params'],             # Словарь параметров запроса
                'timestamp': doc['timestamp'],       # ISO 8601 строка
            })
        return results
    except Exception:
        # MongoDB недоступна — возвращаем пустой список
        return []
