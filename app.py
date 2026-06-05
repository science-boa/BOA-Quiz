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

# 3. CSS
st.markdown("""
    <style>
        #next_btn { background-color: #22c55e !important; color: white !important; }
        #back_btn { background-color: #22c55e !important; color: white !important; }
        #submit_btn { background-color: #ef4444 !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

# Main Logic Flow
if st.session_state.page == 3:
    st.title("Assignment Results")
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.subheader("Multiple Choice Review")
        with st.container(height=600):
            for item in quiz_data.get("multiple_choice", []):
                q_num = item["question_num"]
                user_ans = st.session_state.mc_answers.get(q_num)
                correct_ans = item["correct"]
                st.markdown(f"**Q{q_num}:** {item['text']}")
                st.write(f"Your choice: {user_ans}")
                if user_ans == correct_ans:
                    st.success("Correct!")
                else:
                    st.error(f"Incorrect. Correct answer: {correct_ans}")
                    st.info(f"Explanation: {item.get('explanation', 'No explanation provided.')}")
                st.divider()

    with col2:
        st.subheader("Long Answer Review")
        la = quiz_data.get("long_answer", {})
        st.markdown(f"**Q:** {la.get('text')}")
        st.info(f"Your response: {st.session_state.get('la_input', 'N/A')}")
        if st.session_state.grading_results:
            st.markdown(f"**Rubric:** {la.get('rubric')}")
            st.write(f"**Score:** {st.session_state.grading_results['score']}")
            st.write(f"**Feedback:** {st.session_state.grading_results['feedback']}")
    
    if st.button("Close App"):
        st.write("You may now close this tab.")

else:
    # Pages 1 & 2 Logic...
    col_left, col_right = st.columns([1, 1], gap="large")
    with col_left:
        # [Render Quiz Title/Video/Email/Back button as before]
        pass
    with col_right:
        # [Render MC (Page 1) or LA (Page 2) as before]
        # In Page 2 Submit Button:
        # st.session_state.grading_results = grading
        # st.session_state.page = 3
        # st.rerun()
        pass
