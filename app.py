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

# Initialize Session State
if "page" not in st.session_state: st.session_state.page = 1
if "student_email" not in st.session_state: st.session_state.student_email = ""
if "mc_answers" not in st.session_state: st.session_state.mc_answers = {}
if "grading_results" not in st.session_state: st.session_state.grading_results = None

# Configure Gemini
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    config = {"response_mime_type": "application/json"}
    model_primary = genai.GenerativeModel('gemini-1.5-flash', generation_config=config)
    model_fallback = genai.GenerativeModel('gemini-2.0-flash', generation_config=config)

# Data Ingestion
@st.cache_data(show_spinner="Loading Assignment...")
def fetch_quiz_schema(q_id):
    url = f"https://raw.githubusercontent.com/science-boa/BOA-Quiz/main/quizzes/QUIZ_{q_id}.yaml"
    try:
        response = requests.get(url)
        return yaml.safe_load(response.text) if response.status_code == 200 else None
    except: return None

quiz_id = st.query_params.get("quiz", "101")
quiz_data = fetch_quiz_schema(quiz_id)

# --- EMAIL FORMATTING LOGIC ---
def send_feedback_email(mc_results, la_data, la_input, grading):
    total_questions = len(quiz_data.get('multiple_choice', []))
    correct_count = sum(1 for item in quiz_data.get('multiple_choice', []) 
                       if mc_results.get(item['question_num']) == item.get('correct'))
    
    percent = round((correct_count / total_questions) * 100) if total_questions > 0 else 0
    
    body = f"Multiple Choice Score: {percent}%<br><br>"
    
    for item in quiz_data.get('multiple_choice', []):
        q_num = item['question_num']
        user_ans = mc_results.get(q_num)
        correct = item.get('correct')
        # Display the full question text and the answer option chosen
        body += f"Question Number: {item['text']}<br>"
        body += f"Your Answer: {user_ans}<br>"
        if user_ans == correct:
            body += "Correct<br><br>"
        else:
            body += f"The correct answer was: {correct}<br><br>"
            
    body += "<b>Long Answer Question</b><br>"
    body += f"{la_data.get('text')}<br>"
    body += f"Their Answer: {la_input}<br>"
    body += f"Feedback: {grading.get('feedback')}<br>"
    
    msg = MIMEMultipart()
    msg["Subject"] = f"Feedback from quiz {quiz_data.get('title')}"
    msg["To"] = st.session_state.student_email
    msg.attach(MIMEText(body, "html"))
    
    server = smtplib.SMTP(st.secrets["SMTP_SERVER"], st.secrets["SMTP_PORT"])
    server.starttls()
    server.login(st.secrets["SMTP_USERNAME"], st.secrets["SMTP_PASSWORD"])
    server.sendmail(st.secrets["SMTP_USERNAME"], [st.session_state.student_email, "science.boa@gmail.com"], msg.as_string())
    server.quit()

# --- APP LOGIC ---
if st.session_state.page == 3:
    st.title("Assignment Results")
    st.write("Results have been sent to your email.")
    if st.button("Close"): st.stop()

elif st.session_state.page == 2:
    st.subheader("Part 2: Long Answer")
    la_data = quiz_data.get("long_answer", {})
    la_input = st.text_area("Your response:")
    if st.button("Submit Assignment"):
        prompt = f"Rubric: {la_data.get('rubric')}. Answer: {la_input}. Return JSON: {{'score': 0, 'feedback': ''}}"
        try:
            res = model_primary.generate_content(prompt).text
            grading = json.loads(res)
            st.session_state.grading_results = grading
            send_feedback_email(st.session_state.mc_answers, la_data, la_input, grading)
            st.session_state.page = 3
            st.rerun()
        except Exception as e: st.error(f"Error: {e}")

else:
    st.title(quiz_data.get("title"))
    st.text_input("Email", key="student_email")
    for item in quiz_data.get("multiple_choice", []):
        q = item["question_num"]
        options = [item["A"], item["B"], item["C"], item["D"]]
        st.session_state.mc_answers[q] = st.radio(item["text"], options, index=None, key=f"mc_{q}")
    if st.button("Next"):
        st.session_state.page = 2
        st.rerun()
