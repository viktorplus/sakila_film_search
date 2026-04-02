"""
main.py — Точка входа приложения: меню, обработчики поиска, пагинация.

Это ГЛАВНЫЙ файл приложения. При запуске `python main.py` выполняется
функция main(), которая показывает меню и вызывает обработчики.

Структура модуля:
  - _paginate()                — универсальная постраничная навигация
  - handle_keyword_search()    — обработчик поиска по ключевому слову
  - handle_genre_year_search() — обработчик поиска по жанру и годам
  - main()                     — главный цикл (меню → выбор → действие)

print_menu() определена в formatter.py и импортируется оттуда.
Модуль импортирует функции из всех остальных файлов проекта,
объединяя их в единое приложение.
"""

import sys  # Модуль для sys.exit() — завершения программы с кодом ошибки

from config import PAGE_SIZE  # Размер страницы (10) — единая константа (DRY)

# --- ANSI-цвета ---
RESET = '\033[0m'
CYAN = '\033[36m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RED = '\033[31m'

# Функции вывода данных в консоль (форматирование отделено от логики)
from formatter import print_films, print_genres, print_menu, print_popular, print_recent

# Статистика поисковых запросов из MongoDB
from log_stats import get_popular_queries, get_recent_queries

# Запись поисковых запросов в MongoDB
from log_writer import log_search

# Все функции работы с MySQL (подключение, поиск, подсчёт)
from mysql_connector import (
    get_connection,
    get_genres_with_years,
    count_by_keyword,
    count_by_genre_and_year,
    search_by_keyword,
    search_by_genre_and_year,
)

# Тип Connection нужен для аннотации параметров обработчиков
from pymysql.connections import Connection

# Тип Callable нужен для аннотации fetch_fn в _paginate
from typing import Callable


def _paginate(
    fetch_fn: Callable[[int], list[tuple]], # функция, принимающая offset и возвращающая список кортежей
    log_type: str, # тип поиска для логирования ('keyword' или 'genre_year')
    log_params: dict, # параметры запроса для логирования (словарь)
    total_count: int, # общее количество найденных фильмов (из COUNT запроса)
    search_label: str = '', # заголовок поиска для отображения над таблицей
) -> None:
    """
    Универсальная постраничная навигация по результатам.

    Эта функция НЕ ЗНАЕТ, какой именно SQL-запрос выполняется.
    Она получает функцию fetch_fn, которая принимает offset и возвращает записи.
    Это позволяет использовать _paginate и для поиска по ключевому слову,
    и для поиска по жанру — без дублирования кода пагинации.

    Алгоритм:
      1. Вызываем fetch_fn(offset) → получаем PAGE_SIZE+1 записей
      2. Если пришло > PAGE_SIZE записей — есть следующая страница
      3. Берём только первые PAGE_SIZE записей для отображения
      4. Логируем запрос в MongoDB (только на первой странице)
      5. Спрашиваем пользователя "Show next page?"
      6. Если 'y' — увеличиваем offset на PAGE_SIZE и повторяем

    Args:
        fetch_fn: функция, принимающая offset (int), возвращающая список кортежей.
                  Это замыкание (closure) — вложенная функция def fetch(offset),
                  которая "захватывает" параметры поиска из внешней функции.
        log_type: тип поиска для логирования ('keyword' или 'genre_year')
        log_params: параметры запроса для логирования (словарь)
        total_count: общее количество найденных фильмов (из COUNT запроса)
        search_label: заголовок поиска, например "Searching for 'cat'..."
    """
    offset: int = 0        # Текущее смещение: 0, 10, 20, 30...
    first_page: bool = True  # Флаг: это первая страница?

    while True:
        # Запрашиваем PAGE_SIZE+1 записей (трюк для определения наличия следующей стр.)
        results: list[tuple] = fetch_fn(offset)

        # Если пришло больше PAGE_SIZE записей — есть ещё данные
        has_more: bool = len(results) > PAGE_SIZE

        # Берём только первые PAGE_SIZE записей для отображения (11-ю не показываем)
        page: list[tuple] = results[:PAGE_SIZE]

        # Логируем запрос в MongoDB ТОЛЬКО при первой загрузке страницы.
        # Логируем даже пустые результаты — это помогает понять,
        # какие фильмы пользователи ищут и чего не хватает в базе.
        if first_page:
            log_search(log_type, log_params)
            first_page = False

        if not page:
            # Если результатов нет вообще (первая страница пуста)
            print(f"  ❌ {YELLOW}No films found.{RESET}")
            break

        # Выводим фильмы текущей страницы в виде таблицы с рамкой
        print_films(page, total_count, search_label)

        if not has_more:
            # Данных больше нет — выходим из цикла пагинации
            break

        # Спрашиваем пользователя: показать следующую страницу?
        while True:
            answer: str = input(f"\n  ➡️  {CYAN}Show next page? (y/Enter=back):{RESET} ").strip().lower()
            if answer == 'y' or answer == '':
                break
            print(f"  {YELLOW}Enter 'y' or press Enter.{RESET}")

        if answer != 'y':
            break  # Пользователь нажал Enter — возврат в меню

        # Увеличиваем offset для следующей порции данных
        offset += PAGE_SIZE


def handle_keyword_search(connection: Connection) -> None:
    """
    Обработчик поиска фильмов по ключевому слову.

    1. Запрашивает ключевое слово у пользователя
    2. Считает общее количество результатов (COUNT)
    3. Создаёт вложенную функцию fetch (замыкание), которая "запоминает"
       connection и keyword из внешнего контекста
    4. Вызывает _paginate для постраничного отображения

    Args:
        connection: активное подключение к MySQL
    """
    keyword: str = input(f"{CYAN}Enter keyword (or Enter=back):{RESET} ").strip()
    if not keyword:
        return  # Пустой ввод — возврат в меню

    # COUNT(*) — общее количество фильмов (показывается как "Found: N")
    total: int = count_by_keyword(connection, keyword)

    def fetch(offset: int) -> list[tuple]:
        """
        Замыкание (closure) — вложенная функция, которая "захватывает"
        переменные connection и keyword из внешней функции handle_keyword_search.
        Благодаря этому _paginate может вызывать fetch(offset),
        не зная ничего о connection и keyword.
        """
        return search_by_keyword(connection, keyword, offset)

    # Заголовок поиска для отображения над таблицей
    label: str = f"Searching for '{keyword}'..."
    _paginate(fetch, 'keyword', {'keyword': keyword}, total, label)


def handle_genre_year_search(connection: Connection) -> None:
    """
    Обработчик поиска фильмов по жанру и диапазону лет.

    1. Вывод таблицы жанров (с min/max годами)
    2. Выбор жанра по номеру (с валидацией)
    3. Ввод года или диапазона лет (с валидацией)
    4. Подсчёт результатов и пагинацию

    Args:
        connection: активное подключение к MySQL
    """
    # Загружаем список жанров с диапазонами лет из MySQL
    genres_data: list[dict] = get_genres_with_years(connection)
    # Выводим таблицу жанров пользователю
    print_genres(genres_data)

    # --- Блок выбора жанра ---
    # повторяем запрос, пока пользователь не введёт корректное значение.
    while True:
        genre_input: str = input(f"{CYAN}Enter genre number (or Enter=back):{RESET} ").strip()
        if not genre_input:
            return  # Пустой ввод — возврат в меню

        # Защищает от int() на нечисловом вводе (ValueError).
        if genre_input.isdigit():
            idx: int = int(genre_input) - 1  # -1: пользователь видит 1-16, в списке 0-15
            if 0 <= idx < len(genres_data):
                # Валидный выбор — извлекаем данные жанра
                genre: str = genres_data[idx]['name']
                genre_min: int = genres_data[idx]['min_year']
                genre_max: int = genres_data[idx]['max_year']
                break  # Выходим из цикла валидации
        print(f"  {YELLOW}Enter 1-{len(genres_data)}.{RESET}")

    # --- Блок ввода года/диапазона ---
    while True:
        year_input: str = input(f"{CYAN}Enter year or range ({genre_min}-{genre_max}):{RESET} ").strip()
        if not year_input:
            return  # Пустой ввод — возврат в меню

        try:
            if '-' in year_input:
                # Ввод диапазона: "2000-2010" → split('-') → ['2000', '2010']
                parts: list[str] = year_input.split('-')
                year_from: int = int(parts[0].strip())  # .strip() убирает пробелы: "2000 " → "2000"
                year_to: int = int(parts[1].strip())
            else:
                # Ввод одного года: "2006" → year_from = year_to = 2006
                year_from = int(year_input)
                year_to = year_from
        except (ValueError, IndexError):
            # ValueError — если int() получил нечисловую строку
            # IndexError — если split вернул меньше 2 элементов
            print(f"  {YELLOW}Invalid format. Use: 2000 or 2000-2010{RESET}")
            continue  # Повторяем запрос ввода

        if year_from > year_to:
            print(f"  {YELLOW}'From' must be <= 'To'.{RESET}")
            continue

        if year_from < genre_min or year_to > genre_max:
            print(f"  {YELLOW}Years must be in range {genre_min}-{genre_max}.{RESET}")
            continue
        break  # Все проверки пройдены — выходим из цикла

    # COUNT(*) — общее количество фильмов для выбранного жанра и диапазона
    total: int = count_by_genre_and_year(connection, genre, year_from, year_to)

    def fetch(offset: int) -> list[tuple]:
        """
        Замыкание (closure) — захватывает connection, genre, year_from, year_to
        из внешней функции handle_genre_year_search.
        """
        return search_by_genre_and_year(connection, genre, year_from, year_to, offset)

    # Словарь параметров для записи в MongoDB (лог)
    params: dict = {'genre': genre, 'year_from': year_from, 'year_to': year_to}

    # Заголовок поиска для отображения над таблицей
    label: str = f"Searching genre '{genre}' ({year_from}-{year_to})..."
    _paginate(fetch, 'genre_year', params, total, label)


def main() -> None:
    """
    Главная функция — точка входа приложения.

    1. Устанавливает подключение к MySQL (одно на всё время работы)
    2. В бесконечном цикле показывает меню и обрабатывает выбор
    3. При выходе (choice == '0') закрывает подключение

    Обработка ошибок:
      - Если MySQL недоступен при запуске — выход с кодом 1 (sys.exit(1))
      - Ошибки MongoDB обрабатываются внутри log_writer и log_stats (pass)
    """
    try:
        # Создаём подключение к MySQL один раз при старте.
        # Оно переиспользуется для всех запросов (не создаём каждый раз новое).
        connection: Connection = get_connection()
    except Exception as e:
        # Если MySQL недоступен — печатаем ошибку и завершаем программу.
        # sys.exit(1) — код 1 означает "завершение с ошибкой" (0 = успешно).
        print(f"  ❌ {RED}Could not connect to MySQL: {e}{RESET}")
        sys.exit(1)

    # Главный цикл приложения — работает, пока пользователь не выберет "0"
    while True:
        print_menu()
        choice: str = input(f"\n  {CYAN}Choose action:{RESET} ").strip()

        if choice == '1':
            handle_keyword_search(connection)
        elif choice == '2':
            handle_genre_year_search(connection)
        elif choice == '3':
            # get_popular_queries() — читает из MongoDB через aggregation pipeline
            print_popular(get_popular_queries())
        elif choice == '4':
            # get_recent_queries() — читает последние запросы из MongoDB
            print_recent(get_recent_queries())
        elif choice == '0':
            print(f"  👋 {GREEN}Goodbye!{RESET}")
            break
        else:
            print(f"  {YELLOW}Invalid choice.{RESET}")

    # Закрываем MySQL-соединение при выходе из программы.
    connection.close()


# При импорте (import main) этот блок НЕ выполнится.
# __name__ == "__main__" только когда файл запущен как скрипт: python main.py
if __name__ == "__main__":
    main()
