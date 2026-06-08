import streamlit as st
import requests
import yaml
import json
import google.generativeai as genai
import smtplib
from email.message import EmailMessage

# 1. Page Configuration
st.set_page_config(page_title="Homework Evaluation Portal", layout="wide")

# Initialize Session State
if "page" not in st.session_state: st.session_state.page = 1
if "email_error" not in st.session_state: st.session_state.email_error = False
if "student_email" not in st.session_state: st.session_state.student_email = ""
if "mc_answers" not in st.session_state: st.session_state.mc_answers = {}
if "la_input" not in st.session_state: st.session_state.la_input = ""
if "grading_results" not in st.session_state: st.session_state.grading_results = None
if "model_used" not in st.session_state: st.session_state.model_used = None

# 2. Data Ingestion (Moved to top so 'quiz_data' is available everywhere)
@st.cache_data(show_spinner="Loading Assignment...")
def fetch_quiz_schema(q_id):
    url = f"https://raw.githubusercontent.com/science-boa/BOA-Quiz/main/quizzes/QUIZ_{q_id}.yaml"
    headers = {}
    if "GITHUB_TOKEN" in st.secrets:
        headers["Authorization"] = f"token {st.secrets['GITHUB_TOKEN']}"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200: return None
        return yaml.safe_load(response.text)
    except Exception: return None

quiz_id = st.query_params.get("quiz", "101")
quiz_data = fetch_quiz_schema(quiz_id)

if quiz_data is None:
    st.error(f"⚠️ Could not load Quiz {quiz_id}. Please check repository settings.")
    st.stop()

# Configure Gemini
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    config = {"response_mime_type": "application/json"}
    model_primary = genai.GenerativeModel('gemini-3.1-flash-lite', generation_config=config)
    model_fallback_1 = genai.GenerativeModel('gemini-3.5-flash', generation_config=config)
    model_fallback_2 = genai.GenerativeModel('gemini-2.5-flash', generation_config=config)

# --- EMAIL FORMATTING LOGIC ---
def send_feedback_email(mc_results, la_data, la_input, grading):
    total_questions = len(quiz_data.get('multiple_choice', []))
    correct_count = sum(1 for item in quiz_data.get('multiple_choice', []) 
                       if mc_results.get(item['question_num']) == item.get('answer'))
    percent = round((correct_count / total_questions) * 100) if total_questions > 0 else 0
    
    body = f"Multiple Choice Score: {percent}%<br><br>"
    for item in quiz_data.get('multiple_choice', []):
        q_num = item['question_num']
        user_ans = mc_results.get(q_num)
        correct = item.get('answer')
        body += f"Question Number: {item['text']}<br>Your Answer: {user_ans}<br>"
        body += "Correct<br><br>" if user_ans == correct else f"The correct answer was: {correct}<br><br>"
            
    body += f"<b>Long Answer</b><br>{la_data.get('text')}<br>Answer: {la_input}<br>Feedback: {grading.get('feedback')}<br>"
    
    sender_email = st.secrets["SMTP_USERNAME"].strip()
    student_email = st.session_state.student_email.strip()
    
    msg_student = EmailMessage()
    msg_student.set_content(body, subtype="html")
    msg_student["Subject"] = f"Feedback: {quiz_data.get('title')}"
    msg_student["From"] = sender_email
    msg_student["To"] = student_email
    
    server = smtplib.SMTP(st.secrets["SMTP_SERVER"], st.secrets["SMTP_PORT"])
    server.starttls()
    server.login(sender_email, st.secrets["SMTP_PASSWORD"])
    server.send_message(msg_student)
    server.quit()

# --- APP UI ---
if st.session_state.page == 3:
    st.title("Assignment Results")
    st.write("Results have been sent to your email.")
else:
    col_left, col_right = st.columns(2)
    with col_left:
        st.title(quiz_data.get("title", "Quiz Portal"))
        if quiz_data.get("video_url"): st.video(quiz_data["video_url"])
        if st.session_state.page == 1:
            st.session_state.student_email = st.text_input("School Email", value=st.session_state.student_email)
        else:
            st.info(f"👤 Student: {st.session_state.student_email}")
            if st.button("Back"): st.session_state.page = 1; st.rerun()

    with col_right:
        if st.session_state.page == 1:
            for item in quiz_data.get("multiple_choice", []):
                q = item["question_num"]
                ans = st.radio(item["text"], [item["A"], item["B"], item["C"], item["D"]], index=None)
                st.session_state.mc_answers[q] = ans
            if st.button("Next"): 
                st.session_state.page = 2; st.rerun()
        else:
            st.session_state.la_input = st.text_area("Your response:", value=st.session_state.la_input)
            if st.button("Submit"):
                # Grading logic here
                st.session_state.page = 3; st.rerun()
