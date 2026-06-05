import streamlit as st
import requests
import yaml
import json
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 1. Page Configuration
st.set_page_config(page_title="Homework Evaluation Portal", layout="wide")

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

TARGET_AUDIT_EMAIL = "science.boa@gmail.com"
quiz_id = st.query_params.get("quiz", "101")

@st.cache_data(ttl=1)
def fetch_quiz_schema(q_id):
    paths = [f"https://raw.githubusercontent.com/science-boa/BOA-Quiz/main/quizzes/QUIZ_{q_id}.yaml",
             f"https://raw.githubusercontent.com/science-boa/BOA-Quiz/main/quizs/QUIZ_{q_id}.yaml"]
    for url in paths:
        try:
            r = requests.get(url)
            if r.status_code == 200: return yaml.safe_load(r.text)
        except: pass
    return None

quiz_data = fetch_quiz_schema(quiz_id)

# ─── LEFT COLUMN: ANCHORED (No scrolling) ───
col_left, col_right = st.columns([1, 2], gap="large")

with col_left:
    st.subheader("📺 Video Material")
    if quiz_data and quiz_data.get("video_url"):
        st.video(quiz_data["video_url"])
    
    st.markdown("---")
    st.subheader("👤 Submission")
    student_email = st.text_input("Institutional Email:")
    
    # SUBMIT BUTTON MOVED TO LEFT COLUMN
    submit_trigger = st.button("Finalize and Submit Assignment", type="primary", use_container_width=True)

# ─── RIGHT COLUMN: SCROLLABLE ───
with col_right:
    if not quiz_data:
        st.error("Quiz data not found.")
    else:
        st.title(quiz_data.get("title", "Quiz"))
        
        # We wrap ONLY the questions in the container
        with st.container(height=700):
            mc_user_selections = {}
            
            if "multiple_choice" in quiz_data:
                st.subheader("Part 1: Multiple Choice")
                for item in quiz_data["multiple_choice"]:
                    q_num = item["question_num"]
                    st.markdown(f"**Q{q_num}:** {item['text']}")
                    mc_user_selections[q_num] = st.radio(
                        label="Options", options=[item["A"], item["B"], item["C"], item["D"]],
                        index=None, label_visibility="collapsed", key=f"mc_{q_num}"
                    )
            
            student_long_text = ""
            if "long_answer" in quiz_data:
                st.subheader("Part 2: Long Answer")
                st.markdown(f"**Q{quiz_data['long_answer']['question_num']}:** {quiz_data['long_answer']['text']}")
                student_long_text = st.text_area("Your response:", height=250, key="la_input")

# ─── GRADING LOGIC (Runs when button on LEFT is clicked) ───
if submit_trigger:
    if not student_email:
        st.error("Please enter your email.")
    elif not student_long_text:
        st.error("Please fill in the long answer.")
    else:
        with st.spinner("Grading..."):
            # (Insert your existing Grading/SMTP logic here)
            st.success("Assignment submitted successfully!")
