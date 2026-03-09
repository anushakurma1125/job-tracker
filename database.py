import os
import sqlite3
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL")

# Use PostgreSQL on Render, SQLite locally
USE_POSTGRES = DATABASE_URL is not None


def get_connection():
    if USE_POSTGRES:
        import psycopg2
        import psycopg2.extras
        # Render provides postgres:// but psycopg2 needs postgresql://
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url)
        conn.autocommit = False
        return conn
    else:
        db_path = os.path.join(os.path.dirname(__file__), "jobs.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn


def _ph(n=1):
    """Return placeholder(s) for the current database engine."""
    p = "%s" if USE_POSTGRES else "?"
    return ", ".join([p] * n) if n > 1 else p


def _fetchone(cursor, conn):
    """Fetch one row and return as a dict."""
    if USE_POSTGRES:
        if cursor.description is None:
            return None
        cols = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        return dict(zip(cols, row)) if row else None
    else:
        row = cursor.fetchone()
        return dict(row) if row else None


def _fetchall(cursor, conn):
    """Fetch all rows and return as list of dicts."""
    if USE_POSTGRES:
        if cursor.description is None:
            return []
        cols = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]
    else:
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    if USE_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                applied_date TEXT,
                company TEXT,
                role TEXT,
                posted_on TEXT,
                job_description TEXT,
                link TEXT,
                status TEXT DEFAULT 'Applied',
                comment TEXT DEFAULT '',
                visa_answer TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Migrate: add columns if missing
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs'")
        existing_cols = {row[0] for row in cur.fetchall()}
        if "comment" not in existing_cols:
            cur.execute("ALTER TABLE jobs ADD COLUMN comment TEXT DEFAULT ''")
            conn.commit()
        if "visa_answer" not in existing_cols:
            cur.execute("ALTER TABLE jobs ADD COLUMN visa_answer TEXT DEFAULT ''")
            conn.commit()
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                applied_date TEXT,
                company TEXT,
                role TEXT,
                posted_on TEXT,
                job_description TEXT,
                link TEXT,
                status TEXT DEFAULT 'Applied',
                comment TEXT DEFAULT '',
                visa_answer TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Migrate: add columns if missing
        cur.execute("PRAGMA table_info(jobs)")
        existing_cols = {row[1] for row in cur.fetchall()}
        if "comment" not in existing_cols:
            cur.execute("ALTER TABLE jobs ADD COLUMN comment TEXT DEFAULT ''")
            conn.commit()
        if "visa_answer" not in existing_cols:
            cur.execute("ALTER TABLE jobs ADD COLUMN visa_answer TEXT DEFAULT ''")
            conn.commit()

    cur.close()
    conn.close()


def job_exists(link):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT id FROM jobs WHERE link = {_ph()}", (link,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None


def add_job(data):
    conn = get_connection()
    cur = conn.cursor()

    values = (
        data.get("applied_date", datetime.now().strftime("%Y-%m-%d")),
        data.get("company", ""),
        data.get("role", ""),
        data.get("posted_on", ""),
        data.get("job_description", ""),
        data.get("link", ""),
        data.get("status", "Applied"),
        data.get("comment", ""),
        data.get("visa_answer", ""),
    )

    if USE_POSTGRES:
        cur.execute(
            f"""INSERT INTO jobs (applied_date, company, role, posted_on, job_description, link, status, comment, visa_answer)
            VALUES ({_ph(9)}) RETURNING *""",
            values,
        )
        job = _fetchone(cur, conn)
        conn.commit()
    else:
        cur.execute(
            f"""INSERT INTO jobs (applied_date, company, role, posted_on, job_description, link, status, comment, visa_answer)
            VALUES ({_ph(9)})""",
            values,
        )
        conn.commit()
        job_id = cur.lastrowid
        cur.execute(f"SELECT * FROM jobs WHERE id = {_ph()}", (job_id,))
        job = _fetchone(cur, conn)

    cur.close()
    conn.close()
    return job


def get_jobs(status=None):
    conn = get_connection()
    cur = conn.cursor()
    if status:
        cur.execute(f"SELECT * FROM jobs WHERE status = {_ph()} ORDER BY created_at DESC", (status,))
    else:
        cur.execute("SELECT * FROM jobs ORDER BY created_at DESC")
    jobs = _fetchall(cur, conn)
    cur.close()
    conn.close()
    return jobs


def get_job(job_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM jobs WHERE id = {_ph()}", (job_id,))
    job = _fetchone(cur, conn)
    cur.close()
    conn.close()
    return job


def update_job(job_id, data):
    conn = get_connection()
    cur = conn.cursor()
    fields = []
    values = []
    for key in ("applied_date", "company", "role", "posted_on", "job_description", "link", "status", "comment", "visa_answer"):
        if key in data:
            fields.append(f"{key} = {_ph()}")
            values.append(data[key])
    if not fields:
        cur.close()
        conn.close()
        return None
    fields.append(f"updated_at = {_ph()}")
    values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    values.append(job_id)
    cur.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = {_ph()}", values)
    conn.commit()
    cur.execute(f"SELECT * FROM jobs WHERE id = {_ph()}", (job_id,))
    job = _fetchone(cur, conn)
    cur.close()
    conn.close()
    return job


def delete_job(job_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM jobs WHERE id = {_ph()}", (job_id,))
    conn.commit()
    cur.close()
    conn.close()
