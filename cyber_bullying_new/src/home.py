# MIT License


from flask import Blueprint, request, render_template, redirect, session, abort, flash, url_for, current_app
from src.auth import login_required
from src.helpers import error, UserInfo
from cs50 import SQL
from flask import abort
from src import reddy_tech
from src.text_classifier import load_text_model, get_vocab
import cv2
import pytesseract
from werkzeug.utils import secure_filename
import os
import uuid
import telepot
import config as app_config

# Initialize bot only if token provided
bot = telepot.Bot(app_config.TELEPOT_TOKEN) if app_config.TELEPOT_TOKEN else None
#  Mention the installed location of Tesseract-OCR in your system (configurable)
# Only set tesseract command if provided in config; otherwise rely on PATH
if getattr(app_config, 'TESSERACT_CMD', None):
    pytesseract.pytesseract.tesseract_cmd = app_config.TESSERACT_CMD

# Import required packages
from googletrans import Translator
translator = Translator()
import socket

def get_system_ip():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    return ip_address

home = Blueprint("home", __name__, static_folder="static", template_folder="templates")
blocked_ips = set()

db = SQL("sqlite:///src/main.db")
# Load the ML model and initiate Mindhunters using the text_classifier wrapper
try:
    model = load_text_model()
except Exception as e:
    model = None
    print('Warning: failed to load text model:', e)
    import traceback; traceback.print_exc()
# Ensure vocabulary is available for preprocessing
word_to_index, max_len = get_vocab()

@home.route('/unblock_my_ip')
def unblock_my_ip():
    my_ip_address = get_system_ip()
    blocked_ips.discard(my_ip_address)
    return f"IP address {my_ip_address} unblocked successfully"

@home.route("/detect", methods=["GET", "POST"])
@login_required
def detect():
    userInfo, dp = UserInfo(db)
    # Accept uploaded file or legacy form value
    uploaded_file = request.files.get('file')
    img_field = request.form.get('file')
    # Build absolute path to the project's static images folder
    from pathlib import Path
    project_root = Path(__file__).resolve().parents[1]
    upload_dir = Path(app_config.UPLOAD_FOLDER)
    upload_dir.mkdir(parents=True, exist_ok=True)

    image_path = None
    web_path = None

    # Handle file upload
    if uploaded_file and uploaded_file.filename:
        filename = secure_filename(uploaded_file.filename)
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in getattr(app_config, 'ALLOWED_EXTENSIONS', set()):
            allowed = ','.join(sorted(getattr(app_config, 'ALLOWED_EXTENSIONS', [])))
            flash('Unsupported file type. Allowed: ' + allowed)
            return redirect('/')
        # create unique filename to avoid collisions
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        image_path = upload_dir / unique_name
        try:
            uploaded_file.save(str(image_path))
        except Exception as e:
            print('Failed to save uploaded file:', e)
            flash('Failed to save uploaded image')
            return redirect('/')
        web_path = f'static/images/{unique_name}'

    # Legacy behavior: client may send just a filename string in form
    elif img_field:
        img_filename = img_field
        print('requested image filename:', img_filename)
        image_path = project_root / 'static' / 'images' / img_filename
        web_path = f'static/images/{img_filename}'

    else:
        flash('No image provided')
        return redirect('/')

    if not image_path or not image_path.exists():
        print(f'Image file not found: {image_path}')
        flash('Image file not found')
        return redirect('/')
    # Read the image with OpenCV and verify it loaded
    image = cv2.imread(str(image_path))
    if image is None:
        print(f'cv2.imread failed for: {image_path} (file may be corrupt or unreadable)')
        flash('Uploaded image is unreadable')
        return redirect('/')
    # Convert the image to gray scale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    text1=pytesseract.image_to_string(gray)
    print('\n--------------Recognized Text------------\n')
    print(text1)     
    post_text = text1
    if not post_text:
        return redirect("/")
    text = [reddy_tech.clean_text(post_text)]
    text = reddy_tech.sentences_to_indices(text, word_to_index, max_len)
    if model is None:
        flash('Model not loaded; cannot classify')
        return redirect('/')

    ans = model.predict(text)[0][0]
    db.execute("INSERT INTO :tablename ('text', 'nature', 'image') VALUES (:post_text, :score, :post_img)", tablename=userInfo['username'], post_text=post_text, score=str(ans), post_img=web_path)
    if (ans < 0.4):
        score = (0.4 - ans)
        total = "{:.2f}".format(userInfo['total'] + score)
        good_score = "{:.2f}".format(userInfo['score'] + score)
        db.execute("UPDATE users SET score=:score, total=:total WHERE id=:user_id", score = good_score, total = total, user_id = session["user_id"])
        return redirect("/")
    else:
        score = (ans - 0.8)
        total = "{:.2f}".format((userInfo['total'] + score))
        db.execute("UPDATE users SET total=:total WHERE id=:user_id", total = total, user_id = session["user_id"])
        return redirect("/")


