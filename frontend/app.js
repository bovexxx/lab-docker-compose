/**
 * Frontend — Электронная библиотека (вариант 7).
 *
 * Кнопка 1: запрос каталога прочитанных книг из внутренней БД через Backend.
 * Кнопка 2: поиск книг по автору/названию или ISBN через
 *           Backend -> Web-сервис -> Open Library API.
 */

const API = "/api"; // nginx проксирует /api/ на backend:8000

// ---------------------------------------------------------------------------
// Утилиты: HTTP, форматирование, уведомления
// ---------------------------------------------------------------------------

async function apiGet(path) {
    const response = await fetch(`${API}${path}`);
    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${response.status}`);
    }
    return response.json();
}

async function apiSend(path, method, body) {
    const response = await fetch(`${API}${path}`, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok && response.status !== 204) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${response.status}`);
    }
    return response.status === 204 ? null : response.json();
}

function setStatus(elementId, message, kind = "") {
    const el = document.getElementById(elementId);
    el.textContent = message;
    el.className = `status ${kind}`.trim();
}

/** Всплывающее уведомление. */
function toast(message, kind = "info", timeout = 3500) {
    const box = document.getElementById("toasts");
    const el = document.createElement("div");
    el.className = `toast ${kind}`;
    const icons = { success: "✅", error: "⚠️", info: "ℹ️" };
    el.innerHTML = `<span>${icons[kind] || icons.info}</span><span class="toast-text"></span>
        <button class="toast-close" aria-label="Закрыть">×</button>`;
    el.querySelector(".toast-text").textContent = message;
    const remove = () => {
        el.classList.add("leaving");
        setTimeout(() => el.remove(), 250);
    };
    el.querySelector(".toast-close").addEventListener("click", remove);
    box.appendChild(el);
    setTimeout(remove, timeout);
}

/** Отображение оценки в виде звёзд: ★★★☆☆ */
function starsHtml(rating) {
    if (!rating) return "";
    const full = "★".repeat(rating);
    const empty = "☆".repeat(5 - rating);
    return `${full}<span class="empty">${empty}</span>`;
}

function showEmpty(container, message, icon = "📭") {
    const div = document.createElement("div");
    div.className = "empty-message";
    div.innerHTML = `<span class="big">${icon}</span>`;
    div.append(document.createTextNode(message));
    container.appendChild(div);
}

/** Скелетоны загрузки вместо пустого пространства. */
function showSkeletons(container, count = 4) {
    const tpl = document.getElementById("skeleton-template");
    container.innerHTML = "";
    for (let i = 0; i < count; i++) {
        container.appendChild(tpl.content.firstElementChild.cloneNode(true));
    }
}

// ---------------------------------------------------------------------------
// Карточка книги
// ---------------------------------------------------------------------------

function createBookCard({ title, author, meta, coverUrl, rating, actions = [] }) {
    const tpl = document.getElementById("book-card-template");
    const card = tpl.content.firstElementChild.cloneNode(true);

    const coverBox = card.querySelector(".cover");
    if (coverUrl) {
        const img = card.querySelector("img");
        img.src = coverUrl;
        img.alt = `Обложка: ${title}`;
        img.onerror = () => img.remove(); // остаётся заглушка 📖
    } else {
        card.querySelector("img").remove();
    }

    card.querySelector(".title").textContent = title;
    card.querySelector(".author").textContent = author || "Автор не указан";
    card.querySelector(".stars").innerHTML = starsHtml(rating);
    card.querySelector(".meta").textContent = meta || "";

    const actionsBox = card.querySelector(".actions");
    for (const { label, className, onClick } of actions) {
        const btn = document.createElement("button");
        btn.className = `btn ${className}`;
        btn.textContent = label;
        btn.addEventListener("click", onClick);
        actionsBox.appendChild(btn);
    }
    return card;
}

// ---------------------------------------------------------------------------
// Кнопка 1 — каталог прочитанных книг (Backend -> PostgreSQL)
// ---------------------------------------------------------------------------

async function loadBooks({ silent = false } = {}) {
    const container = document.getElementById("books-container");
    const btn = document.getElementById("btn-load-books");
    const filter = document.getElementById("catalog-filter").value.trim();

    btn.disabled = true;
    if (!silent) showSkeletons(container, 4);

    try {
        const query = filter ? `?search=${encodeURIComponent(filter)}` : "";
        const books = await apiGet(`/books${query}`);

        container.innerHTML = "";
        if (books.length === 0) {
            showEmpty(
                container,
                filter
                    ? "Ничего не найдено по вашему фильтру."
                    : "Каталог пуст. Найдите книгу и добавьте её кнопкой «В прочитанное».",
                "🔖"
            );
        } else {
            for (const book of books) {
                const metaParts = [];
                if (book.isbn) metaParts.push(`ISBN ${book.isbn}`);
                if (book.year) metaParts.push(book.year);
                if (book.pages) metaParts.push(`${book.pages} стр.`);
                if (book.read_date) metaParts.push(`прочитано ${formatDate(book.read_date)}`);

                container.appendChild(createBookCard({
                    title: book.title,
                    author: book.author,
                    meta: metaParts.join(" · "),
                    rating: book.rating,
                    actions: [
                        {
                            label: "⭐ Оценить",
                            className: "btn-ghost",
                            onClick: () => rateBook(book.id),
                        },
                        {
                            label: "✕ Удалить",
                            className: "btn-danger",
                            onClick: () => deleteBook(book.id),
                        },
                    ],
                }));
            }
        }
    } catch (error) {
        container.innerHTML = "";
        showEmpty(container, `Ошибка загрузки каталога: ${error.message}`, "⚠️");
        toast(`Не удалось загрузить каталог: ${error.message}`, "error");
    } finally {
        btn.disabled = false;
        loadStats();
    }
}

