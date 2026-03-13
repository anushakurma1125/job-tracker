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
        # ── Users table ──
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

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
                user_id INTEGER DEFAULT 1,
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
        if "user_id" not in existing_cols:
            cur.execute("ALTER TABLE jobs ADD COLUMN user_id INTEGER DEFAULT 1")
            conn.commit()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id SERIAL PRIMARY KEY,
                filename TEXT NOT NULL,
                label TEXT DEFAULT '',
                file_data BYTEA NOT NULL,
                file_size INTEGER NOT NULL,
                user_id INTEGER DEFAULT 1,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Migrate resumes
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'resumes'")
        resume_cols = {row[0] for row in cur.fetchall()}
        if "user_id" not in resume_cols:
            cur.execute("ALTER TABLE resumes ADD COLUMN user_id INTEGER DEFAULT 1")
            conn.commit()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS email_settings (
                id SERIAL PRIMARY KEY,
                gmail_credentials TEXT DEFAULT '',
                gmail_email TEXT DEFAULT '',
                enabled INTEGER DEFAULT 0,
                last_scanned_at TIMESTAMP,
                user_id INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Migrate email_settings
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'email_settings'")
        email_cols = {row[0] for row in cur.fetchall()}
        if "user_id" not in email_cols:
            cur.execute("ALTER TABLE email_settings ADD COLUMN user_id INTEGER DEFAULT 1")
            conn.commit()
        if "scan_checkpoint" not in email_cols:
            cur.execute("ALTER TABLE email_settings ADD COLUMN scan_checkpoint TEXT DEFAULT NULL")
            conn.commit()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS scan_log (
                id SERIAL PRIMARY KEY,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                emails_checked INTEGER DEFAULT 0,
                rejections_found INTEGER DEFAULT 0,
                details TEXT DEFAULT '[]',
                user_id INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Migrate scan_log
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'scan_log'")
        scan_cols = {row[0] for row in cur.fetchall()}
        if "user_id" not in scan_cols:
            cur.execute("ALTER TABLE scan_log ADD COLUMN user_id INTEGER DEFAULT 1")
            conn.commit()
    else:
        # ── Users table ──
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

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
                user_id INTEGER DEFAULT 1,
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
        if "user_id" not in existing_cols:
            cur.execute("ALTER TABLE jobs ADD COLUMN user_id INTEGER DEFAULT 1")
            conn.commit()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                label TEXT DEFAULT '',
                file_data BLOB NOT NULL,
                file_size INTEGER NOT NULL,
                user_id INTEGER DEFAULT 1,
                uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Migrate resumes
        cur.execute("PRAGMA table_info(resumes)")
        resume_cols = {row[1] for row in cur.fetchall()}
        if "user_id" not in resume_cols:
            cur.execute("ALTER TABLE resumes ADD COLUMN user_id INTEGER DEFAULT 1")
            conn.commit()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS email_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gmail_credentials TEXT DEFAULT '',
                gmail_email TEXT DEFAULT '',
                enabled INTEGER DEFAULT 0,
                last_scanned_at TEXT,
                user_id INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Migrate email_settings
        cur.execute("PRAGMA table_info(email_settings)")
        email_cols = {row[1] for row in cur.fetchall()}
        if "user_id" not in email_cols:
            cur.execute("ALTER TABLE email_settings ADD COLUMN user_id INTEGER DEFAULT 1")
            conn.commit()
        if "scan_checkpoint" not in email_cols:
            cur.execute("ALTER TABLE email_settings ADD COLUMN scan_checkpoint TEXT DEFAULT NULL")
            conn.commit()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS scan_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scanned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                emails_checked INTEGER DEFAULT 0,
                rejections_found INTEGER DEFAULT 0,
                details TEXT DEFAULT '[]',
                user_id INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Migrate scan_log
        cur.execute("PRAGMA table_info(scan_log)")
        scan_cols = {row[1] for row in cur.fetchall()}
        if "user_id" not in scan_cols:
            cur.execute("ALTER TABLE scan_log ADD COLUMN user_id INTEGER DEFAULT 1")
            conn.commit()

    cur.close()
    conn.close()


# ── User CRUD ──

def create_user(username, password_hash, display_name):
    conn = get_connection()
    cur = conn.cursor()
    if USE_POSTGRES:
        cur.execute(
            f"""INSERT INTO users (username, password_hash, display_name)
            VALUES ({_ph(3)}) RETURNING id, username, display_name, created_at""",
            (username, password_hash, display_name),
        )
        user = _fetchone(cur, conn)
    else:
        cur.execute(
            f"""INSERT INTO users (username, password_hash, display_name)
            VALUES ({_ph(3)})""",
            (username, password_hash, display_name),
        )
        user_id = cur.lastrowid
        cur.execute(f"SELECT id, username, display_name, created_at FROM users WHERE id = {_ph()}", (user_id,))
        user = _fetchone(cur, conn)
    conn.commit()
    cur.close()
    conn.close()
    return user


def get_user_by_username(username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE username = {_ph()}", (username,))
    user = _fetchone(cur, conn)
    cur.close()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT id, username, display_name, created_at FROM users WHERE id = {_ph()}", (user_id,))
    user = _fetchone(cur, conn)
    cur.close()
    conn.close()
    return user


# ── Job CRUD ──

def job_exists(link, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT id FROM jobs WHERE link = {_ph()} AND user_id = {_ph()}", (link, user_id))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None


def add_job(data, user_id):
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
        user_id,
    )

    if USE_POSTGRES:
        cur.execute(
            f"""INSERT INTO jobs (applied_date, company, role, posted_on, job_description, link, status, comment, visa_answer, user_id)
            VALUES ({_ph(10)}) RETURNING *""",
            values,
        )
        job = _fetchone(cur, conn)
        conn.commit()
    else:
        cur.execute(
            f"""INSERT INTO jobs (applied_date, company, role, posted_on, job_description, link, status, comment, visa_answer, user_id)
            VALUES ({_ph(10)})""",
            values,
        )
        conn.commit()
        job_id = cur.lastrowid
        cur.execute(f"SELECT * FROM jobs WHERE id = {_ph()}", (job_id,))
        job = _fetchone(cur, conn)

    cur.close()
    conn.close()
    return job


def get_existing_links(links, user_id):
    """Check which links already exist for this user in one query."""
    if not links:
        return set()
    conn = get_connection()
    cur = conn.cursor()
    placeholders = ", ".join([_ph()] * len(links))
    cur.execute(
        f"SELECT link FROM jobs WHERE link IN ({placeholders}) AND user_id = {_ph()}",
        tuple(links) + (user_id,),
    )
    existing = {row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return existing


def bulk_add_jobs(jobs_data, user_id):
    """Insert multiple jobs in a single connection with batch inserts."""
    if not jobs_data:
        return 0
    conn = get_connection()
    cur = conn.cursor()
    added = 0
    for data in jobs_data:
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
            user_id,
        )
        cur.execute(
            f"""INSERT INTO jobs (applied_date, company, role, posted_on, job_description, link, status, comment, visa_answer, user_id)
            VALUES ({_ph(10)})""",
            values,
        )
        added += 1
    conn.commit()
    cur.close()
    conn.close()
    return added


def get_jobs(user_id, status=None):
    conn = get_connection()
    cur = conn.cursor()
    if status:
        cur.execute(
            f"SELECT * FROM jobs WHERE user_id = {_ph()} AND status = {_ph()} ORDER BY applied_date DESC",
            (user_id, status),
        )
    else:
        cur.execute(
            f"SELECT * FROM jobs WHERE user_id = {_ph()} ORDER BY applied_date DESC",
            (user_id,),
        )
    jobs = _fetchall(cur, conn)
    cur.close()
    conn.close()
    return jobs


def get_job(job_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM jobs WHERE id = {_ph()} AND user_id = {_ph()}", (job_id, user_id))
    job = _fetchone(cur, conn)
    cur.close()
    conn.close()
    return job


def update_job(job_id, data, user_id):
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
    values.append(user_id)
    cur.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = {_ph()} AND user_id = {_ph()}", values)
    conn.commit()
    cur.execute(f"SELECT * FROM jobs WHERE id = {_ph()} AND user_id = {_ph()}", (job_id, user_id))
    job = _fetchone(cur, conn)
    cur.close()
    conn.close()
    return job


def delete_job(job_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM jobs WHERE id = {_ph()} AND user_id = {_ph()}", (job_id, user_id))
    conn.commit()
    cur.close()
    conn.close()


def get_earliest_applied_date(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT MIN(applied_date) FROM jobs WHERE user_id = {_ph()}", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    val = row[0] if not isinstance(row, dict) else list(row.values())[0]
    return val


def get_active_jobs(user_id):
    """Get jobs that are not rejected or withdrawn (candidates for status update)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT * FROM jobs WHERE user_id = {_ph()} AND status NOT IN ('Rejected', 'Withdrawn') ORDER BY applied_date DESC",
        (user_id,),
    )
    jobs = _fetchall(cur, conn)
    cur.close()
    conn.close()
    return jobs


# ── Resume CRUD ──

def add_resume(filename, label, file_data, file_size, user_id):
    conn = get_connection()
    cur = conn.cursor()
    if USE_POSTGRES:
        import psycopg2
        cur.execute(
            f"""INSERT INTO resumes (filename, label, file_data, file_size, user_id)
            VALUES ({_ph(5)}) RETURNING id, filename, label, file_size, uploaded_at""",
            (filename, label, psycopg2.Binary(file_data), file_size, user_id),
        )
        resume = _fetchone(cur, conn)
    else:
        cur.execute(
            f"""INSERT INTO resumes (filename, label, file_data, file_size, user_id)
            VALUES ({_ph(5)})""",
            (filename, label, file_data, file_size, user_id),
        )
        resume_id = cur.lastrowid
        cur.execute(
            f"SELECT id, filename, label, file_size, uploaded_at FROM resumes WHERE id = {_ph()}",
            (resume_id,),
        )
        resume = _fetchone(cur, conn)
    conn.commit()
    cur.close()
    conn.close()
    return resume


def get_resumes(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT id, filename, label, file_size, uploaded_at FROM resumes WHERE user_id = {_ph()} ORDER BY uploaded_at DESC",
        (user_id,),
    )
    resumes = _fetchall(cur, conn)
    cur.close()
    conn.close()
    return resumes


def get_resume_file(resume_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT filename, file_data FROM resumes WHERE id = {_ph()} AND user_id = {_ph()}",
        (resume_id, user_id),
    )
    row = _fetchone(cur, conn)
    cur.close()
    conn.close()
    return row


def update_resume_label(resume_id, label, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE resumes SET label = {_ph()} WHERE id = {_ph()} AND user_id = {_ph()}",
        (label, resume_id, user_id),
    )
    conn.commit()
    cur.execute(
        f"SELECT id, filename, label, file_size, uploaded_at FROM resumes WHERE id = {_ph()} AND user_id = {_ph()}",
        (resume_id, user_id),
    )
    resume = _fetchone(cur, conn)
    cur.close()
    conn.close()
    return resume


def delete_resume(resume_id, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM resumes WHERE id = {_ph()} AND user_id = {_ph()}", (resume_id, user_id))
    conn.commit()
    cur.close()
    conn.close()


# ── Email Settings CRUD ──

def get_email_settings(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT id, gmail_email, enabled, last_scanned_at, scan_checkpoint, created_at FROM email_settings WHERE user_id = {_ph()} LIMIT 1",
        (user_id,),
    )
    row = _fetchone(cur, conn)
    cur.close()
    conn.close()
    return row


def save_email_settings(gmail_credentials, gmail_email, user_id):
    conn = get_connection()
    cur = conn.cursor()
    # Check if settings exist for this user
    cur.execute(f"SELECT id FROM email_settings WHERE user_id = {_ph()} LIMIT 1", (user_id,))
    existing = cur.fetchone()
    if existing:
        row_id = existing[0] if not isinstance(existing, dict) else existing["id"]
        cur.execute(
            f"UPDATE email_settings SET gmail_credentials = {_ph()}, gmail_email = {_ph()}, enabled = 1 WHERE id = {_ph()}",
            (gmail_credentials, gmail_email, row_id),
        )
    else:
        cur.execute(
            f"INSERT INTO email_settings (gmail_credentials, gmail_email, enabled, user_id) VALUES ({_ph(4)})",
            (gmail_credentials, gmail_email, 1, user_id),
        )
    conn.commit()
    cur.close()
    conn.close()


def get_gmail_credentials(user_id):
    """Return the raw gmail_credentials JSON string."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT gmail_credentials FROM email_settings WHERE enabled = 1 AND user_id = {_ph()} LIMIT 1",
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return row[0] if not isinstance(row, dict) else row.get("gmail_credentials")


def update_last_scanned(user_id):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        f"UPDATE email_settings SET last_scanned_at = {_ph()} WHERE user_id = {_ph()}",
        (now, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def save_scan_checkpoint(checkpoint_epoch, user_id):
    """Save the epoch of the oldest processed email so next scan continues from there."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE email_settings SET scan_checkpoint = {_ph()} WHERE user_id = {_ph()}",
        (str(checkpoint_epoch), user_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def clear_scan_checkpoint(user_id):
    """Clear checkpoint after first scan is fully complete."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE email_settings SET scan_checkpoint = NULL WHERE user_id = {_ph()}",
        (user_id,),
    )
    conn.commit()
    cur.close()
    conn.close()


def delete_email_settings(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM email_settings WHERE user_id = {_ph()}", (user_id,))
    conn.commit()
    cur.close()
    conn.close()


# ── Scan Log CRUD ──

def add_scan_log(emails_checked, rejections_found, details_json, user_id):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        f"INSERT INTO scan_log (scanned_at, emails_checked, rejections_found, details, user_id) VALUES ({_ph(5)})",
        (now, emails_checked, rejections_found, details_json, user_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_scan_logs(user_id, limit=20):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT * FROM scan_log WHERE user_id = {_ph()} ORDER BY scanned_at DESC LIMIT {_ph()}",
        (user_id, limit),
    )
    logs = _fetchall(cur, conn)
    cur.close()
    conn.close()
    return logs
