from __future__ import annotations
import os
import sqlite3
from datetime import datetime

import streamlit as st
from openai import OpenAI

# ---- Config ----
st.set_page_config(page_title="AI Psychologist ", page_icon="🧠")
st.title("🧠 AI Psychologist")
st.caption("Local username login • SQLite persistence • Secrets for API key")

# ---- Secrets / API key ----
try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
except Exception:
    OPENAI_API_KEY = None

if not OPENAI_API_KEY:
    st.error("Missing OPENAI_API_KEY in .streamlit/secrets.toml")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)

# ---- Database (sqlite3) ----
DB_PATH = "chat.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """
)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('user','assistant')),
        content TEXT NOT NULL,
        ts TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """
)
conn.commit()

# ---- Helpers ----

def upsert_user(name: str) -> str:
    user_id = f"local:{name.strip().lower()}"
    conn.execute("INSERT OR IGNORE INTO users (id, display_name) VALUES (?, ?)", (user_id, name.strip()))
    conn.commit()
    return user_id


def load_messages(user_id: str) -> list[dict]:
    cur = conn.execute("SELECT role, content, ts FROM messages WHERE user_id=? ORDER BY id ASC",(user_id))
    rows = cur.fetchall()
    return [{"role": r[0], "content": r[1], "ts": r[2]} for r in rows]


def save_message(user_id: str, role: str, content: str) -> None:
    conn.execute("INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",(user_id, role, content))
    conn.commit()


# ---- Session state ----
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-5"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "auth_user_id" not in st.session_state:
    st.session_state.auth_user_id = None
if "loaded_history" not in st.session_state:
    st.session_state.loaded_history = False

# ---- Sidebar: login + controls ----
with st.sidebar:
    st.header("Sign in")
    name = st.text_input("Your name", placeholder="e.g., Alex")
    if st.button("Continue"):
        if not name.strip():
            st.error("Please enter your name.")
        else:
            user_id = upsert_user(name)
            st.session_state.auth_user_id = user_id
            st.session_state.loaded_history = False
            st.success(f"Signed in as {name}")
            st.rerun()

    st.divider()
    st.subheader("Session")
    if st.button("Sign out"):
        st.session_state.auth_user_id = None
        st.session_state.messages = []
        st.session_state.loaded_history = False
        st.experimental_rerun()

    if st.button("Clear my saved history"):
        if st.session_state.auth_user_id:
            conn.execute("DELETE FROM messages WHERE user_id=?", (st.session_state.auth_user_id,))
            conn.commit()
            st.session_state.messages = []
            st.success("Deleted your saved chat history.")
            st.rerun()

# ---- Require login ----
if not st.session_state.auth_user_id:
    st.stop()

# ---- Load history (once per sign-in) ----
if not st.session_state.loaded_history:
    st.session_state.messages = load_messages(st.session_state.auth_user_id)
    st.session_state.loaded_history = True

# ---- System prompt (not stored) ----
SYSTEM_PROMPT = {"role": "system", "content": (
        "You are an empathetic psychologist. Respond with warmth, validation, and gentle, practical guidance. "
        "Be concise, avoid medical diagnoses, suggest reflective questions, and encourage healthy coping strategies. "
        "Feel free to mention well-known ideas from psychology to validate the user. Use what they share about themselves.")}

# ---- Render prior messages ----
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ---- Chat input ----
prompt = st.chat_input("Tell me what's on your chest!")
if prompt:
    # save/display user message
    st.session_state.messages.append({"role": "user", "content": prompt, "ts": datetime.utcnow().isoformat()})
    save_message(st.session_state.auth_user_id, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    # build API messages: system + history
    api_messages = [SYSTEM_PROMPT] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages if m["role"] in ("user", "assistant")]

    # get/stream assistant reply
    with st.chat_message("assistant"):
        stream = client.chat.completions.create(model=st.session_state["openai_model"],messages=api_messages,stream=True)
        reply = st.write_stream(stream)

    # persist assistant reply
    st.session_state.messages.append({"role": "assistant", "content": reply, "ts": datetime.utcnow().isoformat()})
    save_message(st.session_state.auth_user_id, "assistant", reply)

# ---- Footer ----
st.caption(f"DB file: {DB_PATH}")
