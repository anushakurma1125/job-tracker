import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "jobs.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            applied_date TEXT,
            company TEXT,
            role TEXT,
            posted_on TEXT,
            job_description TEXT,
            link TEXT,
            status TEXT DEFAULT 'Applied',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def job_exists(link):
    conn = get_connection()
    row = conn.execute("SELECT id FROM jobs WHERE link = ?", (link,)).fetchone()
    conn.close()
    return row is not None


def add_job(data):
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO jobs (applied_date, company, role, posted_on, job_description, link, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.get("applied_date", datetime.now().strftime("%Y-%m-%d")),
            data.get("company", ""),
            data.get("role", ""),
            data.get("posted_on", ""),
            data.get("job_description", ""),
            data.get("link", ""),
            data.get("status", "Applied"),
        ),
    )
    conn.commit()
    job_id = cursor.lastrowid
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(job)


def get_jobs(status=None):
    conn = get_connection()
    if status:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_job(job_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_job(job_id, data):
    conn = get_connection()
    fields = []
    values = []
    for key in ("applied_date", "company", "role", "posted_on", "job_description", "link", "status"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        conn.close()
        return None
    fields.append("updated_at = ?")
    values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    values.append(job_id)
    conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(job) if job else None


def delete_job(job_id):
    conn = get_connection()
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
