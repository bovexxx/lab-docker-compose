"""
Backend-сервис (REST API) лабораторной работы.
Вариант 7 — Электронная библиотека.

Задачи сервиса:
  * CRUD-операции с каталогом прочитанных книг в PostgreSQL;
  * интеграция с Web-сервисом (локальный микросервис-обёртка над
    Open Library API) для поиска книг по автору и по ISBN;
  * журналирование поисковых запросов в БД.
"""

import os
from datetime import date
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import psycopg

# ------------------------------------------------------------------
# Конфигурация (переменные окружения задаются в docker-compose.yml)
# ------------------------------------------------------------------
DB_HOST = os.environ.get("DB_HOST", "db")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "library_db")
DB_USER = os.environ.get("DB_USER", "library")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "library_password")

WEBSERVICE_URL = os.environ.get("WEBSERVICE_URL", "http://web-service:8001").rstrip("/")

app = FastAPI(title="Backend — Электронная библиотека (вариант 7)")

# Разрешаем CORS, чтобы фронтенд мог обращаться напрямую (например, при отладке)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Модели данных
# ------------------------------------------------------------------
class Book(BaseModel):
    id: int
    title: str
    author: str
    isbn: Optional[str] = None
    year: Optional[int] = None
    pages: Optional[int] = None
    rating: Optional[int] = None
    read_date: date


class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    author: str = Field(..., min_length=1, max_length=255)
    isbn: Optional[str] = Field(None, max_length=20)
    year: Optional[int] = None
    pages: Optional[int] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    read_date: Optional[date] = None


# ------------------------------------------------------------------
# Работа с базой данных
# ------------------------------------------------------------------
def get_connection():
    """Открывает соединение с PostgreSQL."""
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=5,
    )


def row_to_book(row) -> dict:
    return {
        "id": row[0],
        "title": row[1],
        "author": row[2],
        "isbn": row[3],
        "year": row[4],
        "pages": row[5],
        "rating": row[6],
        "read_date": row[7].isoformat() if row[7] else None,
    }


# ------------------------------------------------------------------
# Эндпоинты
# ------------------------------------------------------------------
@app.get("/health")
def health():
    """Проверка работоспособности сервиса (используется в healthcheck)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok", "db": "ok" if db_ok else "unavailable"}


@app.get("/api/books", response_model=list[Book])
def list_books(search: Optional[str] = None):
    """
    Кнопка 1 фронтенда: каталог прочитанных книг из внутренней БД.
    Параметр search — необязательный поиск по названию или автору.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if search:
                    like = f"%{search}%"
                    cur.execute(
                        """
                        SELECT id, title, author, isbn, year, pages, rating, read_date
                        FROM books
                        WHERE title ILIKE %s OR author ILIKE %s
                        ORDER BY read_date DESC, id DESC
                        """,
                        (like, like),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, title, author, isbn, year, pages, rating, read_date
                        FROM books
                        ORDER BY read_date DESC, id DESC
                        """
                    )
                rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Ошибка подключения к БД: {exc}")
    return [row_to_book(r) for r in rows]


@app.post("/api/books", response_model=Book, status_code=201)
def add_book(book: BookCreate):
    """Добавление книги в каталог прочитанных (из результатов поиска)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO books (title, author, isbn, year, pages, rating, read_date)
                    VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s, CURRENT_DATE))
                    RETURNING id, title, author, isbn, year, pages, rating, read_date
                    """,
                    (
                        book.title,
                        book.author,
                        book.isbn,
                        book.year,
                        book.pages,
                        book.rating,
                        book.read_date,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Ошибка записи в БД: {exc}")
    return row_to_book(row)


@app.delete("/api/books/{book_id}", status_code=204)
def delete_book(book_id: int):
    """Удаление книги из каталога."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM books WHERE id = %s RETURNING id", (book_id,))
                deleted = cur.fetchone()
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Ошибка удаления из БД: {exc}")
    if deleted is None:
        raise HTTPException(status_code=404, detail="Книга не найдена")


@app.put("/api/books/{book_id}/rating", response_model=Book)
def rate_book(book_id: int, rating: int):
    """Проставление оценки прочитанной книге (1–5)."""
    if not 1 <= rating <= 5:
        raise HTTPException(status_code=422, detail="Оценка должна быть от 1 до 5")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE books SET rating = %s
                    WHERE id = %s
                    RETURNING id, title, author, isbn, year, pages, rating, read_date
                    """,
                    (rating, book_id),
                )
                row = cur.fetchone()
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Ошибка обновления в БД: {exc}")
    if row is None:
        raise HTTPException(status_code=404, detail="Книга не найдена")
    return row_to_book(row)


@app.get("/api/stats")
def stats():
    """Сводная статистика библиотеки."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*), COALESCE(SUM(pages), 0), ROUND(AVG(rating), 2) FROM books")
                total, pages, avg_rating = cur.fetchone()
                cur.execute("SELECT COUNT(*) FROM search_log")
                searches = cur.fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Ошибка подключения к БД: {exc}")
    return {
        "total_books": total,
        "total_pages": int(pages),
        "avg_rating": float(avg_rating) if avg_rating is not None else None,
        "total_searches": searches,
    }


# ------------------------------------------------------------------
# Интеграция с Web-сервисом (Open Library через локальный микросервис)
# ------------------------------------------------------------------
@app.get("/api/search")
def search_books(q: str, search_type: str = "author"):
    """
    Кнопка 2 фронтенда: поиск книг у Web-сервиса.
    search_type = 'author' — поиск по автору/названию;
    search_type = 'isbn'   — поиск по ISBN.
    Результат журнализируется в таблицу search_log.
    """
    if not q.strip():
        raise HTTPException(status_code=422, detail="Поисковый запрос не может быть пустым")

    params = {"q": q.strip()}
    if search_type == "isbn":
        path = f"/book/{q.strip()}"
        params = None
    elif search_type == "author":
        path = "/search"
    else:
        raise HTTPException(status_code=422, detail="search_type должен быть 'author' или 'isbn'")

    try:
        response = httpx.get(f"{WEBSERVICE_URL}{path}", params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Web-сервис недоступен: {exc}")

    # Web-сервис возвращает список для /search и одну карточку для /book/{isbn}
    if search_type == "isbn":
        results = [payload] if payload.get("title") else []
    else:
        results = payload.get("results", [])
    count = len(results)

    # журналируем запрос в БД (не критично, если запись не удалась)
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO search_log (query, search_type, results_count) VALUES (%s, %s, %s)",
                    (q.strip(), search_type, count),
                )
            conn.commit()
    except Exception:  # noqa: BLE001
        pass

    return {"query": q.strip(), "search_type": search_type, "count": count, "results": results}
