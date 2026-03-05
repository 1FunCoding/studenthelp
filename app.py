from flask import Flask, request, jsonify, session, send_from_directory, g
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__, static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "studenthelp-dev-secret-2026-xyz")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
CORS(app, supports_credentials=True, origins=["http://localhost:8080", "http://127.0.0.1:8080"])

DB_PATH = os.path.join(os.path.dirname(__file__), "studenthelp.db")


# ─── DB ────────────────────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur


# ─── AUTH DECORATOR ────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Not authenticated"}), 401
        return f(*args, **kwargs)
    return decorated


def uid():
    return session.get("user_id")


# ─── DB INIT ───────────────────────────────────────────────────────────────────

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'requester',
            bio           TEXT NOT NULL DEFAULT '',
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS requests (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            subject     TEXT NOT NULL DEFAULT 'Other',
            category    TEXT NOT NULL DEFAULT 'Tutoring',
            urgency     TEXT NOT NULL DEFAULT 'medium',
            format      TEXT NOT NULL DEFAULT 'online',
            user_id     INTEGER NOT NULL,
            status      TEXT NOT NULL DEFAULT 'open',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS offers (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id   INTEGER NOT NULL,
            helper_id    INTEGER NOT NULL,
            message      TEXT NOT NULL,
            availability TEXT NOT NULL DEFAULT '',
            status       TEXT NOT NULL DEFAULT 'pending',
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES requests(id),
            FOREIGN KEY (helper_id)  REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id   INTEGER NOT NULL,
            user2_id   INTEGER NOT NULL,
            request_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user1_id) REFERENCES users(id),
            FOREIGN KEY (user2_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_id       INTEGER NOT NULL,
            text            TEXT NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id),
            FOREIGN KEY (sender_id)       REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS help_sessions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id    INTEGER NOT NULL,
            requester_id  INTEGER NOT NULL,
            helper_id     INTEGER NOT NULL,
            status        TEXT NOT NULL DEFAULT 'upcoming',
            scheduled_at  TEXT,
            notes         TEXT NOT NULL DEFAULT '',
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id)   REFERENCES requests(id),
            FOREIGN KEY (requester_id) REFERENCES users(id),
            FOREIGN KEY (helper_id)    REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            type       TEXT NOT NULL DEFAULT 'info',
            message    TEXT NOT NULL,
            link_id    INTEGER,
            is_read    INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS ratings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL UNIQUE,
            rater_id   INTEGER NOT NULL,
            rated_id   INTEGER NOT NULL,
            score      INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES help_sessions(id),
            FOREIGN KEY (rater_id)   REFERENCES users(id),
            FOREIGN KEY (rated_id)   REFERENCES users(id)
        );
    """)
    db.commit()

    # Add password-reset columns if they don't exist yet (safe migration)
    for col in ("reset_token TEXT", "reset_token_expiry TEXT",
                "rating_sum INTEGER NOT NULL DEFAULT 0",
                "rating_count INTEGER NOT NULL DEFAULT 0"):
        try:
            db.execute(f"ALTER TABLE users ADD COLUMN {col}")
            db.commit()
        except Exception:
            pass

    # Seed demo data only on first run
    if db.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"] == 0:
        _seed(db)

    db.close()


def _seed(db):
    demo_users = [
        ("Nina",           "nina@scu.edu",  generate_password_hash("password"), "both",      "Hi, I'm Nina! I both request and offer help."),
        ("Sarah Johnson",  "sarah@scu.edu", generate_password_hash("password"), "helper",    "Senior Math major, love tutoring!"),
        ("Mike Davis",     "mike@scu.edu",  generate_password_hash("password"), "helper",    "CS major, React & full-stack dev."),
        ("Emily Rodriguez","emily@scu.edu", generate_password_hash("password"), "requester", "Sophomore looking for study help."),
    ]
    for u in demo_users:
        db.execute("INSERT INTO users (name,email,password_hash,role,bio) VALUES (?,?,?,?,?)", u)
    db.commit()

    nina_id  = db.execute("SELECT id FROM users WHERE email='nina@scu.edu'").fetchone()["id"]
    sarah_id = db.execute("SELECT id FROM users WHERE email='sarah@scu.edu'").fetchone()["id"]
    mike_id  = db.execute("SELECT id FROM users WHERE email='mike@scu.edu'").fetchone()["id"]
    emily_id = db.execute("SELECT id FROM users WHERE email='emily@scu.edu'").fetchone()["id"]

    sample_reqs = [
        ("Need help with Calculus II homework",
         "Struggling with integration by parts and related problems. Need someone to walk me through a few examples.",
         "Mathematics", "Tutoring", "high", "online", nina_id, "open"),
        ("Help setting up React project",
         "New to React and need help understanding components and state management. Would love a quick tutorial session.",
         "Computer Science", "Project Guidance", "medium", "either", nina_id, "open"),
        ("Moving furniture – need help!",
         "Need help moving some furniture in my dorm room this weekend. Should take about 30 minutes.",
         "Other", "General Assistance", "low", "in-person", emily_id, "open"),
    ]
    for r in sample_reqs:
        db.execute(
            "INSERT INTO requests (title,description,subject,category,urgency,format,user_id,status) VALUES (?,?,?,?,?,?,?,?)",
            r,
        )
    db.commit()

    # Seed demo conversations so Nina has messages when she first logs in
    db.execute("INSERT INTO conversations (user1_id,user2_id,request_id) VALUES (?,?,1)", (sarah_id, nina_id))
    convo1 = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    db.execute("INSERT INTO conversations (user1_id,user2_id,request_id) VALUES (?,?,2)", (mike_id, nina_id))
    convo2 = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    db.commit()

    seed_msgs = [
        (convo1, sarah_id, "Hey! I saw your request about Calculus II. I took that class last semester and aced it — I'd love to help you with integration by parts! 😊"),
        (convo1, nina_id,  "That's amazing! I'm really struggling with it. When are you free to meet?"),
        (convo1, sarah_id, "I'm free tomorrow evening after 6 pm, or anytime this weekend. Does that work?"),
        (convo2, mike_id,  "Hi! I saw you need help with your React project. I've been using React for 2 years — happy to walk you through components and state management!"),
        (convo2, nina_id,  "That would be super helpful! Can we do a Zoom call this week?"),
    ]
    for m in seed_msgs:
        db.execute("INSERT INTO messages (conversation_id,sender_id,text) VALUES (?,?,?)", m)
    db.commit()

    # Seed demo notifications for Nina
    seed_notifs = [
        (nina_id, "offer_received", "Sarah Johnson offered to help with \"Need help with Calculus II homework\"", 1),
        (nina_id, "offer_received", "Mike Davis offered to help with \"Help setting up React project\"", 2),
    ]
    for n in seed_notifs:
        db.execute("INSERT INTO notifications (user_id,type,message,link_id) VALUES (?,?,?,?)", n)
    db.commit()

    # Seed demo offers so Nina can accept them (helpers offer on Nina's requests)
    db.execute("INSERT INTO offers (request_id,helper_id,message,availability,status) VALUES (?,?,?,?,?)",
               (1, sarah_id, "I'd love to help! I aced Calc II last semester.", "Evenings after 6pm", "pending"))
    db.execute("INSERT INTO offers (request_id,helper_id,message,availability,status) VALUES (?,?,?,?,?)",
               (2, mike_id, "Happy to walk you through React components and state!", "Anytime weekends", "pending"))
    db.commit()


# ─── HELPERS ───────────────────────────────────────────────────────────────────

def fmt_date(ts):
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(str(ts))
        return f"{dt.month}/{dt.day}/{dt.year}"
    except Exception:
        return str(ts)


def fmt_time(ts):
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(str(ts))
        now = datetime.now()
        if dt.date() == now.date():
            hour = dt.hour % 12 or 12
            ampm = "AM" if dt.hour < 12 else "PM"
            return f"{hour}:{dt.minute:02d} {ampm}"
        yesterday = now.replace(day=now.day - 1) if now.day > 1 else now
        if dt.date() == yesterday.date():
            return "Yesterday"
        return fmt_date(ts)
    except Exception:
        return str(ts)


def req_dict(row):
    d = dict(row)
    d["date"] = fmt_date(d.get("created_at", ""))
    d["description"] = d.get("description", "")
    return d


def push_notif(user_id, type_, message, link_id=None):
    execute(
        "INSERT INTO notifications (user_id,type,message,link_id) VALUES (?,?,?,?)",
        (user_id, type_, message, link_id),
    )


# ─── STATIC ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ─── AUTH ──────────────────────────────────────────────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.json or {}
    name     = (data.get("name") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role     = data.get("role") or "requester"

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400

    if query("SELECT id FROM users WHERE email=?", (email,), one=True):
        return jsonify({"error": "That email is already registered"}), 409

    cur = execute(
        "INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,?)",
        (name, email, generate_password_hash(password), role),
    )
    user_id = cur.lastrowid
    session["user_id"] = user_id
    user = query("SELECT id,name,email,role,bio FROM users WHERE id=?", (user_id,), one=True)
    return jsonify({"user": dict(user)}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data     = request.json or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = query("SELECT * FROM users WHERE email=?", (email,), one=True)
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_id"] = user["id"]
    return jsonify({"user": {"id": user["id"], "name": user["name"],
                              "email": user["email"], "role": user["role"],
                              "bio": user["bio"]}})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me")
@login_required
def me():
    user = query("SELECT id,name,email,role,bio FROM users WHERE id=?", (uid(),), one=True)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": dict(user)})


@app.route("/api/auth/forgot-password", methods=["POST"])
def forgot_password():
    data  = request.json or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = query("SELECT id FROM users WHERE email=?", (email,), one=True)
    # Always return 200 so we don't leak whether the email exists
    if not user:
        return jsonify({"ok": True, "message": "If that email is registered you will receive a reset code."})

    token  = secrets.token_hex(4).upper()   # 8-char hex code, easy to type
    expiry = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    execute(
        "UPDATE users SET reset_token=?, reset_token_expiry=? WHERE id=?",
        (token, expiry, user["id"]),
    )
    # In production this token would be emailed; here we return it so the UI can display it.
    return jsonify({"ok": True, "token": token})


@app.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    data         = request.json or {}
    token        = (data.get("token") or "").strip().upper()
    new_password = data.get("new_password") or ""

    if not token or not new_password:
        return jsonify({"error": "Token and new password are required"}), 400
    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    user = query("SELECT id, reset_token_expiry FROM users WHERE reset_token=?", (token,), one=True)
    if not user:
        return jsonify({"error": "Invalid or expired reset code"}), 400

    expiry = user["reset_token_expiry"]
    if not expiry or datetime.utcnow() > datetime.fromisoformat(expiry):
        return jsonify({"error": "Reset code has expired. Please request a new one."}), 400

    execute(
        "UPDATE users SET password_hash=?, reset_token=NULL, reset_token_expiry=NULL WHERE id=?",
        (generate_password_hash(new_password), user["id"]),
    )
    return jsonify({"ok": True})


# ─── REQUESTS ──────────────────────────────────────────────────────────────────

@app.route("/api/requests")
def get_requests():
    search  = request.args.get("search", "")
    subject = request.args.get("subject", "")
    urgency = request.args.get("urgency", "")
    mine    = request.args.get("mine", "")
    current = uid()

    sql  = "SELECT r.*, u.name as by FROM requests r JOIN users u ON r.user_id=u.id WHERE 1=1"
    args = []

    if mine and current:
        sql += " AND r.user_id=?"
        args.append(current)
    else:
        sql += " AND r.status='open'"
        if current:
            sql += " AND r.user_id!=?"
            args.append(current)

    if search:
        # Split into individual words so every word must appear somewhere in
        # the title or description (AND logic), making multi-word queries like
        # "Operating System" match even when words are non-consecutive.
        words = [w.strip() for w in search.split() if w.strip()]
        for word in words:
            sql += " AND (r.title LIKE ? OR r.description LIKE ?)"
            args += [f"%{word}%", f"%{word}%"]
    if subject:
        sql += " AND r.subject=?"
        args.append(subject)
    if urgency:
        sql += " AND r.urgency=?"
        args.append(urgency)

    sql += " ORDER BY r.created_at DESC"
    rows = query(sql, args)
    return jsonify({"requests": [req_dict(r) for r in rows]})


@app.route("/api/requests", methods=["POST"])
@login_required
def create_request():
    data  = request.json or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), 400

    cur = execute(
        "INSERT INTO requests (title,description,subject,category,urgency,format,user_id) VALUES (?,?,?,?,?,?,?)",
        (title,
         data.get("description") or "",
         data.get("subject")     or "Other",
         data.get("category")    or "Tutoring",
         data.get("urgency")     or "medium",
         data.get("format")      or "online",
         uid()),
    )
    req_id = cur.lastrowid
    row = query("SELECT r.*, u.name as by FROM requests r JOIN users u ON r.user_id=u.id WHERE r.id=?",
                (req_id,), one=True)
    return jsonify({"request": req_dict(row)}), 201


@app.route("/api/requests/<int:req_id>")
def get_request(req_id):
    row = query("SELECT r.*, u.name as by FROM requests r JOIN users u ON r.user_id=u.id WHERE r.id=?",
                (req_id,), one=True)
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"request": req_dict(row)})


@app.route("/api/requests/<int:req_id>", methods=["DELETE"])
@login_required
def delete_request(req_id):
    row = query("SELECT * FROM requests WHERE id=?", (req_id,), one=True)
    if not row:
        return jsonify({"error": "Not found"}), 404
    if row["user_id"] != uid():
        return jsonify({"error": "Unauthorized"}), 403
    # Remove child rows first to satisfy foreign-key constraints
    execute("DELETE FROM offers WHERE request_id=?", (req_id,))
    execute("DELETE FROM help_sessions WHERE request_id=?", (req_id,))
    execute("DELETE FROM notifications WHERE link_id=? AND type='offer_received'", (req_id,))
    execute("DELETE FROM requests WHERE id=?", (req_id,))
    return jsonify({"ok": True})


@app.route("/api/requests/<int:req_id>", methods=["PATCH"])
@login_required
def update_request(req_id):
    data = request.json or {}
    row  = query("SELECT * FROM requests WHERE id=?", (req_id,), one=True)
    if not row:
        return jsonify({"error": "Not found"}), 404
    if row["user_id"] != uid():
        return jsonify({"error": "Unauthorized"}), 403

    if "status" in data:
        execute("UPDATE requests SET status=? WHERE id=?", (data["status"], req_id))

    row = query("SELECT r.*, u.name as by FROM requests r JOIN users u ON r.user_id=u.id WHERE r.id=?",
                (req_id,), one=True)
    return jsonify({"request": req_dict(row)})


# ─── OFFERS ────────────────────────────────────────────────────────────────────

@app.route("/api/requests/<int:req_id>/offers", methods=["POST"])
@login_required
def submit_offer(req_id):
    data    = request.json or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "A message is required"}), 400

    req = query("SELECT * FROM requests WHERE id=?", (req_id,), one=True)
    if not req:
        return jsonify({"error": "Request not found"}), 404
    if req["user_id"] == uid():
        return jsonify({"error": "You cannot offer on your own request"}), 400

    if query("SELECT id FROM offers WHERE request_id=? AND helper_id=?", (req_id, uid()), one=True):
        return jsonify({"error": "You already submitted an offer for this request"}), 409

    execute(
        "INSERT INTO offers (request_id,helper_id,message,availability) VALUES (?,?,?,?)",
        (req_id, uid(), message, data.get("availability") or ""),
    )

    # Create conversation between helper and requester (if none exists)
    requester_id = req["user_id"]
    existing = query(
        "SELECT id FROM conversations WHERE (user1_id=? AND user2_id=?) OR (user1_id=? AND user2_id=?)",
        (uid(), requester_id, requester_id, uid()), one=True,
    )
    if not existing:
        cur = execute(
            "INSERT INTO conversations (user1_id,user2_id,request_id) VALUES (?,?,?)",
            (uid(), requester_id, req_id),
        )
        convo_id = cur.lastrowid
        execute(
            "INSERT INTO messages (conversation_id,sender_id,text) VALUES (?,?,?)",
            (convo_id, uid(), message),
        )

    # Notify the request owner
    helper = query("SELECT name FROM users WHERE id=?", (uid(),), one=True)
    helper_name = helper["name"] if helper else "Someone"
    push_notif(
        requester_id,
        "offer_received",
        f"{helper_name} offered to help with \"{req['title']}\"",
        req_id,
    )

    return jsonify({"ok": True}), 201


@app.route("/api/requests/<int:req_id>/offers")
@login_required
def get_offers(req_id):
    rows = query(
        "SELECT o.*, u.name as helper_name FROM offers o JOIN users u ON o.helper_id=u.id WHERE o.request_id=? ORDER BY o.created_at DESC",
        (req_id,),
    )
    return jsonify({"offers": [dict(r) for r in rows]})


@app.route("/api/offers/<int:offer_id>/accept", methods=["POST"])
@login_required
def accept_offer(offer_id):
    offer = query(
        "SELECT o.*, r.user_id as req_owner FROM offers o JOIN requests r ON o.request_id=r.id WHERE o.id=?",
        (offer_id,), one=True,
    )
    if not offer:
        return jsonify({"error": "Not found"}), 404
    if offer["req_owner"] != uid():
        return jsonify({"error": "Unauthorized"}), 403
    if offer["helper_id"] == uid():
        return jsonify({"error": "You cannot accept your own offer"}), 400

    # Prevent accepting a second offer if one is already accepted
    already = query(
        "SELECT id FROM offers WHERE request_id=? AND status='accepted'",
        (offer["request_id"],), one=True,
    )
    if already:
        return jsonify({"error": "You have already accepted an offer for this request"}), 409

    execute("UPDATE offers SET status='accepted' WHERE id=?", (offer_id,))
    # Reject all remaining pending offers for this request
    execute(
        "UPDATE offers SET status='rejected' WHERE request_id=? AND id!=? AND status='pending'",
        (offer["request_id"], offer_id),
    )
    execute("UPDATE requests SET status='in-progress' WHERE id=?", (offer["request_id"],))
    execute(
        "INSERT INTO help_sessions (request_id,requester_id,helper_id,status) VALUES (?,?,?,?)",
        (offer["request_id"], uid(), offer["helper_id"], "upcoming"),
    )

    # Notify the helper their offer was accepted
    req_row = query("SELECT title FROM requests WHERE id=?", (offer["request_id"],), one=True)
    if req_row:
        push_notif(
            offer["helper_id"],
            "offer_accepted",
            f"Your offer on \"{req_row['title']}\" was accepted! Check your Sessions.",
            offer["request_id"],
        )

    return jsonify({"ok": True})


# ─── CONVERSATIONS ─────────────────────────────────────────────────────────────

@app.route("/api/conversations")
@login_required
def get_conversations():
    current = uid()
    rows = query(
        """
        SELECT c.id, c.request_id,
               u1.id as u1_id, u1.name as u1_name,
               u2.id as u2_id, u2.name as u2_name,
               (SELECT text       FROM messages WHERE conversation_id=c.id ORDER BY created_at DESC LIMIT 1) as last_msg,
               (SELECT created_at FROM messages WHERE conversation_id=c.id ORDER BY created_at DESC LIMIT 1) as last_ts
        FROM conversations c
        JOIN users u1 ON c.user1_id=u1.id
        JOIN users u2 ON c.user2_id=u2.id
        WHERE c.user1_id=? OR c.user2_id=?
        ORDER BY last_ts DESC
        """,
        (current, current),
    )
    result = []
    for r in rows:
        other_id   = r["u2_id"]   if r["u1_id"] == current else r["u1_id"]
        other_name = r["u2_name"] if r["u1_id"] == current else r["u1_name"]
        result.append({
            "id":                r["id"],
            "request_id":        r["request_id"],
            "other_user_id":     other_id,
            "other_user_name":   other_name,
            "other_user_initial": other_name[0].upper() if other_name else "?",
            "last_message":      r["last_msg"] or "",
            "last_message_time": fmt_time(r["last_ts"]) if r["last_ts"] else "",
        })
    return jsonify({"conversations": result})


@app.route("/api/conversations", methods=["POST"])
@login_required
def create_conversation():
    data          = request.json or {}
    other_user_id = data.get("other_user_id")
    if not other_user_id:
        return jsonify({"error": "other_user_id required"}), 400

    current  = uid()
    existing = query(
        "SELECT id FROM conversations WHERE (user1_id=? AND user2_id=?) OR (user1_id=? AND user2_id=?)",
        (current, other_user_id, other_user_id, current), one=True,
    )
    if existing:
        return jsonify({"conversation_id": existing["id"]})

    cur = execute("INSERT INTO conversations (user1_id,user2_id) VALUES (?,?)", (current, other_user_id))
    return jsonify({"conversation_id": cur.lastrowid}), 201


@app.route("/api/conversations/<int:convo_id>/messages")
@login_required
def get_messages(convo_id):
    current = uid()
    convo   = query(
        "SELECT * FROM conversations WHERE id=? AND (user1_id=? OR user2_id=?)",
        (convo_id, current, current), one=True,
    )
    if not convo:
        return jsonify({"error": "Not found"}), 404

    rows = query(
        "SELECT m.id,m.text,m.sender_id,m.created_at, u.name as sender_name FROM messages m JOIN users u ON m.sender_id=u.id WHERE m.conversation_id=? ORDER BY m.created_at ASC",
        (convo_id,),
    )
    result = [
        {
            "id":          m["id"],
            "text":        m["text"],
            "from":        "me" if m["sender_id"] == current else "them",
            "sender_name": m["sender_name"],
            "time":        fmt_time(m["created_at"]),
        }
        for m in rows
    ]
    return jsonify({"messages": result})


@app.route("/api/conversations/<int:convo_id>/messages", methods=["POST"])
@login_required
def send_message(convo_id):
    current = uid()
    data    = request.json or {}
    text    = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Text is required"}), 400

    convo = query(
        "SELECT * FROM conversations WHERE id=? AND (user1_id=? OR user2_id=?)",
        (convo_id, current, current), one=True,
    )
    if not convo:
        return jsonify({"error": "Not found"}), 404

    cur = execute(
        "INSERT INTO messages (conversation_id,sender_id,text) VALUES (?,?,?)",
        (convo_id, current, text),
    )
    msg = query(
        "SELECT m.*,u.name as sender_name FROM messages m JOIN users u ON m.sender_id=u.id WHERE m.id=?",
        (cur.lastrowid,), one=True,
    )

    # Notify the other participant
    other_id = convo["user2_id"] if convo["user1_id"] == current else convo["user1_id"]
    preview  = text[:80] + ("…" if len(text) > 80 else "")
    push_notif(
        other_id,
        "message",
        f"{msg['sender_name']}: {preview}",
        convo_id,
    )

    return jsonify({
        "message": {
            "id":          msg["id"],
            "text":        msg["text"],
            "from":        "me",
            "sender_name": msg["sender_name"],
            "time":        fmt_time(msg["created_at"]),
        }
    }), 201


# ─── SESSIONS ──────────────────────────────────────────────────────────────────

@app.route("/api/sessions")
@login_required
def get_sessions():
    current = uid()
    rows = query(
        """
        SELECT s.*, r.title as request_title,
               u1.name as requester_name, u2.name as helper_name,
               rt.score as rating_given
        FROM help_sessions s
        JOIN requests r ON s.request_id=r.id
        JOIN users u1 ON s.requester_id=u1.id
        JOIN users u2 ON s.helper_id=u2.id
        LEFT JOIN ratings rt ON rt.session_id=s.id AND rt.rater_id=?
        WHERE s.requester_id=? OR s.helper_id=?
        ORDER BY s.created_at DESC
        """,
        (current, current, current),
    )
    return jsonify({"sessions": [dict(r) for r in rows]})


@app.route("/api/sessions/<int:session_id>", methods=["PATCH"])
@login_required
def update_session(session_id):
    current = uid()
    row     = query(
        "SELECT * FROM help_sessions WHERE id=? AND (requester_id=? OR helper_id=?)",
        (session_id, current, current), one=True,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404

    data = request.json or {}
    if "status" in data:
        execute("UPDATE help_sessions SET status=? WHERE id=?", (data["status"], session_id))
    return jsonify({"ok": True})


@app.route("/api/sessions/<int:session_id>/rate", methods=["POST"])
@login_required
def rate_session(session_id):
    current = uid()
    sess = query(
        "SELECT * FROM help_sessions WHERE id=? AND requester_id=?",
        (session_id, current), one=True,
    )
    if not sess:
        return jsonify({"error": "Not found or you are not the requester"}), 404
    if sess["status"] != "completed":
        return jsonify({"error": "Session must be completed before rating"}), 400

    data  = request.json or {}
    score = data.get("score")
    if score is None or not isinstance(score, int) or not (1 <= score <= 5):
        return jsonify({"error": "Score must be an integer between 1 and 5"}), 400

    existing = query("SELECT id FROM ratings WHERE session_id=?", (session_id,), one=True)
    if existing:
        return jsonify({"error": "Session already rated"}), 409

    helper_id = sess["helper_id"]
    execute(
        "INSERT INTO ratings (session_id, rater_id, rated_id, score) VALUES (?,?,?,?)",
        (session_id, current, helper_id, score),
    )
    execute(
        "UPDATE users SET rating_sum = rating_sum + ?, rating_count = rating_count + 1 WHERE id=?",
        (score, helper_id),
    )

    helper = query("SELECT rating_sum, rating_count FROM users WHERE id=?", (helper_id,), one=True)
    return jsonify({"ok": True, "rating_sum": helper["rating_sum"], "rating_count": helper["rating_count"]})


# ─── USERS ─────────────────────────────────────────────────────────────────────

@app.route("/api/users/me", methods=["PATCH"])
@login_required
def update_profile():
    data    = request.json or {}
    current = uid()
    fields, args = [], []

    if data.get("name", "").strip():
        fields.append("name=?");  args.append(data["name"].strip())
    if "bio" in data:
        fields.append("bio=?");   args.append(data["bio"] or "")
    if "role" in data:
        fields.append("role=?");  args.append(data["role"])

    if fields:
        args.append(current)
        execute(f"UPDATE users SET {', '.join(fields)} WHERE id=?", args)

    user = query("SELECT id,name,email,role,bio FROM users WHERE id=?", (current,), one=True)
    return jsonify({"user": dict(user)})


# ─── STATS ─────────────────────────────────────────────────────────────────────

@app.route("/api/stats")
@login_required
def get_stats():
    current = uid()
    user = query("SELECT rating_sum, rating_count FROM users WHERE id=?", (current,), one=True)
    rating_sum   = user["rating_sum"]   if user else 0
    rating_count = user["rating_count"] if user else 0

    if rating_count > 0:
        bayesian_rating = round(rating_sum / rating_count, 1)
    else:
        bayesian_rating = None

    return jsonify({
        "my_requests":    query("SELECT COUNT(*) as c FROM requests WHERE user_id=?",                     (current,), one=True)["c"],
        "open_requests":  query("SELECT COUNT(*) as c FROM requests WHERE status='open'",                 one=True)["c"],
        "completed":      query("SELECT COUNT(*) as c FROM requests WHERE user_id=? AND status='closed'", (current,), one=True)["c"],
        "sessions":       query("SELECT COUNT(*) as c FROM help_sessions WHERE requester_id=? OR helper_id=?", (current, current), one=True)["c"],
        "rating_sum":     rating_sum,
        "rating_count":   rating_count,
        "bayesian_rating": bayesian_rating,
    })


# ─── NOTIFICATIONS ─────────────────────────────────────────────────────────────

@app.route("/api/notifications")
@login_required
def get_notifications():
    rows   = query(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 30",
        (uid(),),
    )
    unread = sum(1 for r in rows if not r["is_read"])
    return jsonify({
        "notifications": [dict(r) for r in rows],
        "unread_count":  unread,
    })


@app.route("/api/notifications/read-all", methods=["POST"])
@login_required
def mark_all_notifications_read():
    execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (uid(),))
    return jsonify({"ok": True})


@app.route("/api/notifications/<int:notif_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notif_id):
    execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (notif_id, uid()))
    return jsonify({"ok": True})


# ─── ENTRY ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=8080)