function formatDate(iso) {
    if (!iso) return "";
    try {
        return new Date(iso).toLocaleDateString("ru-RU", {
            day: "numeric", month: "short", year: "numeric",
        });
    } catch {
        return iso;
    }
}

async function deleteBook(id) {
    if (!confirm("Удалить книгу из каталога?")) return;
    try {
        await apiSend(`/books/${id}`, "DELETE");
        toast("Книга удалена из каталога", "success");
        loadBooks({ silent: true });
    } catch (error) {
        toast(`Не удалось удалить: ${error.message}`, "error");
    }
}

async function rateBook(id) {
    const value = prompt("Оценка книги (1–5):", "5");
    if (value === null) return;
    const rating = Number(value);
    if (!Number.isInteger(rating) || rating < 1 || rating > 5) {
        toast("Введите целое число от 1 до 5", "error");
        return;
    }
    try {
        await apiSend(`/books/${id}/rating?rating=${rating}`, "PUT");
        toast(`Оценка ${rating}/5 сохранена`, "success");
        loadBooks({ silent: true });
    } catch (error) {
        toast(`Не удалось оценить: ${error.message}`, "error");
    }
}

// ---------------------------------------------------------------------------
// Кнопка 2 — поиск книг (Backend -> Web-сервис -> Open Library)
// ---------------------------------------------------------------------------

async function searchBooks() {
    const query = document.getElementById("search-query").value.trim();
    const searchType = document.getElementById("search-type").value;
    const container = document.getElementById("search-results");
    const btn = document.getElementById("btn-search");

    if (!query) {
        setStatus("search-status", "Введите поисковый запрос.", "error");
        document.getElementById("search-query").focus();
        return;
    }

    if (searchType === "isbn" && !/^\d[\d\-Xx]{9,16}$/.test(query)) {
        setStatus("search-status", "Похоже, это не ISBN. Пример: 9780451524935", "error");
        return;
    }

    btn.disabled = true;
    setStatus("search-status", "⏳ Запрос к Web-сервису (Open Library)…");
    showSkeletons(container, 4);

    try {
        const data = await apiGet(
            `/search?q=${encodeURIComponent(query)}&search_type=${encodeURIComponent(searchType)}`
        );

        container.innerHTML = "";
        if (data.results.length === 0) {
            showEmpty(container, "Ничего не найдено. Попробуйте изменить запрос.", "🔎");
            setStatus("search-status", "Ничего не найдено.", "error");
        } else {
            for (const item of data.results) {
                const metaParts = [];
                if (item.year) metaParts.push(item.year);
                if (item.isbn) metaParts.push(`ISBN ${item.isbn}`);
                if (item.pages) metaParts.push(`${item.pages} стр.`);

                container.appendChild(createBookCard({
                    title: item.title,
                    author: item.author,
                    meta: metaParts.join(" · "),
                    coverUrl: item.cover_url,
                    actions: [{
                        label: "➕ В прочитанное",
                        className: "btn-small",
                        onClick: () => addToCatalog(item),
                    }],
                }));
            }
            setStatus("search-status", `✅ Найдено книг: ${data.count}`, "success");
        }
    } catch (error) {
        container.innerHTML = "";
        showEmpty(container, `Ошибка поиска: ${error.message}`, "⚠️");
        setStatus("search-status", `Ошибка: ${error.message}`, "error");
    } finally {
        btn.disabled = false;
        loadStats();
    }
}

/** Сохранение найденной книги в каталог прочитанных (через Backend в БД). */
async function addToCatalog(item) {
    try {
        await apiSend("/books", "POST", {
            title: item.title,
            author: item.author,
            isbn: item.isbn || null,
            year: item.year || null,
            pages: item.pages || null,
            read_date: new Date().toISOString().slice(0, 10),
        });
        toast(`«${item.title}» добавлена в каталог`, "success");
        loadBooks({ silent: true });
    } catch (error) {
        toast(`Не удалось добавить: ${error.message}`, "error");
    }
}

// ---------------------------------------------------------------------------
// Статистика библиотеки
// ---------------------------------------------------------------------------

async function loadStats() {
    try {
        const stats = await apiGet("/stats");
        document.getElementById("stats").classList.remove("hidden");
        document.getElementById("stat-books").textContent = stats.total_books;
        document.getElementById("stat-pages").textContent =
            Number(stats.total_pages).toLocaleString("ru-RU");
        document.getElementById("stat-rating").textContent =
            stats.avg_rating !== null ? `★ ${stats.avg_rating}` : "—";
        document.getElementById("stat-searches").textContent = stats.total_searches;
    } catch {
        // статистика — не критичная часть, молча игнорируем ошибку
    }
}

// ---------------------------------------------------------------------------
// Инициализация
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.getElementById("search-query");
    const searchTypeEl = document.getElementById("search-type");

    document.getElementById("btn-load-books").addEventListener("click", () => loadBooks());
    document.getElementById("btn-search").addEventListener("click", searchBooks);

    // Подсказки-чипы: заполняют поле и сразу выполняют поиск
    document.querySelectorAll(".chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            searchInput.value = chip.dataset.query;
            searchTypeEl.value = chip.dataset.type;
            searchBooks();
        });
    });

    // Enter в полях ввода
    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") searchBooks();
    });
    document.getElementById("catalog-filter").addEventListener("keydown", (e) => {
        if (e.key === "Enter") loadBooks();
    });

    // Фильтр каталога при очистке поля — сброс к полному списку
    document.getElementById("catalog-filter").addEventListener("change", (e) => {
        if (!e.target.value.trim()) loadBooks({ silent: true });
    });

    // Первичная загрузка каталога и статистики
    loadBooks();
});
