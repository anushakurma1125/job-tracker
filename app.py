import os
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

from database import init_db, add_job, get_jobs, get_job, update_job, delete_job, job_exists, get_existing_links, bulk_add_jobs
from extractor import extract_job_details

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

# Always initialize the database (works with both direct run and Gunicorn)
init_db()


@app.errorhandler(Exception)
def handle_exception(e):
    """Return JSON for API errors instead of HTML error pages."""
    if request.path.startswith("/api/"):
        return jsonify({"error": str(e)}), 500
    return e


@app.errorhandler(500)
def handle_500(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error"}), 500
    return e

# Auth credentials from environment variables
APP_USERNAME = os.environ.get("APP_USERNAME", "admin")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "password")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == APP_USERNAME and password == APP_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/jobs", methods=["GET"])
@login_required
def list_jobs():
    status = request.args.get("status")
    jobs = get_jobs(status=status)
    return jsonify(jobs)


@app.route("/api/jobs", methods=["POST"])
@login_required
def create_job():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request body"}), 400

        link = data.get("link", "").strip()
        if not link:
            return jsonify({"error": "Job link is required"}), 400

        if job_exists(link):
            return jsonify({"error": "This job link has already been added"}), 409

        extracted = extract_job_details(link)
        job = add_job(extracted)
        return jsonify(job), 201
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/bulk", methods=["POST"])
@login_required
def bulk_upload():
    from openpyxl import load_workbook
    import io

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename.endswith((".xlsx", ".xls")):
        return jsonify({"error": "Please upload an Excel file (.xlsx)"}), 400

    try:
        from datetime import datetime as dt
        wb = load_workbook(io.BytesIO(file.read()), read_only=True)
        ws = wb.active

        # Read header row to map columns
        headers = [str(cell.value or "").strip().lower() for cell in next(ws.iter_rows(min_row=1, max_row=1))]

        col_map = {}
        for i, h in enumerate(headers):
            if "applied" in h and "date" in h:
                col_map["applied_date"] = i
            elif "company" in h:
                col_map["company"] = i
            elif "role" in h or "title" in h or "position" in h:
                col_map["role"] = i
            elif "posted" in h:
                col_map["posted_on"] = i
            elif "description" in h:
                col_map["job_description"] = i
            elif "link" in h or "url" in h:
                col_map["link"] = i
            elif "status" in h:
                col_map["status"] = i
            elif "comment" in h or "note" in h:
                col_map["comment"] = i
            elif "visa" in h:
                col_map["visa_answer"] = i

        # First pass: parse all rows from the spreadsheet
        parsed_rows = []
        errors = []

        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            try:
                def get_val(key):
                    if key in col_map and col_map[key] < len(row):
                        val = row[col_map[key]]
                        if val is None:
                            return ""
                        if hasattr(val, 'strftime'):
                            return val.strftime("%Y-%m-%d")
                        return str(val).strip()
                    return ""

                job_data = {
                    "applied_date": get_val("applied_date"),
                    "company": get_val("company"),
                    "role": get_val("role"),
                    "posted_on": get_val("posted_on"),
                    "job_description": get_val("job_description"),
                    "link": get_val("link"),
                    "status": get_val("status") or "Applied",
                    "comment": get_val("comment"),
                    "visa_answer": get_val("visa_answer"),
                }

                if not job_data["company"] and not job_data["role"] and not job_data["link"]:
                    continue

                parsed_rows.append(job_data)
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        wb.close()

        # Single DB call: check all existing links at once
        all_links = [r["link"] for r in parsed_rows if r["link"]]
        existing_links = get_existing_links(all_links) if all_links else set()

        # Split into new vs duplicate
        to_insert = []
        skipped = 0
        for row_data in parsed_rows:
            if row_data["link"] and row_data["link"] in existing_links:
                skipped += 1
            else:
                to_insert.append(row_data)

        # Single DB call: batch insert all new jobs
        added = bulk_add_jobs(to_insert)

        return jsonify({
            "added": added,
            "skipped": skipped,
            "errors": errors,
        }), 200

    except Exception as e:
        return jsonify({"error": f"Failed to process file: {str(e)}"}), 500


@app.route("/api/jobs/<int:job_id>", methods=["GET"])
@login_required
def get_single_job(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/jobs/<int:job_id>", methods=["PUT"])
@login_required
def update_single_job(job_id):
    data = request.get_json()
    job = update_job(job_id, data)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/jobs/<int:job_id>", methods=["DELETE"])
@login_required
def delete_single_job(job_id):
    delete_job(job_id)
    return jsonify({"message": "Job deleted"}), 200


if __name__ == "__main__":
    app.run(debug=True, port=5001)
