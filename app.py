import streamlit as st
import requests
import yaml
import json
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

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

# Configure Gemini
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    config = {"response_mime_type": "application/json"}
    model_primary = genai.GenerativeModel('gemini-3.1-flash-lite', generation_config=config)
    model_fallback_1 = genai.GenerativeModel('gemini-3.5-flash', generation_config=config)
    model_fallback_2 = genai.GenerativeModel('gemini-2.5-flash', generation_config=config)

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

# Safety check: Prevent app crash if file is missing or cached as None
if quiz_data is None:
    st.error(f"⚠️ Could not load Quiz {quiz_id}. Please ensure it is pushed to the 'quizzes' folder on GitHub and clear your Streamlit cache.")
    st.stop()

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
        
        body += f"Question Number: {item['text']}<br>"
        body += f"Your Answer: {user_ans}<br>"
        if user_ans == correct:
            body += "Correct<br><br>"
        else:
            body += f"The correct answer was: {correct}<br><br>"
            
    body += "<b>Long Answer Question</b><br>"
    body += f"{la_data.get('text')}<br>"
    body += f"Answer: {la_input}<br>"
    body += f"Feedback: {grading.get('feedback')}<br>"
    
    # Strictly strip and clean all email addresses to prevent SMTP 555 errors
    sender_email = st.secrets["SMTP_USERNAME"].strip()
    student_email = st.session_state.student_email.strip()
    admin_email = "science.boa@gmail.com"
    
    # 1. Prepare Feedback Email for the Student with proper UTF-8 headers and payload
    msg_student = MIMEMultipart()
    msg_student["Subject"] = Header(f"Feedback from quiz {quiz_data.get('title')}", "utf-8")
    msg_student["From"] = sender_email
    msg_student["To"] = student_email
    msg_student.attach(MIMEText(body, "html", "utf-8"))
    
    # 2. Prepare Duplicated Admin Record Email with proper UTF-8 headers and payload
    msg_admin = MIMEMultipart()
    q_id_val = quiz_data.get('quiz_id', quiz_id)
    msg_admin["Subject"] = Header(f"Result-{q_id_val}-{student_email}", "utf-8")
    msg_admin["From"] = sender_email
    msg_admin["To"] = admin_email
    msg_admin.attach(MIMEText(body, "html", "utf-8"))
    
    # Send both messages over a single SMTP connection
    server = smtplib.SMTP(st.secrets["SMTP_SERVER"], st.secrets["SMTP_PORT"])
    server.starttls()
    server.login(sender_email, st.secrets["SMTP_PASSWORD"])
    
    # Send to Student
    server.sendmail(sender_email, [student_email], msg_student.as_string())
    
    # Send to Admin Address
    server.sendmail(sender_email, [admin_email], msg_admin.as_string())
    
    server.quit()

# --- PAGE 3: RESULTS ---
if st.session_state.page == 3:
    st.title("Assignment Results")
    st.caption("You can close this window when ready.")
    st.write("Your results have been calculated and sent to your email.")
    
    col_res_l, col_res_r = st.columns([1, 1], gap="large")
    
    with col_res_l:
        st.subheader("Multiple Choice Review")
        for item in quiz_data.get("multiple_choice", []):
            q_num = item["question_num"]
            user_ans = st.session_state.mc_answers.get(q_num)
            correct = item.get("answer")
            st.markdown(f"**Question {q_num}:** {item['text']}")
            st.write(f"Your Answer: {user_ans}")
            if user_ans == correct:
                st.success("Correct")
            else:
                st.error(f"The correct answer was: {correct}")
                st.caption(f"Explanation: {item.get('explanation')}")
            st.divider()

    with col_res_r:
        st.subheader("Long Answer Feedback")
        la_data = quiz_data.get("long_answer", {})
        st.markdown(f"**Question:** {la_data.get('text')}")
        st.markdown(f"**Your Answer:** {st.session_state.la_input}")
        st.info(f"**AI Feedback:** {st.session_state.grading_results.get('feedback')}")
        st.write(f"**Score:** {st.session_state.grading_results.get('score')}")
        if st.session_state.model_used:
            st.caption(f"Graded using: `{st.session_state.model_used}`")

# --- PAGES 1 & 2 ---
else:
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
                    options = [item["A"], item["B"], item["C"], item["D"]]
                    ans = st.radio(item["text"], options, index=None, key=f"mc_{q}")
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
                if not la_input:
                    st.warning("Please provide an answer.")
                else:
                    with st.spinner("Grading..."):
                        model_status = st.empty()
                        try:
                            prompt = (f"Evaluate: Question: {la_data.get('text')}. Rubric: {la_data.get('rubric')}. "
                                      f"Answer: {la_input}. JSON: {{'score': 0, 'feedback': ''}}")
                            
                            try:
                                model_status.caption("Using model: `gemini-3.1-flash-lite`...")
                                res = model_primary.generate_content(prompt).text
                                active_model = "gemini-3.1-flash-lite"
                            except Exception as e1:
                                try:
                                    model_status.caption("Using fallback model: `gemini-3.5-flash`...")
                                    res = model_fallback_1.generate_content(prompt).text
                                    active_model = "gemini-3.5-flash"
                                except Exception as e2:
                                    model_status.caption("Using fallback model: `gemini-2.5-flash`...")
                                    res = model_fallback_2.generate_content(prompt).text
                                    active_model = "gemini-2.5-flash"
                            
                            grading = json.loads(res)
                            send_feedback_email(st.session_state.mc_answers, la_data, la_input, grading)
                            st.session_state.grading_results = grading
                            st.session_state.model_used = active_model
                            st.session_state.page = 3
                            st.rerun()
                        except Exception as e:
                            st.error(f"Grading/Submission failed: {e}")
