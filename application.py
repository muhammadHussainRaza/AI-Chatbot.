from flask import Flask, render_template, request, redirect, url_for
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os, sqlite3, datetime

app = Flask(__name__)

# Configuration (LLMs, API, Prompt)
load_dotenv()
llm = ChatGoogleGenerativeAI(model='gemini-1.5-flash',google_api_key=os.getenv('GOOGLE_API_KEY'))
DB_FILE = "chatbot.db"

# ---- DB SETUP ----
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    created_at TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    sender TEXT,
                    text TEXT,
                    created_at TEXT,
                    FOREIGN KEY(chat_id) REFERENCES chats(id)
                )''')
    conn.commit()
    conn.close()

init_db()

# ---- ROUTES ----
@app.route("/")
def home():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, title FROM chats ORDER BY created_at DESC")
    chats = c.fetchall()
    conn.close()

    if chats:
        return redirect(url_for("view_chat", chat_id=chats[0][0]))
    else:
        return redirect(url_for("new_chat"))

@app.route("/chat/<int:chat_id>")
def view_chat(chat_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, title FROM chats ORDER BY created_at DESC")
    all_chats = c.fetchall()

    c.execute("SELECT sender, text FROM messages WHERE chat_id=? ORDER BY created_at ASC", (chat_id,))
    chat_history = [{"sender": row[0], "text": row[1]} for row in c.fetchall()]
    conn.close()

    return render_template("index.html", chats=all_chats, chat_history=chat_history, current_chat=chat_id)

@app.route("/new_chat")
def new_chat():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO chats (title, created_at) VALUES (?, ?)", (f"Chat {now}", now))
    chat_id = c.lastrowid

    # Add initial AI welcome message
    c.execute("INSERT INTO messages (chat_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
              (chat_id, "ai", "Hello! How can I help you today?", now))
    conn.commit()
    conn.close()
    return redirect(url_for("view_chat", chat_id=chat_id))

@app.route("/send/<int:chat_id>", methods=["POST"])
def send_message(chat_id):
    user_message = request.form.get("message", "").strip()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if user_message:
        # 1️ Store user message 
        with sqlite3.connect(DB_FILE, timeout=10, check_same_thread=False) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO messages (chat_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
                (chat_id, "user", user_message, now)
            )
            conn.commit()

        # 2️ Call AI 
        prompt = f"""
        You are a friendly, polite, and helpful AI assistant for general conversation.
        Always respond respectfully and to the point.
        Limit your answer to two sentences.
        If the query is unclear, politely ask for clarification.
        User: {user_message}
        """
        ai_response = llm.invoke(prompt)
        ai_reply = ai_response.content.strip()

        # 3️ Store AI response in DB
        with sqlite3.connect(DB_FILE, timeout=10, check_same_thread=False) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO messages (chat_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
                (chat_id, "ai", ai_reply, now)
            )
            conn.commit()

    return redirect(url_for("view_chat", chat_id=chat_id))


if __name__ == "__main__":
    app.run(debug=True)
