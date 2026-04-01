"""
mysql_connector.py — Модуль подключения к MySQL и SQL-запросов.

Этот файл отвечает за ВСЮ работу с MySQL:
  - Подключение к базе данных sakila
  - Получение списка жанров с диапазонами лет
  - Получение общего диапазона годов выпуска фильмов
  - Поиск фильмов по ключевому слову и по жанру/году
  - Подсчёт общего количества результатов (COUNT) для пагинации

Таблицы Sakila, используемые в запросах:
  - film           — основная таблица фильмов (title, release_year)
  - category       — справочник жанров (category_id, name)
  - film_category  — связь многие-ко-многим между фильмами и жанрами
"""

import os  # Модуль для доступа к переменным окружения (os.getenv)

import pymysql  # Библиотека для подключения к MySQL из Python
from pymysql.connections import Connection  # Тип подключения (для аннотаций)
from dotenv import load_dotenv  # Загрузка переменных окружения из .env файла

from config import PAGE_SIZE  # Размер страницы — единый для всего приложения (DRY)

# Загружаем переменные окружения из файла .env в текущий процесс.
# После этого os.getenv('MYSQL_HOST') вернёт значение из .env.
load_dotenv()

# Конфигурация подключения к MySQL — собираем из переменных окружения.
# Словарь, который потом распакуется в pymysql.connect(**_MYSQL_CONFIG).
_MYSQL_CONFIG: dict[str, str | int | None] = {
    'host': os.getenv('MYSQL_HOST'),          # Адрес сервера MySQL
    'port': int(os.getenv('MYSQL_PORT', 3306)),  # Порт (3306 по умолчанию)
    'user': os.getenv('MYSQL_USER'),          # Имя пользователя БД
    'password': os.getenv('MYSQL_PASSWORD'),  # Пароль
    'database': os.getenv('MYSQL_DB'),        # Имя базы данных (sakila)
}


def get_connection() -> Connection:
    """
    Создаёт и возвращает новое подключение к MySQL.

    **_MYSQL_CONFIG — это распаковка словаря в именованные аргументы:
      pymysql.connect(host='...', port=3306, user='...', password='...', database='sakila')

    Если MySQL недоступен — бросает исключение (ловится в main.py).

    Returns:
        Connection — объект подключения pymysql
    """
    return pymysql.connect(**_MYSQL_CONFIG)


def get_genres_with_years(connection: Connection) -> list[dict[str, str | int]]:
    """
    Получает список жанров с минимальным и максимальным годом выпуска.

    SQL использует два JOIN для объединения трёх таблиц:
      category → film_category → film
    Потому что таблицы связаны через промежуточную film_category (связь M:N).

    GROUP BY c.name — группировка по жанру для вычисления MIN/MAX года.
    ORDER BY c.name — алфавитная сортировка жанров.

    Args:
        connection: активное подключение к MySQL

    Returns:
        Список словарей: [{'name': 'Action', 'min_year': 2006, 'max_year': 2006}, ...]
    """
    sql: str = """
        SELECT c.name, MIN(f.release_year), MAX(f.release_year)
        FROM category c
        JOIN film_category fc ON c.category_id = fc.category_id
        JOIN film f ON fc.film_id = f.film_id
        GROUP BY c.name
        ORDER BY c.name
    """
    # with — контекстный менеджер: курсор автоматически закроется после блока
    with connection.cursor() as cursor:
        cursor.execute(sql)
        # fetchall() возвращает список кортежей, например: [('Action', 2006, 2006), ...]
        # Преобразуем каждый кортеж в словарь для удобного доступа по ключу
        return [
            {'name': row[0], 'min_year': row[1], 'max_year': row[2]}
            for row in cursor.fetchall()
        ]


def count_by_keyword(connection: Connection, keyword: str) -> int:
    """
    Считает ОБЩЕЕ количество фильмов, подходящих под ключевое слово.

    Вызывается один раз при первой загрузке результатов.
    Результат показывается как "Found: N" и используется для пагинации.

    %s — плейсхолдер PyMySQL. Библиотека подставляет значение БЕЗОПАСНО
    (экранирует спецсимволы), защищая от SQL-инъекций.

    Args:
        connection: подключение к MySQL
        keyword: ключевое слово для поиска

    Returns:
        int — общее количество найденных фильмов (может быть 0)
    """
    sql: str = """
        SELECT COUNT(*)
        FROM film f
        WHERE f.title LIKE %s
    """
    with connection.cursor() as cursor:
        # f"%{keyword}%" — оборачиваем в % для LIKE (поиск подстроки в любой позиции)
        cursor.execute(sql, (f"%{keyword}%",))
        # fetchone() возвращает кортеж, например (42,) → берём [0] = 42
        return cursor.fetchone()[0]


