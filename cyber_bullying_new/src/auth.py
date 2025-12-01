

from werkzeug.security import check_password_hash, generate_password_hash
from flask import Blueprint, session, request, render_template, redirect
from src.helpers import error
from functools import wraps
from cs50 import SQL
import re

auth = Blueprint("auth", __name__, static_folder = "static", template_folder = "templates")
db = SQL("sqlite:///src/main.db")

@auth.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirm = request.form.get("confirm")
        # Ensure username was submitted
        if not username:
            return render_template("register.html", msg = "You must provide a username")
        # Username must be alphanumeric/underscore only and contain at least one letter
        if not re.match(r'^[A-Za-z0-9_]+$', username) or not re.search(r'[A-Za-z]', username):
            return render_template("register.html", msg = "Please enter a valid username (letters, numbers, underscores only and must include a letter)")
        # Ensure password was submitted
        elif not password:
            return render_template("register.html", msg = "You must provide a password")
        # Ensure the passwords match
        elif password != confirm:
            return render_template("register.html", msg = "Your passwords do not match")
        # Password policy: at least 8 chars, one uppercase, one lowercase, one special char
        if len(password) < 8 or not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password) or not re.search(r'[^A-Za-z0-9]', password):
            return render_template("register.html", msg = "Please enter a valid password: min 8 chars, include upper & lower case and a special character")
        # Insert the username and hash onto the SQL database
        try:
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=generate_password_hash(password))
            db.execute("CREATE TABLE IF NOT EXISTS :tablename ('id' INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,'text' TEXT NOT NULL, 'timestamp' DATETIME DEFAULT CURRENT_TIMESTAMP, 'image' TEXT, 'nature' TEXT DEFAULT 'na')", tablename=username)
            db.execute("CREATE TABLE IF NOT EXISTS :tablename ('following' TEXT PRIMARY KEY NOT NULL, 'timestamp' DATETIME DEFAULT CURRENT_TIMESTAMP)", tablename=str(username)+'Social')
            session['reg_success'] = "Registration successful. Please log in."
            return redirect("/login")
        except Exception as msg:
            return render_template("register.html", msg = "Username already taken")

@auth.route("/login", methods=["GET", "POST"])
def login():
    reg_msg = session.pop('reg_success', None)
    session.clear()
    if request.method == "POST":
        username = request.form.get("username")
        if not username:
            return render_template("login.html", msg = "You must provide username")
        # Do not accept numeric-only usernames at login
        if username.isdigit():
            return render_template("login.html", msg = "Invalid username")
        elif not request.form.get("password"):
            return render_template("login.html", msg = "You must provide password")
        accountExists = db.execute("SELECT * FROM users WHERE username = :username", username=username)
        if len(accountExists) != 1 or not check_password_hash(accountExists[0]["hash"], request.form.get("password")):
            return render_template("login.html", msg = "Invalid username and/or password")
        session["user_id"] = accountExists[0]["id"]
        return redirect("/")
    else:
        return render_template("login.html", msg = reg_msg if reg_msg else "")

@auth.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function
