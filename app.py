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
if "grading_results" not in st.session_state: st.session_state.grading_results = None
if "ai_raw_output" not in st.session_state: st.session_state.ai_raw_output = None
if "grading_prompt" not in st.session_state: st.session_state.grading_prompt = None

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

# --- PAGE 3: RESULTS ---
if st.session_state.page == 3:
    st.title("Assignment Results")
    c1, c2 = st.columns([1, 1], gap="large")
    
    with c1:
        st.subheader("Multiple Choice Review")
        for item in quiz_data.get("multiple_choice", []):
            q = item["question_num"]
            ans = st.session_state.mc_answers.get(q)
            correct_ans = item.get("answer", "N/A")
            st.markdown(f"**Q{q}:** {item['text']}")
            st.write(f"Your choice: {ans} | Correct: {correct_ans}")
            if ans != correct_ans: st.error("Incorrect")
            else: st.success("Correct!")
            st.divider()
                
    with c2:
        st.subheader("Long Answer Review")
        la = quiz_data.get("long_answer", {})
        st.write(f"**Score:** {st.session_state.grading_results.get('score', 'N/A')}")
        st.write(f"**Feedback:** {st.session_state.grading_results.get('feedback', 'N/A')}")
    
    if st.button("Close App"): st.stop()

# --- PAGE 2b: GRADING PREVIEW ---
elif st.session_state.page == 2.5:
    st.subheader("Grading Preview")
    st.markdown("### Prompt sent to AI:")
    st.code(st.session_state.grading_prompt)
    
    if st.session_state.ai_raw_output:
        st.markdown("### Raw AI Output:")
        st.code(st.session_state.ai_raw_output)
        if st.button("Proceed to Results"):
            st.session_state.page = 3
            st.rerun()
    else:
        if st.button("Run AI Grading"):
            with st.spinner("Grading..."):
                try:
                    res = model_primary.generate_content(st.session_state.grading_prompt).text
                except:
                    res = model_fallback.generate_content(st.session_state.grading_prompt).text
                
                st.session_state.ai_raw_output = res
                st.session_state.grading_results = json.loads(res)
                st.rerun()

# --- PAGES 1 & 2 ---
else:
    col_left, col_right = st.columns([1, 1], gap="large")
    with col_left:
        st.title(quiz_data.get("title", "Quiz Portal"))
        if st.session_state.page == 1:
            st.text_input("Email", key="student_email")
        else:
            if st.button("Back"):
                st.session_state.page = 1
                st.rerun()

    with col_right:
        if st.session_state.page == 1:
            st.subheader("Part 1: Multiple Choice")
            for item in quiz_data.get("multiple_choice", []):
                q = item["question_num"]
                st.session_state.mc_answers[q] = st.radio(item["text"], [item["A"], item["B"], item["C"], item["D"]], index=None, key=f"mc_{q}")
            if st.button("Next"):
                st.session_state.page = 2
                st.rerun()
        else:
            st.subheader("Part 2: Long Answer")
            la_data = quiz_data.get("long_answer", {})
            la_input = st.text_area("Response", key="la_input")
            if st.button("Submit for Grading"):
                st.session_state.grading_prompt = f"Grade: {la_data.get('rubric')}. Answer: {la_input}. Output JSON keys: 'score', 'feedback'"
                st.session_state.page = 2.5
                st.rerun()
