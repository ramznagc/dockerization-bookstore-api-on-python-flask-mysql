import os
from flask import Flask, jsonify, request
import pymysql
from pymysql.cursors import DictCursor

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024


def get_connection():
    """Create a short-lived connection; credentials come only from environment."""
    return pymysql.connect(
        host=os.getenv("DB_HOST", "database"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.getenv("DB_NAME", "bookstore_db"),
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10,
    )


def serialize_book(row):
    if row is None:
        return None
    row["is_sold"] = bool(row["is_sold"])
    return row


def error(message, status):
    return jsonify({"error": message}), status


@app.get("/")
def home():
    return jsonify({"message": "Welcome to Callahan's Bookstore API Service"})


@app.get("/health")
def health():
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        return jsonify({"status": "ok", "database": "connected"}), 200
    except (pymysql.MySQLError, KeyError, ValueError):
        app.logger.exception("Database health check failed")
        return jsonify({"status": "error", "database": "unavailable"}), 503


@app.get("/books")
def get_books():
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT book_id, title, author, is_sold FROM books ORDER BY book_id"
                )
                books = [serialize_book(row) for row in cursor.fetchall()]
        return jsonify({"books": books})
    except pymysql.MySQLError:
        app.logger.exception("Could not retrieve books")
        return error("Database temporarily unavailable", 503)


@app.get("/books/<int:book_id>")
def get_book(book_id):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT book_id, title, author, is_sold FROM books WHERE book_id = %s",
                    (book_id,),
                )
                book = serialize_book(cursor.fetchone())
        return (jsonify({"book": book}), 200) if book else error("Book not found", 404)
    except pymysql.MySQLError:
        app.logger.exception("Could not retrieve book")
        return error("Database temporarily unavailable", 503)


@app.post("/books")
def add_book():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("Request body must be a JSON object", 400)
    title = payload.get("title")
    author = payload.get("author", "")
    if not isinstance(title, str) or not title.strip():
        return error("'title' is required and must be a non-empty string", 400)
    if not isinstance(author, str):
        return error("'author' must be a string", 400)
    if len(title.strip()) > 100 or len(author) > 100:
        return error("title and author must be at most 100 characters", 400)

    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO books (title, author, is_sold) VALUES (%s, %s, %s)",
                    (title.strip(), author.strip(), False),
                )
                book_id = cursor.lastrowid
                cursor.execute(
                    "SELECT book_id, title, author, is_sold FROM books WHERE book_id = %s",
                    (book_id,),
                )
                book = serialize_book(cursor.fetchone())
        return jsonify({"book": book}), 201
    except pymysql.MySQLError:
        app.logger.exception("Could not create book")
        return error("Database temporarily unavailable", 503)


@app.put("/books/<int:book_id>")
def update_book(book_id):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("Request body must be a JSON object", 400)
    allowed = {"title", "author", "is_sold"}
    if not payload or not set(payload).issubset(allowed):
        return error("Provide one or more valid fields: title, author, is_sold", 400)

    if "title" in payload and (
        not isinstance(payload["title"], str)
        or not payload["title"].strip()
        or len(payload["title"].strip()) > 100
    ):
        return error("'title' must be a non-empty string of at most 100 characters", 400)
    if "author" in payload and (
        not isinstance(payload["author"], str) or len(payload["author"]) > 100
    ):
        return error("'author' must be a string of at most 100 characters", 400)
    if "is_sold" in payload and not isinstance(payload["is_sold"], bool):
        return error("'is_sold' must be a JSON boolean", 400)

    fields, values = [], []
    for field in ("title", "author", "is_sold"):
        if field in payload:
            value = payload[field]
            fields.append(f"{field} = %s")
            values.append(value.strip() if isinstance(value, str) else value)
    values.append(book_id)

    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE books SET {', '.join(fields)} WHERE book_id = %s", values
                )
                if cursor.rowcount == 0:
                    cursor.execute("SELECT book_id FROM books WHERE book_id = %s", (book_id,))
                    if cursor.fetchone() is None:
                        return error("Book not found", 404)
                cursor.execute(
                    "SELECT book_id, title, author, is_sold FROM books WHERE book_id = %s",
                    (book_id,),
                )
                book = serialize_book(cursor.fetchone())
        return jsonify({"book": book})
    except pymysql.MySQLError:
        app.logger.exception("Could not update book")
        return error("Database temporarily unavailable", 503)


@app.delete("/books/<int:book_id>")
def delete_book(book_id):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM books WHERE book_id = %s", (book_id,))
                if cursor.rowcount == 0:
                    return error("Book not found", 404)
        return jsonify({"message": "Book deleted", "book_id": book_id}), 200
    except pymysql.MySQLError:
        app.logger.exception("Could not delete book")
        return error("Database temporarily unavailable", 503)


@app.errorhandler(404)
def not_found(_error):
    return error("Not found", 404)


@app.errorhandler(405)
def method_not_allowed(_error):
    return error("Method not allowed", 405)


@app.errorhandler(413)
def payload_too_large(_error):
    return error("Request body is too large", 413)


@app.errorhandler(500)
def internal_error(_error):
    return error("Internal server error", 500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
