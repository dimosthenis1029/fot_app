
from __future__ import annotations
import os
import json
from datetime import datetime

import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="AI Psychologist", page_icon="🧠")
st.title("🧠 AI Psychologist")
st.caption("Local username login • JSON persistence • Secrets for API key")

try:
    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
except Exception:
    OPENAI_API_KEY = None

client = OpenAI(api_key=OPENAI_API_KEY)

# ---- Simple JSON database ----
DB_PATH = "chat_history.json"
if not os.path.exists(DB_PATH):
    with open(DB_PATH, "w") as f:
        json.dump({"users": {}, "messages": {}}, f)

def load_db():
    with open(DB_PATH, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)

def upsert_user(name: str) -> str:
    user_id = f"local:{name.strip().lower()}"
    db = load_db()
    if user_id not in db["users"]:
        db["users"][user_id] = {
            "display_name": name.strip(),
            "created_at": datetime.utcnow().isoformat(),}
        db["messages"][user_id] = []
        save_db(db)
    return user_id

def load_messages(user_id: str) -> list[dict]:
    db = load_db()
    return db["messages"].get(user_id, [])

def save_message(user_id: str, role: str, content: str) -> None:
    db = load_db()
    db["messages"].setdefault(user_id, []).append({
        "role": role,
        "content": content,
        "ts": datetime.utcnow().isoformat()
    })
    save_db(db)

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
            db = load_db()
            db["messages"][st.session_state.auth_user_id] = []
            save_db(db)
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
SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are an empathetic psychologist. Respond with warmth, validation, and gentle, practical guidance. "
        "Be concise, avoid medical diagnoses, suggest reflective questions, and encourage healthy coping strategies. "
        "Feel free to mention well-known ideas from psychology to validate the user. Use what they share about themselves."
    ),
}

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
