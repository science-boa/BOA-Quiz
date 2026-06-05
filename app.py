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
if "email_error" not in st.session_state: st.session_state.email_error = False
if "student_email" not in st.session_state: st.session_state.student_email = ""
if "mc_answers" not in st.session_state: st.session_state.mc_answers = {}

# Configure Gemini
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    config = {"response_mime_type": "application/json"}
    model_primary = genai.GenerativeModel('gemini-3.5-flash', generation_config=config)
    model_fallback = genai.GenerativeModel('gemini-2.5-flash', generation_config=config)

# 2. Data Ingestion
@st.cache_data(show_spinner="Loading Assignment...")
def fetch_quiz_schema(q_id):
    url = f"https://raw.githubusercontent.com/science-boa/BOA-Quiz/main/quizzes/QUIZ_{q_id}.yaml"
    try:
        response = requests.get(url)
        return yaml.safe_load(response.text) if response.status_code == 200 else None
    except: return None

quiz_id = st.query_params.get("quiz", "101")
quiz_data = fetch_quiz_schema(quiz_id)

if not quiz_data:
    st.error("Unable to load quiz data.")
    st.stop()

# Layout
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.title(quiz_data.get("title", "Quiz Portal"))
    if quiz_data.get("video_url"): st.video(quiz_data["video_url"])
    
    if st.session_state.page == 1:
        st.markdown("**Enter your school email**")
        st.text_input("", key="student_email", label_visibility="collapsed")
        if st.session_state.email_error: st.warning("⚠️ Enter a valid email.")
    else:
        if st.button("Back", key="back_btn"):
            st.session_state.page = 1
            st.rerun()

with col_right:
    if st.session_state.page == 1:
        st.subheader("Part 1: Multiple Choice")
        with st.container(height=650):
            for item in quiz_data.get("multiple_choice", []):
                q = item["question_num"]
                # Display radio and save selection to session state
                ans = st.radio(item["text"], ["A", "B", "C", "D"], index=None, key=f"mc_{q}")
                st.session_state.mc_answers[q] = ans
            
            if st.button("Next", type="primary", key="next_btn", use_container_width=True):
                if not st.session_state.student_email or "@" not in st.session_state.student_email:
                    st.session_state.email_error = True
                    st.rerun()
                else:
                    st.session_state.email_error = False
                    st.session_state.page = 2
                    st.rerun()
    else:
        st.subheader("Part 2: Long Answer")
        la_data = quiz_data.get("long_answer", {})
        st.markdown(la_data.get("text", ""))
        la_input = st.text_area("Your response:", key="la_input")
        
        if st.button("Submit Assignment", type="primary", key="submit_btn"):
            with st.spinner("Grading..."):
                try:
                    prompt = f"Rubric: {la_data.get('rubric')}. Resp: {la_input}. Output JSON: {{'score': 0, 'feedback': ''}}"
                    try:
                        ai_response = model_primary.generate_content(prompt).text
                    except Exception as e:
                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                            ai_response = model_fallback.generate_content(prompt).text
                        else:
                            raise e
                    
                    grading = json.loads(ai_response)
                    
                    # SMTP Dispatch
                    msg = MIMEMultipart()
                    msg["Subject"] = f"Assignment Results: {quiz_data['title']}"
                    msg["To"] = st.session_state.student_email
                    msg.attach(MIMEText(f"Your score: {grading['score']}<br>Feedback: {grading['feedback']}", "html"))
                    
                    server = smtplib.SMTP(st.secrets["SMTP_SERVER"], st.secrets["SMTP_PORT"])
                    server.starttls()
                    server.login(st.secrets["SMTP_USERNAME"], st.secrets["SMTP_PASSWORD"])
                    server.sendmail(st.secrets["SMTP_USERNAME"], [st.session_state.student_email, "science.boa@gmail.com"], msg.as_string())
                    server.quit()
                    
                    st.success("🎉 Assignment submitted! Results sent to your email.")
                except Exception as e:
                    st.error(f"Submission failed: {str(e)}")
