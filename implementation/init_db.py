from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
DROP VIEW IF EXISTS student_scores;
DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS students;

CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cohort TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    age INTEGER NOT NULL CHECK (age >= 16)
);

CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    credit INTEGER NOT NULL CHECK (credit > 0)
);

CREATE TABLE enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 100),
    semester TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

CREATE VIEW student_scores AS
SELECT
    enrollments.id AS enrollment_id,
    students.id AS student_id,
    students.name AS student_name,
    students.cohort AS cohort,
    courses.code AS course_code,
    courses.title AS course_title,
    enrollments.score AS score,
    enrollments.semester AS semester
FROM enrollments
JOIN students ON students.id = enrollments.student_id
JOIN courses ON courses.id = enrollments.course_id;
"""


SEED_SQL = """
INSERT INTO students (name, cohort, email, age) VALUES
('An Nguyen', 'A1', 'an.nguyen@example.com', 20),
('Binh Tran', 'A1', 'binh.tran@example.com', 21),
('Chi Le', 'B2', 'chi.le@example.com', 19),
('Dung Pham', 'B2', 'dung.pham@example.com', 22);

INSERT INTO courses (code, title, credit) VALUES
('PY101', 'Python Foundations', 3),
('DB201', 'Database Systems', 4),
('AI301', 'Applied AI', 3);

INSERT INTO enrollments (student_id, course_id, score, semester) VALUES
(1, 1, 88.5, '2026-S1'),
(1, 2, 91.0, '2026-S1'),
(2, 1, 75.0, '2026-S1'),
(2, 3, 84.0, '2026-S2'),
(3, 2, 93.0, '2026-S1'),
(3, 3, 95.0, '2026-S2'),
(4, 1, 68.0, '2026-S1'),
(4, 2, 72.5, '2026-S2');
"""


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "lab.db"


def create_database(db_path: str | Path = DEFAULT_DB_PATH) -> Path:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()
    return path


if __name__ == "__main__":
    created = create_database()
    print(f"Database initialized at {created}")
