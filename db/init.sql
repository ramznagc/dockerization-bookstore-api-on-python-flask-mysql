CREATE TABLE IF NOT EXISTS books (
    book_id INT NOT NULL AUTO_INCREMENT,
    title VARCHAR(100) NOT NULL,
    author VARCHAR(100) NOT NULL DEFAULT '',
    is_sold BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (book_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO books (title, author, is_sold)
SELECT 'Where the Crawdads Sing', 'Delia Owens', TRUE
WHERE NOT EXISTS (SELECT 1 FROM books WHERE title = 'Where the Crawdads Sing');

INSERT INTO books (title, author, is_sold)
SELECT 'The Vanishing Half: A Novel', 'Brit Bennett', FALSE
WHERE NOT EXISTS (SELECT 1 FROM books WHERE title = 'The Vanishing Half: A Novel');

INSERT INTO books (title, author, is_sold)
SELECT '1st Case', 'James Patterson, Chris Tebbetts', FALSE
WHERE NOT EXISTS (SELECT 1 FROM books WHERE title = '1st Case');
