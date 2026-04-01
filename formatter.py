"""
formatter.py — Форматирование и вывод данных в консоль.

Этот модуль отвечает за ВСЁ отображение информации пользователю.
main.py вызывает функции этого модуля, передавая готовые данные.

Принцип: formatter НЕ знает откуда данные (MySQL, MongoDB, файл) —
он только красиво выводит то, что ему дали. Это разделение ответственности (SRP).

Функции:
  - print_films()    — список фильмов (результат поиска)
  - print_genres()   — таблица жанров с годами
  - print_popular()  — популярные поисковые запросы
  - print_recent()   — последние поисковые запросы
  - print_menu()     — главное меню приложения
  - _format_label()  — вспомогательная: форматирует описание запроса

"""

import re             # Для удаления ANSI escape-кодов при подсчёте длины строки
import textwrap       # Стандартная библиотека для переноса текста по ширине

from config import TABLE_W  # Ширина таблиц задаётся в config.py

# --- ANSI-цвета для консольного вывода ---
RESET = '\033[0m'
BOLD = '\033[1m'
DIM = '\033[2m'          # Приглушённый текст (для рамок)
CYAN = '\033[36m'        # Заголовки таблиц, рамки
GREEN = '\033[32m'       # Названия фильмов, жанров
YELLOW = '\033[33m'      # Годы, числа
WHITE = '\033[97m'       # Основной текст
MAGENTA = '\033[35m'     # Метки поиска, ID
RED = '\033[31m'         # Выход, ошибки

# --- Ширина содержимого между │ и │ ---
INNER_W: int = TABLE_W - 2

# --- Фиксированная ширина колонок таблицы фильмов ---
# Формула строки: │ {id_w} ␣␣ {title_w} ␣␣ {year_w} │
# INNER_W = 1 + id_w + 2 + title_w + 2 + year_w + 1 = id_w + title_w + year_w + 6
ID_W: int = 2
YEAR_W: int = 4
TITLE_W: int = INNER_W - ID_W - YEAR_W - 6  # 36


def print_films(films: list[tuple], total_count: int, search_label: str = '') -> None:
    """
    Выводит список фильмов в виде таблицы с рамкой из Unicode box-drawing символов.

    Формат вывода:
      Searching for 'cat'... (Total matches: 12)
      ┌────────────────────────────────────────────────┐
      │ ID  Title                              Year    │
      ├────────────────────────────────────────────────┤
      │  1  CAT MOVIE                          2006    │
      │ 🎭 Comedy                                      │
      │ A short description of the film...             │
      └────────────────────────────────────────────────┘

    Ширина таблицы фиксирована — TABLE_W (задаётся в config.py).
 
    Args:
        films: список кортежей (title, year, genre, description) — одна страница
        total_count: общее количество найденных фильмов (из COUNT запроса)
        search_label: строка-заголовок, например "Searching for 'cat'..."
    """
    # --- Заголовок с количеством ---
    if search_label:
        print(f"\n{CYAN}{search_label}{RESET} (Total matches: {YELLOW}{total_count}{RESET})")
    else:
        print(f"\n  Found: {YELLOW}{total_count}{RESET}")

    # --- Строки рамки таблицы ---
    top: str = f"{DIM}┌{'─' * INNER_W}┐{RESET}"
    sep: str = f"{DIM}├{'─' * INNER_W}┤{RESET}"
    bot: str = f"{DIM}└{'─' * INNER_W}┘{RESET}"

    # --- Рисуем таблицу ---
    print(top)
    print(f"{DIM}│{RESET} {BOLD}{'ID':^{ID_W}}  {'Title':<{TITLE_W}}  {'Year':^{YEAR_W}}{RESET} {DIM}│{RESET}")
    print(sep)
    for i, row in enumerate(films, 1):
        title: str = str(row[0])[:TITLE_W]
        year = row[1]
        genre: str = str(row[2]) if len(row) > 2 and row[2] else ''
        desc: str = row[3] if len(row) > 3 and row[3] else ''
        print(f"{DIM}│{RESET} {MAGENTA}{i:^{ID_W}}{RESET}  {GREEN}{title:<{TITLE_W}}{RESET}  {YELLOW}{year:^{YEAR_W}}{RESET} {DIM}│{RESET}")
        if genre:
            max_line: int = INNER_W - 4
            genre_str: str = f"🎭 {genre}"[:max_line]
            pad: int = max_line - len(genre_str) - 1  # -1: emoji 🎭 = 2 колонки
            print(f"{DIM}│{RESET}  {CYAN}{genre_str}{RESET}{' ' * pad}  {DIM}│{RESET}")
        if desc:
            max_desc: int = INNER_W - 4
            lines: list[str] = textwrap.wrap(desc, width=max_desc)
            for line in lines:
                print(f"{DIM}│{RESET}  {WHITE}{line:<{max_desc}}{RESET}  {DIM}│{RESET}")
        if i < len(films):
            print(sep)
    print(bot)