@home.route("/", methods=["GET", "POST"])
@login_required
def index():
    userInfo, dp = UserInfo(db)
    if request.method == "GET":
        get_posts = db.execute("SELECT * FROM :tablename", tablename=userInfo['username'])
        get_posts = add_publisher(get_posts, userInfo['username'])
        follow_metadata = db.execute("SELECT following FROM :tablename", tablename=userInfo["username"]+'Social')
        posts_metadata = {userInfo['username']:dp}
        for following in follow_metadata:
            following_posts = db.execute("SELECT * FROM :tablename", tablename=following['following'])
            following_posts = add_publisher(following_posts, following['following'])
            other_user_info, other_user_dp = UserInfo(db, following['following'])
            posts_metadata[following['following']] = other_user_dp
            get_posts.extend(following_posts)
        get_posts.sort(key=get_timestamp, reverse=True)
        if get_posts:
            print('score is ', ((userInfo['score']/userInfo['total'])*10))
            if ((userInfo['score']/userInfo['total'])*10) < 5:
                blocked_ips.add(get_system_ip())
                print('blocked')
                if bot:
                    try:
                        bot.sendMessage("5486829784", str("your account is blocked"))
                    except Exception as e:
                        print('Failed to send bot notification:', e)
##                abort(403, "ip blocked due to score is les than 5")
                return render_template("index.html", msg = "ip blocked due to score is less than 5")
            else:
                return render_template('index.html', posts=get_posts, posts_metadata=posts_metadata, dp=dp, user=userInfo, reputation = ((userInfo['score']/userInfo['total'])*10))
        else:
            return render_template("index.html")
    else:
        # Accept either typed post or voice_post (from microphone)
        post_text = request.form.get("post")
        voice_text = request.form.get("voice_post")
        # Prefer voice input if present
        if voice_text and voice_text.strip():
            post_text = voice_text

        if not post_text or not post_text.strip():
            # nothing to post
            return redirect("/")

        # Default to English since language dropdown is removed
        fromlang = 'en'
        try:
            post_text = translator.translate(post_text, src=fromlang, dest='en').text
        except Exception as e:
            print('Translation error:', e)
            # Fall back to original text if translation fails
            pass

        text = [reddy_tech.clean_text(post_text)]
        text = reddy_tech.sentences_to_indices(text, word_to_index, max_len)
        ans = model.predict(text)[0][0]
        db.execute("INSERT INTO :tablename ('text', 'nature') VALUES (:post_text, :score)", tablename=userInfo['username'], post_text=post_text, score=str(ans))
        if (ans < 0.4):
            score = (0.4 - ans)
            total = "{:.2f}".format(userInfo['total'] + score)
            good_score = "{:.2f}".format(userInfo['score'] + score)
            db.execute("UPDATE users SET score=:score, total=:total WHERE id=:user_id", score = good_score, total = total, user_id = session["user_id"])
            return redirect("/")
        else:
            score = (ans - 0.4)
            total = "{:.2f}".format((userInfo['total'] + score))
            db.execute("UPDATE users SET total=:total WHERE id=:user_id", total = total, user_id = session["user_id"])
            return redirect("/")
        


@home.route("/about", methods=["GET"])
@login_required
def about():
    return render_template("about.html")

def get_timestamp(post):
    return post.get('timestamp')

def add_publisher(posts, publisher):
    for item in posts:
        item["publisher"] = publisher
    return posts
