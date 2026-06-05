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

@st.cache_data(show_spinner="Loading Assignment Resource File...")
def fetch_quiz_schema(q_id):
    raw_git_url = f"https://raw.githubusercontent.com/science-boa/BOA-Quiz/main/quizzes/QUIZ_{q_id}.yaml"
    try:
        response = requests.get(raw_git_url)
        if response.status_code == 200:
            return yaml.safe_load(response.text)
    except Exception:
        return None
    return None

quiz_data = fetch_quiz_schema(quiz_id)

# ─── 3. View Interface Architecture Rendering ───
if not quiz_data:
    st.error(f"⚠️ Unable to load Assignment ID: **{quiz_id}**.")
else:
    st.title(quiz_data.get("title", f"Quiz Portal (ID: {quiz_id})"))
    
    col_left, col_right = st.columns([1, 2], gap="large")
    
    # ─── LEFT COLUMN: ANCHORED CONTROLS (Sticky behavior is default) ───
    with col_left:
        st.subheader("📺 Video Source Material")
        if quiz_data.get("video_url") and quiz_data["video_url"].strip() != "":
            st.video(quiz_data["video_url"])
        else:
            st.warning("No video provided.")
        
        st.divider()
        st.subheader("👤 Your Identity Details")
        student_email = st.text_input("Institutional Email:")
        
        st.write("")
        # Submit button is anchored here so it's always available
        submit_trigger = st.button("Finalize and Submit Assignment", type="primary", use_container_width=True)

    # ─── RIGHT COLUMN: SCROLLABLE CONTENT AREA ───
    with col_right:
        st.subheader("📝 Assignment Questions")
        
        mc_user_selections = {}
        
        # Render MC Questions
        if "multiple_choice" in quiz_data and quiz_data["multiple_choice"]:
            st.markdown("### Part 1: Quick-Check Selection Questions")
            for item in quiz_data["multiple_choice"]:
                q_num = item["question_num"]
                st.markdown(f"**Question {q_num}:** {item['text']}")
                options_list = [item["A"], item["B"], item["C"], item["D"]]
                mc_user_selections[q_num] = st.radio(
                    label=f"Options for Q{q_num}",
                    options=options_list,
                    index=None,
                    label_visibility="collapsed",
                    key=f"mc_radio_{q_num}"
                )
                st.write("")
        
        # Render Long Answer Question
        student_long_text = ""
        if "long_answer" in quiz_data and quiz_data["long_answer"]:
            la_data = quiz_data["long_answer"]
            st.divider()
            st.markdown("### Part 2: Long-Form Written Explanation")
            st.markdown(f"**Question {la_data['question_num']}:** {la_data['text']}")
            student_long_text = st.text_area(
                "Type your complete analytical response below:", 
                height=250,
                key="student_long_answer"
            )

# ─── 4. Grading Logic ───
if submit_trigger:
    if not student_email or "@" not in student_email:
        st.error("❌ Submission Failed: You must provide a valid email address.")
    elif "long_answer" in quiz_data and not student_long_text.strip():
        st.error("❌ Submission Failed: Please write a response for the long answer question.")
    else:
        # (Grading and SMTP code remains the same as in your previous file)
        st.success("Submission logic triggered successfully.")