def print_genres(genres_data: list[dict[str, str | int]]) -> None:
    """
    Выводит таблицу жанров с диапазонами лет в виде таблицы с рамкой.

    Args:
        genres_data: список словарей [{'name': 'Action', 'min_year': 2006, 'max_year': 2006}, ...]
    """
    id_w: int = max(2, len(str(len(genres_data))))
    range_w: int = 11  # "2006 - 2006"
    name_w: int = INNER_W - id_w - range_w - 6

    top = f"{DIM}┌{'─' * INNER_W}┐{RESET}"
    sep = f"{DIM}├{'─' * INNER_W}┤{RESET}"
    bot = f"{DIM}└{'─' * INNER_W}┘{RESET}"

    print(f"\n  🎭 {BOLD}{CYAN}MOVIE GENRES & YEAR RANGE{RESET}")
    print(top)
    print(f"{DIM}│{RESET} {BOLD}{'#':^{id_w}}  {'Genre':<{name_w}}  {'Year Range':^{range_w}}{RESET} {DIM}│{RESET}")
    print(sep)
    for i, g in enumerate(genres_data, 1):
        name: str = str(g['name'])[:name_w]
        year_range: str = f"{g['min_year']} - {g['max_year']}"
        print(f"{DIM}│{RESET} {MAGENTA}{i:^{id_w}}{RESET}  {GREEN}{name:<{name_w}}{RESET}  {YELLOW}{year_range:^{range_w}}{RESET} {DIM}│{RESET}")
    print(bot)


def print_popular(queries: list[dict]) -> None:
    """
    Выводит список самых популярных поисковых запросов.

    Получает данные из log_stats.get_popular_queries().
    Каждый элемент — словарь: {'search_type': '...', 'params': {...}, 'count': N}

    _format_label() — вспомогательная функция, преобразует search_type + params
    в читаемую строку: "Keyword: cat" или "Genre: Comedy, Years: 2000-2010".

    Args:
        queries: список словарей с полями search_type, params, count
    """
    if not queries:
        print(f"  ❌ {YELLOW}No search history found.{RESET}")
        return

    id_w: int = max(2, len(str(len(queries)))) # Ширина колонки ID зависит от количества запросов
    count_w: int = 5 
    query_w: int = INNER_W - id_w - count_w - 6 
    labels: list[str] = [_format_label(q['search_type'], q['params'])[:query_w] for q in queries] #

    top = f"{DIM}┌{'─' * INNER_W}┐{RESET}"
    mid = f"{DIM}├{'─' * INNER_W}┤{RESET}"
    bot = f"{DIM}└{'─' * INNER_W}┘{RESET}"

    print(f"\n  ⭐ {BOLD}{CYAN}POPULAR SEARCHES{RESET}")
    print(top)
    print(f"{DIM}│{RESET} {BOLD}{'#':^{id_w}}  {'Query':<{query_w}}  {'Count':^{count_w}}{RESET} {DIM}│{RESET}")
    print(mid)
    for i, (q, label) in enumerate(zip(queries, labels), 1):
        print(f"{DIM}│{RESET} {MAGENTA}{i:^{id_w}}{RESET}  {GREEN}{label:<{query_w}}{RESET}  {YELLOW}{q['count']:^{count_w}}{RESET} {DIM}│{RESET}")
    print(bot)


