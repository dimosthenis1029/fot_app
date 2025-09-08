from __future__ import annotations
import os
import json
from datetime import datetime

import streamlit as st
from openai import OpenAI

# ---- Config ----
st.set_page_config(page_title="ROE", page_icon="Roe.png")
st.image("Roe.png", width=240)

# ---- Secrets / API key ----
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
        db["users"][user_id] = {"display_name": name.strip(),"created_at": datetime.utcnow().isoformat()}
        db["messages"][user_id] = []
        save_db(db)
    return user_id

def load_messages(user_id: str) -> list[dict]:
    db = load_db()
    return db["messages"].get(user_id, [])

def save_message(user_id: str, role: str, content: str) -> None:
    db = load_db()
    db["messages"].setdefault(user_id, []).append({"role": role,"content": content,"ts": datetime.utcnow().isoformat()})
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
    st.header("Sign in to ROE")
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
    st.subheader("ROE Session")
    if st.button("Sign out"):
        st.session_state.auth_user_id = None
        st.session_state.messages = []
        st.session_state.loaded_history = False
        st.rerun()
    if st.button("Clear my history"):
        if st.session_state.auth_user_id:
            db = load_db()
            db["messages"][st.session_state.auth_user_id] = []
            save_db(db)
            st.session_state.messages = []
            st.success("Deleted chat history.")
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
    "content": ( "You are a psychologist who helps users sharing their problems with you and expecting advice that will improve their life. When answering please consider only the following famous psychologists and psychoanalysts: Wilhelm Wundt, William James, Sigmund Freud, Ivan Pavlov, John B. Watson, B. F. Skinner, Jean Piaget, Carl Rogers, Albert Bandura, Aaron Beck, Carl Jung, Alfred Adler, Erik Erikson, Lev Vygotsky and Abraham Maslow. Only use their schools of thought and advice as a foundation for your answer. No one else. Also leverage the information users share about themselves for a more educated answer. Also in the end of the answer give book references where you based your advice on. In the end ask the user a guided question these authors would think is best to try to get to the bottom of their issue. During the conversation remember their answers and in the end double down on a strategy they can easily pick up and execute after the conversation. And be easy on them. And continually reference these authors." ),}

# ---- Render prior messages ----
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ---- Chat input ----
placeholder_text = "Please share your thoughts!"
if st.session_state.auth_user_id:
    user_display = st.session_state.auth_user_id.split(":", 1)[-1].capitalize()
    placeholder_text = f"{user_display}, please share your thoughts!"


prompt = st.chat_input(placeholder_text)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt, "ts": datetime.utcnow().isoformat()})
    save_message(st.session_state.auth_user_id, "user", prompt)
    with st.chat_message("user", avatar="🧍"):
        st.markdown(prompt)
    # build API messages: system + history
    api_messages = [SYSTEM_PROMPT] + [ {"role": m["role"], "content": m["content"]} for m in st.session_state.messages if m["role"] in ("user", "assistant") ]
    # get/stream assistant reply
    with st.chat_message("assistant", avatar="Roechat.png"):
        stream = client.chat.completions.create( model=st.session_state["openai_model"], messages=api_messages, stream=True, )
        reply = st.write_stream(stream)
    # persist assistant reply
    st.session_state.messages.append({"role": "assistant", "content": reply, "ts": datetime.utcnow().isoformat()})
    save_message(st.session_state.auth_user_id, "assistant", reply)




