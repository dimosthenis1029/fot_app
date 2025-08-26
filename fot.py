from openai import OpenAI
import streamlit as st
import os

# ---- Secrets / API key (env-based) ----
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]  # set in your environment or Streamlit Cloud Secrets

# ---- App UI ----
st.title("AI Psychologist")

client = OpenAI(api_key=OPENAI_API_KEY)

# Model + session state
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-5"

if "messages" not in st.session_state:
    st.session_state.messages = []

# -------- System prompt (hidden from chat UI) --------
SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are an empathetic psychologist. Respond with warmth, validation, and gentle, practical guidance. Be concise, avoid medical diagnoses, suggest reflective questions, and encourage healthy coping strategies. Free feel to use references from psychology literature that students study at graduate school in psychology to guide the user and validate their feelings. Suggest what famous psychologists would advise in an easy, digestible way. Make sure to use the information they provide about themselves."
    ),
}

# Show existing conversation (skip system messages if any ever get added)
for message in st.session_state.messages:
    if message.get("role") == "system":
        continue
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input
if prompt := st.chat_input("Tell me what is on your chest!"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build messages with system prompt PREPENDED (not stored in session)
    api_messages = [SYSTEM_PROMPT] + [
        {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
    ]

    # Stream assistant reply
    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=st.session_state["openai_model"],
            messages=api_messages,
            stream=True,
        )
        response = st.write_stream(stream)
    st.session_state.messages.append({"role": "assistant", "content": response})


