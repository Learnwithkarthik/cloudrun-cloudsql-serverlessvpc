import os
import time

import pymysql
from flask import Flask, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)


def get_connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        port=int(os.environ.get("DB_PORT", "3306")),
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def initialize_database():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS students (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(150) NOT NULL,
                    course VARCHAR(100) NOT NULL,
                    phone VARCHAR(20),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
    finally:
        connection.close()


def initialize_with_retry():
    attempts = 5

    for attempt in range(1, attempts + 1):
        try:
            initialize_database()
            app.logger.info("Database table initialized")
            return
        except Exception as error:
            app.logger.warning(
                "Database initialization attempt %s failed: %s",
                attempt,
                error,
            )

            if attempt < attempts:
                time.sleep(2)


@app.route("/")
def home():
    students = []
    database_status = "Connected"
    database_error = None
    connection = None

    try:
        initialize_database()
        connection = get_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, email, course, phone, created_at
                FROM students
                ORDER BY id DESC
                """
            )

            students = cursor.fetchall()

    except Exception as error:
        app.logger.exception("Unable to load students")
        database_status = "Connection failed"
        database_error = str(error)

    finally:
        if connection:
            connection.close()

    return render_template(
        "index.html",
        students=students,
        database_status=database_status,
        database_error=database_error,
    )


@app.route("/register", methods=["POST"])
def register():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    course = request.form.get("course", "").strip()
    phone = request.form.get("phone", "").strip()

    if not name or not email or not course:
        return "Name, email and course are required", 400

    connection = None

    try:
        initialize_database()
        connection = get_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO students (name, email, course, phone)
                VALUES (%s, %s, %s, %s)
                """,
                (name, email, course, phone),
            )

        return redirect(url_for("home"))

    except Exception as error:
        app.logger.exception("Student registration failed")
        return f"Registration failed: {error}", 500

    finally:
        if connection:
            connection.close()


@app.route("/delete/<int:student_id>", methods=["POST"])
def delete_student(student_id):
    connection = None

    try:
        connection = get_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM students WHERE id = %s",
                (student_id,),
            )

        return redirect(url_for("home"))

    except Exception as error:
        app.logger.exception("Student deletion failed")
        return f"Deletion failed: {error}", 500

    finally:
        if connection:
            connection.close()


@app.route("/health")
def health():
    connection = None

    try:
        connection = get_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    DATABASE() AS database_name,
                    NOW() AS database_time,
                    COUNT(*) AS student_count
                FROM students
                """
            )

            result = cursor.fetchone()

        return jsonify(
            {
                "application": "healthy",
                "cloud_run": "working",
                "cloud_sql": "connected",
                "network_path": "Serverless VPC Access Connector",
                "details": result,
            }
        )

    except Exception as error:
        app.logger.exception("Health check failed")

        return (
            jsonify(
                {
                    "application": "running",
                    "cloud_sql": "connection failed",
                    "error": str(error),
                }
            ),
            500,
        )

    finally:
        if connection:
            connection.close()


initialize_with_retry()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        debug=False,
    )