def print_recent(queries: list[dict]) -> None:
    """
    Выводит список последних поисковых запросов с временем.

    Получает данные из log_stats.get_recent_queries().
    Каждый элемент — словарь: {'search_type': '...', 'params': {...}, 'timestamp': '...'}

    .replace('T', ' ') — преобразует ISO формат '2025-01-15T14:30:00'
    в более читаемый '2025-01-15 14:30:00' (заменяет букву T на пробел).

    Args:
        queries: список словарей с полями search_type, params, timestamp
    """
    if not queries:
        print(f"  ❌ {YELLOW}No search history found.{RESET}")
        return

    id_w: int = max(2, len(str(len(queries))))
    time_w: int = 19  # "2026-04-01 20:20:11"
    query_w: int = INNER_W - id_w - time_w - 6
    labels: list[str] = [_format_label(q['search_type'], q['params'])[:query_w] for q in queries]
    times: list[str] = [q['timestamp'].replace('T', ' ')[:time_w] for q in queries]

    top = f"{DIM}┌{'─' * INNER_W}┐{RESET}"
    mid = f"{DIM}├{'─' * INNER_W}┤{RESET}"
    bot = f"{DIM}└{'─' * INNER_W}┘{RESET}"

    print(f"\n  🕐 {BOLD}{CYAN}RECENT SEARCHES{RESET}")
    print(top)
    print(f"{DIM}│{RESET} {BOLD}{'#':^{id_w}}  {'Query':<{query_w}}  {'Time':^{time_w}}{RESET} {DIM}│{RESET}")
    print(mid)
    for i, (label, time) in enumerate(zip(labels, times), 1):
        print(f"{DIM}│{RESET} {MAGENTA}{i:^{id_w}}{RESET}  {GREEN}{label:<{query_w}}{RESET}  {YELLOW}{time:^{time_w}}{RESET} {DIM}│{RESET}")
    print(bot)


def print_menu() -> None:
    """Выводит главное меню приложения в виде таблицы."""
    top = f"{DIM}┌{'─' * INNER_W}┐{RESET}"
    sep = f"{DIM}├{'─' * INNER_W}┤{RESET}"
    bot = f"{DIM}└{'─' * INNER_W}┘{RESET}"

    def row(text: str) -> None:
        # Убираем ANSI-коды для подсчёта видимой длины, -1 за emoji (2 колонки)
        clean: str = re.sub(r'\033\[[0-9;]*m', '', text)
        pad: int = INNER_W - len(clean) - 1
        print(f"{DIM}│{RESET}{text}{' ' * pad}{DIM}│{RESET}")

    print()
    print(top)
    row(f"  {BOLD}{CYAN}🎬 === MOVIE SEARCH MENU ==={RESET}")
    print(sep)
    row(f"  {GREEN}1{RESET} - 🔍 Search by keyword")
    row(f"  {GREEN}2{RESET} - 🎭 Search by genre and years")
    row(f"  {GREEN}3{RESET} - ⭐ Show popular searches")
    row(f"  {GREEN}4{RESET} - 🕐 Show recent searches")
    row(f"  {RED}0{RESET} - 🚪 Exit")
    print(bot)


def _format_label(search_type: str, params: dict) -> str:
    """
    Формирует человекочитаемую метку для поискового запроса.

    Вспомогательная функция (начинается с _), используется только внутри модуля.

    Примеры:
      _format_label('keyword', {'keyword': 'cat'})
        → 'Keyword: cat'
      _format_label('genre_year', {'genre': 'Comedy', 'year_from': 2000, 'year_to': 2010})
        → 'Genre: Comedy, Years: 2000-2010'

    params.get('keyword', '') — безопасное получение значения из словаря.
    Если ключ 'keyword' отсутствует, вернёт '' (пустую строку) вместо KeyError.

    Args:
        search_type: тип поиска ('keyword' или 'genre_year')
        params: словарь параметров запроса

    Returns:
        Отформатированная строка для отображения в консоли
    """
    if search_type == 'keyword':
        return f"Keyword: {params.get('keyword', '')}"
    if search_type == 'genre_year':
        genre: str = params.get('genre', '')
        year_from = params.get('year_from', '')
        year_to = params.get('year_to', '')
        return f"Genre: {genre}, Years: {year_from}-{year_to}"
    # Fallback для неизвестных типов (на случай расширения)
    return f"{search_type}: {params}"
