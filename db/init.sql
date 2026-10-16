-- =============================================================
-- Вариант 7. Электронная библиотека.
-- Каталог прочитанных книг + журнал поисковых запросов.
-- Файл автоматически выполняется PostgreSQL при первом старте
-- контейнера (монтируется в /docker-entrypoint-initdb.d/).
-- =============================================================

-- Таблица каталога прочитанных книг
CREATE TABLE IF NOT EXISTS books (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    author      VARCHAR(255) NOT NULL,
    isbn        VARCHAR(20),
    year        INTEGER,
    pages       INTEGER,
    rating      INTEGER CHECK (rating BETWEEN 1 AND 5),
    read_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Таблица журнала поисковых запросов к web-сервису
CREATE TABLE IF NOT EXISTS search_log (
    id          SERIAL PRIMARY KEY,
    query       VARCHAR(255) NOT NULL,
    search_type VARCHAR(20) NOT NULL DEFAULT 'author', -- author | isbn
    results_count INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Первичные (демонстрационные) данные каталога
INSERT INTO books (title, author, isbn, year, pages, rating, read_date) VALUES
    ('Мастер и Маргарита',        'Михаил Булгаков',      '9785389012345', 1967, 480, 5, '2024-01-15'),
    ('Преступление и наказание',  'Фёдор Достоевский',    '9785170853787', 1866, 608, 5, '2024-02-20'),
    ('1984',                      'Джордж Оруэлл',        '9780451524935', 1949, 328, 4, '2024-03-10'),
    ('Мёртвые души',              'Николай Гоголь',       '9785389048098', 1842, 384, 4, '2024-04-05'),
    ('Harry Potter and the Philosopher''s Stone',
                                  'J.K. Rowling',         '9780747532743', 1997, 352, 5, '2024-05-12'),
    ('The Lord of the Rings',     'J.R.R. Tolkien',       '9780007525546', 1954, 1178, 5, '2024-06-30');

-- Индекс для ускорения поиска по автору
CREATE INDEX IF NOT EXISTS idx_books_author ON books (author);