def search_by_keyword(connection: Connection, keyword: str, offset: int = 0) -> list[tuple]:
    """
    Поиск фильмов по подстроке в названии (LIKE '%keyword%').

    LEFT JOIN — нужен потому что у некоторых фильмов может не быть жанра.
    Обычный JOIN пропустил бы такие фильмы, а LEFT JOIN покажет их (с genre = NULL).

    LIMIT PAGE_SIZE + 1 — трюк: запрашиваем на 1 запись больше, чем показываем.
    Если пришло 11 записей — значит есть следующая страница.
    Если 10 или меньше — данных больше нет.

    OFFSET — смещение для пагинации:
      OFFSET 0  → первые 11 записей
      OFFSET 10 → следующие 11 записей

    Args:
        connection: подключение к MySQL
        keyword: ключевое слово
        offset: с какой записи начинать (по умолчанию 0)

    Returns:
        Список кортежей: [(title, release_year, genre, description), ...]
        Максимум PAGE_SIZE + 1 записей
    """
    sql: str = """
        SELECT f.title, f.release_year, c.name, f.description
        FROM film f
        LEFT JOIN film_category fc ON f.film_id = fc.film_id
        LEFT JOIN category c ON fc.category_id = c.category_id
        WHERE f.title LIKE %s
        ORDER BY f.title
        LIMIT %s OFFSET %s
    """
    with connection.cursor() as cursor:
        # %s — плейсхолдеры, PyMySQL подставит значения безопасно (защита от SQL-инъекций)
        cursor.execute(sql, (f"%{keyword}%", PAGE_SIZE + 1, offset))
        return cursor.fetchall()


def count_by_genre_and_year(connection: Connection, genre: str, year_from: int, year_to: int) -> int:
    """
    Считает ОБЩЕЕ количество фильмов по жанру и диапазону лет.

    INNER JOIN (просто JOIN) — потому что мы ищем по жанру, фильм обязан его иметь.
    BETWEEN — включает обе границы: BETWEEN 2000 AND 2010 → 2000, 2001, ..., 2010.

    Args:
        connection: подключение к MySQL
        genre: точное название жанра (например 'Comedy')
        year_from: начальный год (включительно)
        year_to: конечный год (включительно)

    Returns:
        int — общее количество найденных фильмов (может быть 0)
    """
    sql: str = """
        SELECT COUNT(*)
        FROM film f
        JOIN film_category fc ON f.film_id = fc.film_id
        JOIN category c ON fc.category_id = c.category_id
        WHERE c.name = %s AND f.release_year BETWEEN %s AND %s
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, (genre, year_from, year_to))
        return cursor.fetchone()[0]


def search_by_genre_and_year(
    connection: Connection, genre: str, year_from: int, year_to: int, offset: int = 0
) -> list[tuple]:
    """
    Поиск фильмов по жанру и диапазону лет выпуска.

    ORDER BY f.release_year, f.title — сортировка сначала по году, потом по алфавиту.
    LIMIT PAGE_SIZE + 1 — трюк для определения наличия следующей страницы.

    Args:
        connection: подключение к MySQL
        genre: точное название жанра
        year_from: начальный год (включительно)
        year_to: конечный год (включительно)
        offset: смещение для пагинации (по умолчанию 0)

    Returns:
        Список кортежей: [(title, release_year, genre, description), ...]
        Максимум PAGE_SIZE + 1 записей
    """
    sql: str = """
        SELECT f.title, f.release_year, c.name, f.description
        FROM film f
        JOIN film_category fc ON f.film_id = fc.film_id
        JOIN category c ON fc.category_id = c.category_id
        WHERE c.name = %s AND f.release_year BETWEEN %s AND %s
        ORDER BY f.release_year, f.title
        LIMIT %s OFFSET %s
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, (genre, year_from, year_to, PAGE_SIZE + 1, offset))
        return cursor.fetchall()
