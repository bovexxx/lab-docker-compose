"""
Web-сервис (микросервис-эмулятор предметной области).
Вариант 7 — Электронная библиотека.

Предоставляет упрощённый REST-интерфейс поверх публичного API
Open Library (https://openlibrary.org/developers/api):

  GET /search?q=<автор или название>  — поиск книг;
  GET /book/<isbn>                    — карточка книги по ISBN;
  GET /health                         — проверка работоспособности.
"""

import os
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException

OPENLIBRARY_BASE = os.environ.get("OPENLIBRARY_BASE", "https://openlibrary.org").rstrip("/")

app = FastAPI(title="Web-сервис — поиск книг (Open Library, вариант 7)")

TIMEOUT = 20.0


@app.get("/health")
def health():
    return {"status": "ok", "provider": OPENLIBRARY_BASE}


@app.get("/search")
def search(q: str, limit: int = 12):
    """
    Поиск книг по автору или названию через Open Library Search API.
    Возвращает упрощённый список: заголовок, авторы, год, ISBN, обложка.
    """
    if not q.strip():
        raise HTTPException(status_code=422, detail="Параметр q обязателен")

    url = f"{OPENLIBRARY_BASE}/search.json"
    params = {
        "q": q.strip(),
        "limit": max(1, min(limit, 30)),
        "fields": "title,author_name,first_publish_year,isbn,cover_i",
    }

    try:
        response = httpx.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Open Library вернул ошибку: {exc.response.status_code}")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось обратиться к Open Library: {exc}")

    results = []
    for doc in payload.get("docs", []):
        title = doc.get("title")
        if not title:
            continue
        authors = doc.get("author_name", [])
        isbns = doc.get("isbn", [])
        cover_id = doc.get("cover_i")
        results.append(
            {
                "title": title,
                "authors": authors,
                "author": authors[0] if authors else "Неизвестный автор",
                "year": doc.get("first_publish_year"),
                "isbn": isbns[0] if isbns else None,
                # обложка: подгружается с covers.openlibrary.org по идентификатору
                "cover_url": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else None,
            }
        )

    return {"count": len(results), "results": results}


@app.get("/book/{isbn}")
def book(isbn: str):
    """
    Получение карточки книги по ISBN через Open Library Books API.
    Возвращает: заголовок, авторов, год издания, число страниц, обложку.
    """
    isbn = isbn.strip().replace("-", "")
    if not isbn.isdigit() or not (10 <= len(isbn) <= 13):
        raise HTTPException(status_code=422, detail="Некорректный ISBN")

    url = f"{OPENLIBRARY_BASE}/api/books"
    params = {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"}

    try:
        response = httpx.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Open Library вернул ошибку: {exc.response.status_code}")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось обратиться к Open Library: {exc}")

    record = payload.get(f"ISBN:{isbn}")
    if not record:
        raise HTTPException(status_code=404, detail="Книга с таким ISBN не найдена")

    authors = [a.get("name") for a in record.get("authors", []) if a.get("name")]
    cover = record.get("cover") or {}
    publish_date = record.get("publish_date", "")
    year = None
    for token in publish_date.replace(",", " ").split():
        if token.isdigit() and len(token) == 4:
            year = int(token)
            break

    return {
        "title": record.get("title"),
        "subtitle": record.get("subtitle"),
        "authors": authors,
        "author": authors[0] if authors else "Неизвестный автор",
        "year": year,
        "pages": record.get("number_of_pages"),
        "isbn": isbn,
        "cover_url": cover.get("medium") or cover.get("small"),
        "url": (record.get("url") or {}).get("#value") if isinstance(record.get("url"), dict) else record.get("url"),
    }
