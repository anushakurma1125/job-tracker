import os
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

from database import init_db, add_job, get_jobs, get_job, update_job, delete_job, job_exists
from extractor import extract_job_details

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

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
    data = request.get_json()
    link = data.get("link", "").strip()
    if not link:
        return jsonify({"error": "Job link is required"}), 400

    if job_exists(link):
        return jsonify({"error": "This job link has already been added"}), 409

    try:
        extracted = extract_job_details(link)
        job = add_job(extracted)
        return jsonify(job), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
    init_db()
    app.run(debug=True, port=5001)
