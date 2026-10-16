# Электронная библиотека — Вариант 7

Лабораторная работа: **«Контейнеризация многокомпонентных приложений с помощью Docker Compose»**.

**Вариант 7 — Электронная библиотека.**
Web-сервис: поиск книг по автору или ISBN (**Open Library API**).
Данные для БД: каталог прочитанных книг.

---

## Архитектура

Приложение состоит из **4 независимых компонентов (контейнеров)**, объединённых в виртуальную сеть Docker Compose (bridge):

| Сервис | Технологии | Назначение |
|---|---|---|
| **frontend** | HTML/CSS/JS + nginx | Веб-интерфейс с двумя функциональными кнопками, проброс порта `8081:80` |
| **backend** | Python 3.12 + FastAPI + psycopg + httpx | REST API: CRUD каталога в PostgreSQL, вызов Web-сервиса, журналирование запросов |
| **db** | PostgreSQL 16 | Хранит каталог прочитанных книг и журнал поисковых запросов; инициализируется `db/init.sql`; данные сохраняются в named volume `pgdata` |
| **web-service** | Python 3.12 + FastAPI + httpx | Локальный микросервис-эмулятор предметной области: упрощённая обёртка над публичным API **Open Library** |

```
Браузер ──:8081──▶ frontend (nginx) ──/api/*──▶ backend ──▶ db (PostgreSQL, 5432)
                                            │
                                            └──▶ web-service ──▶ Open Library API (openlibrary.org)
```

### Две функциональные кнопки фронтенда

1. **«Показать каталог»** — запрос каталога прочитанных книг из внутренней БД через Backend (GET `/api/books`).
   Доступны фильтр по названию/автору, удаление книги и оценка (1–5).
2. **«Найти»** — поиск книг по автору/названию или по ISBN через Backend → Web-сервис → Open Library API
   (GET `/api/search`). У каждой найденной книги есть кнопка **«В прочитанное»**,
   сохраняющая её в каталог БД.

Результаты отображаются в виде карточек с обложками. Дополнительно выводится статистика библиотеки
(число прочитанных книг, суммарное число страниц, средняя оценка, число поисковых запросов).

### Интерфейс

* тёмная «библиотечная» шапка со схемой взаимодействия сервисов (`frontend → backend → db + web-service → Open Library`);
* скелетоны-заглушки при загрузке данных, всплывающие уведомления об успехе/ошибке;
* звёзды-оценки (★) для прочитанных книг, фильтр каталога, чипы-подсказки для быстрого поиска;
* полностью адаптивная вёрстка (телефон/планшет/ПК), поддержка `prefers-reduced-motion`.

---

## Структура проекта

```
.
├── docker-compose.yml        # описание всех 4 сервисов, сети, томов, healthcheck
├── .env.example              # пример переменных окружения (скопируйте в .env)
├── .gitignore
├── README.md
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf            # статика + проксирование /api/ → backend:8000
│   ├── index.html
│   ├── style.css
│   └── app.js
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py               # REST API + работа с БД + вызов web-service
├── db/
│   └── init.sql              # схема БД + первичные данные (выполняется при первом старте)
└── web-service/
    ├── Dockerfile
    ├── requirements.txt
    └── service.py            # микросервис-обёртка над Open Library API
```

---

## API

### Backend (`http://localhost:8081/api/...` через nginx)

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/books?search=...` | Каталог прочитанных книг (с опциональным фильтром) |
| POST | `/api/books` | Добавить книгу в каталог |
| DELETE | `/api/books/{id}` | Удалить книгу из каталога |
| PUT | `/api/books/{id}/rating?rating=5` | Оценить книгу (1–5) |
| GET | `/api/search?q=...&search_type=author\|isbn` | Поиск книг через Web-сервис |
| GET | `/api/stats` | Статистика библиотеки |
| GET | `/health` | Проверка работоспособности |

### Web-сервис (внутренний, порт 8001)

| Метод | Путь | Описание |
|---|---|---|
| GET | `/search?q=...` | Поиск книг по автору/названию (Open Library Search API) |
| GET | `/book/{isbn}` | Карточка книги по ISBN (Open Library Books API) |
| GET | `/health` | Проверка работоспособности |

Источник данных — публичный API Open Library: <https://openlibrary.org/developers/api>.

---

## Запуск

Требования: установленный [Docker](https://docs.docker.com/get-docker/) с плагином Compose.

```bash
# 1. (необязательно) задайте свои параметры БД
cp .env.example .env

# 2. сборка и запуск всех 4 контейнеров
docker compose up --build

# или в фоновом режиме
docker compose up -d --build
```

После запуска откройте в браузере: **http://localhost:8081**


Проверка:

```bash
docker compose ps          # все сервисы healthy
curl http://localhost:8081/api/books      # каталог из БД
curl "http://localhost:8081/api/search?q=Tolkien&search_type=author"  # поиск через web-service
```

Остановка:

```bash
docker compose down          # данные БД сохраняются в volume pgdata
docker compose down -v       # удалить и volume с данными тоже
```

---

## Особенности реализации

- **Порядок запуска**: `depends_on` с `condition: service_healthy` — Backend стартует только после готовности PostgreSQL (healthcheck `pg_isready`) и Web-сервиса.
- **Сохранность данных**: каталог БД лежит в named volume `pgdata` и переживает перезапуски контейнеров.
- **Первичные данные**: `db/init.sql` автоматически создаёт таблицы `books` и `search_log` и наполняет каталог демонстрационными книгами.
- **Переменные окружения**: параметры подключения и адрес Web-сервиса задаются в `docker-compose.yml` через `.env`.
- **Устойчивость**: таймауты и понятные сообщения об ошибках при недоступности Open Library или БД.
