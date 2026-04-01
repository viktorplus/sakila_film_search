# Sakila Film Search

Консольное приложение для поиска фильмов по базе данных MySQL Sakila
с логированием запросов в MongoDB и статистикой поиска.

## Содержание

- [Цель проекта](#цель-проекта)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
- [Технологии](#технологии)
- [Структура проекта](#структура-проекта)
- [Работа с базами данных](#работа-с-базами-данных)
- [Примеры работы](#примеры-работы)
- [Автор](#автор)

## Цель проекта

Приложение демонстрирует практическое применение Python для разработки
консольного интерфейса с подключением к реальным базам данных. Реализовано:

- поиск фильмов по ключевому слову (`LIKE '%keyword%'`) с пагинацией
- фильтрация по жанрам и диапазону лет выпуска с пагинацией
- сохранение истории поиска в MongoDB
- статистика: топ-5 популярных запросов и последние 5 запросов
- цветной вывод в терминале (ANSI-цвета) с Unicode box-drawing таблицами

## Быстрый старт

```bash
# 1. Клонируем репозиторий
git clone https://github.com/viktorplus/sakila_film_search.git
cd sakila_film_search

# 2. Создаём и активируем виртуальное окружение
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Устанавливаем зависимости
pip install -r requirements.txt

# 4. Создаём файл .env и прописываем настройки подключения (см. раздел Конфигурация)

# 5. Запускаем приложение
python main.py
```

### Требования

| Компонент     | Версия |
|---------------|--------|
| Python        | 3.10+  |
| pymysql       | любая  |
| pymongo       | любая  |
| python-dotenv | любая  |

## Конфигурация

Все настройки подключений находятся в файле `.env`.
Создайте его в корне проекта и заполните своими данными:

```ini
# --- MySQL ---
MYSQL_HOST=your-mysql-host
MYSQL_PORT=3306
MYSQL_USER=your-user
MYSQL_PASSWORD=your-password
MYSQL_DB=sakila

# --- MongoDB ---
MONGO_URI=mongodb://user:password@host:port/?authSource=db_name
MONGO_DB=your-db
MONGO_COLLECTION=your-collection-name
```

> **Важно:** файл `.env` содержит пароли и добавлен в `.gitignore` — он не попадает в Git.

## Технологии

| Технология        | Назначение                                     |
|-------------------|------------------------------------------------|
| Python            | Основной язык приложения                       |
| MySQL + pymysql   | Основная БД Sakila: фильмы, жанры, годы        |
| MongoDB + pymongo | Хранение и аналитика поисковых запросов        |
| python-dotenv     | Загрузка настроек подключения из `.env` файла  |

### Паттерны и решения

**Lazy Singleton для MongoDB** — `log_writer.py` хранит единственный экземпляр
`MongoClient` в переменной модуля `_client`. При первом вызове `get_collection()`
создаётся подключение, при последующих — возвращается существующее.

**Пагинация через LIMIT+1** — SQL-запросы запрашивают `PAGE_SIZE + 1` записей.
Если пришло 11 — значит есть следующая страница, показываем первые 10.
Если 10 или меньше — данных больше нет.

**MongoDB как необязательный компонент** — все обращения к MongoDB обёрнуты
в `try/except`. Если MongoDB недоступна, поиск фильмов продолжает работать,
просто логирование и статистика отключаются.

**ANSI-цвета** — модуль `formatter.py` использует escape-последовательности
для цветного вывода: зелёный — названия, жёлтый — годы/числа, голубой — заголовки.

**DRY** — общие константы (`PAGE_SIZE`, `TABLE_W`) вынесены в `config.py`.
Повторяющаяся логика пагинации — в функцию `_paginate()`.
Форматирование меток запросов — в `_format_label()`.

## Структура проекта

```text
sakila_film_search/
│
├── main.py             # Точка входа, меню, обработчики, пагинация
├── config.py           # Общие константы (PAGE_SIZE, TABLE_W)
├── mysql_connector.py  # Подключение к MySQL и все SQL-запросы
├── log_writer.py       # Запись поисковых запросов в MongoDB
├── log_stats.py        # Получение статистики из MongoDB
├── formatter.py        # Форматирование и вывод данных в консоль
├── .env                # Настройки подключения (не в Git)
├── .gitignore          # Игнорируемые файлы
└── README.md           # Этот файл
```

### Зависимости между модулями

```text
main.py
 ├── config.py            (PAGE_SIZE, TABLE_W)
 ├── formatter.py         (print_films, print_genres, print_menu, print_popular, print_recent)
 ├── log_stats.py         (get_popular_queries, get_recent_queries)
 │    └── log_writer.py   (get_collection)
 ├── log_writer.py        (log_search)
 └── mysql_connector.py   (get_connection, search_by_keyword, ...)
      └── config.py       (PAGE_SIZE)
```

## Работа с базами данных

### MySQL — поиск фильмов

Таблицы Sakila, задействованные в запросах:

| Таблица         | Поля                                      | Назначение                |
|-----------------|-------------------------------------------|---------------------------|
| `film`          | film_id, title, release_year, description | Основная таблица фильмов  |
| `film_category` | film_id, category_id                      | Связь фильм ↔ жанр (M:N)  |
| `category`      | category_id, name                         | Справочник жанров         |

#### Загрузка справочников

```sql
-- Жанры с диапазонами лет
SELECT c.name, MIN(f.release_year), MAX(f.release_year)
FROM category c
JOIN film_category fc ON c.category_id = fc.category_id
JOIN film f ON fc.film_id = f.film_id
GROUP BY c.name
ORDER BY c.name;

-- Общий диапазон лет
SELECT MIN(release_year), MAX(release_year) FROM film;
```

#### Поиск по ключевому слову

```sql
SELECT f.title, f.release_year, c.name, f.description
FROM film f
LEFT JOIN film_category fc ON f.film_id = fc.film_id
LEFT JOIN category c ON fc.category_id = c.category_id
WHERE f.title LIKE '%keyword%'
ORDER BY f.title
LIMIT 11 OFFSET 0;
```

`LEFT JOIN` — чтобы не потерять фильмы без жанра.
`LIMIT 11` — трюк `PAGE_SIZE + 1` для определения наличия следующей страницы.

#### Поиск по жанру и диапазону лет

```sql
SELECT f.title, f.release_year, c.name, f.description
FROM film f
JOIN film_category fc ON f.film_id = fc.film_id
JOIN category c ON fc.category_id = c.category_id
WHERE c.name = 'Comedy' AND f.release_year BETWEEN 2000 AND 2010
ORDER BY f.release_year, f.title
LIMIT 11 OFFSET 0;
```

`JOIN` (не LEFT) — фильтрация по жанру подразумевает его наличие.

#### Запросы подсчёта (для пагинации)

```sql
-- По ключевому слову
SELECT COUNT(*)
FROM film f
WHERE f.title LIKE '%keyword%';

-- По жанру и годам
SELECT COUNT(*)
FROM film f
JOIN film_category fc ON f.film_id = fc.film_id
JOIN category c ON fc.category_id = c.category_id
WHERE c.name = 'Comedy' AND f.release_year BETWEEN 2000 AND 2010;
```

Выполняется один раз при первой загрузке — результат показывается как `Total matches: N`.

### MongoDB — логирование и статистика

#### Структура документа

Каждый поисковый запрос сохраняется как документ:

```json
{
  "timestamp": "2026-03-28T14:30:00",
  "search_type": "keyword",
  "params": {
    "keyword": "matrix"
  }
}
```

Для поиска по жанру:

```json
{
  "timestamp": "2026-03-28T14:35:00",
  "search_type": "genre_year",
  "params": {
    "genre": "Comedy",
    "year_from": 2000,
    "year_to": 2010
  }
}
```

#### Aggregation Pipeline — топ-5 популярных запросов

```python
pipeline = [
    # 1. Группируем по (search_type + params), считаем количество
    {"$group": {
        "_id": {"search_type": "$search_type", "params": "$params"},
        "count": {"$sum": 1},
    }},
    # 2. Сортируем по убыванию частоты
    {"$sort": {"count": -1}},
    # 3. Берём топ-5
    {"$limit": 5},
]
```

Аналог SQL:

```sql
SELECT search_type, params, COUNT(*) as count
FROM searches
GROUP BY search_type, params
ORDER BY count DESC
LIMIT 5;
```

#### Последние 5 запросов

```python
collection.find().sort('timestamp', -1).limit(5)
```

Сортировка по `timestamp` в порядке убывания, берём первые 5 документов.

## Примеры работы

### Главное меню

```text
┌────────────────────────────────────────────────────────────────────┐
│  🎬 === MOVIE SEARCH MENU ===                                         │
├────────────────────────────────────────────────────────────────────┤
│  1 - 🔍 Search by keyword                                              │
│  2 - 🎭 Search by genre and years                                      │
│  3 - ⭐ Show popular searches                                           │
│  4 - 🕐 Show recent searches                                           │
│  0 - 🚪 Exit                                                           │
└────────────────────────────────────────────────────────────────────┘

  Choose action:
```

### Результат поиска по ключевому слову

```text
Enter keyword (or Enter=back): love

Searching for 'love'... (Total matches: 28)
┌────────────────────────────────────────────────────────────────────┐
│ ID  Title                                                    Year    │
├────────────────────────────────────────────────────────────────────┤
│  1  IDAHO LOVE                                               2017    │
│  🎭 Drama                                                            │
│  A Fast-Paced Drama of a Student And a Husband who must      │
│  Confront a Cat in An Abandoned Fun House                    │
├────────────────────────────────────────────────────────────────────┤
│  2  INDIAN LOVE                                              1993    │
│  🎭 Sci-Fi                                                           │
│  A Insightful Saga of a Mad Scientist who must ...           │
└────────────────────────────────────────────────────────────────────┘

  ➡️  Show next page? (y/Enter=back):
```

### Список жанров

```text
  🎭 MOVIE GENRES & YEAR RANGE
┌────────────────────────────────────────────────────────────────────┐
│  #  Genre                                       Year Range       │
├────────────────────────────────────────────────────────────────────┤
│  1  Action                                      2006 - 2006      │
│  2  Animation                                   2006 - 2006      │
│  3  Children                                    2006 - 2006      │
│ ...                                                              │
│ 16  Travel                                      2006 - 2006      │
└────────────────────────────────────────────────────────────────────┘
```

### Популярные запросы

```text
  ⭐ POPULAR SEARCHES
┌────────────────────────────────────────────────────────────────────┐
│  #  Query                                               Count    │
├────────────────────────────────────────────────────────────────────┤
│  1  Keyword: love                                         5      │
│  2  Genre: Comedy, Years: 2006-2006                       3      │
└────────────────────────────────────────────────────────────────────┘
```

### Последние запросы

```text
  🕐 RECENT SEARCHES
┌────────────────────────────────────────────────────────────────────┐
│  #  Query                          Time                          │
├────────────────────────────────────────────────────────────────────┤
│  1  Keyword: love                  2026-04-01 20:20:11           │
│  2  Keyword: cat                   2026-04-01 20:18:05           │
└────────────────────────────────────────────────────────────────────┘
```

## Автор

Viktor Khomenko — финальный проект курса Python, группа 101025-ptm, апрель 2026.
