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

# Configure Gemini
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Initialize Page State
if "page" not in st.session_state:
    st.session_state.page = 1

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

# 3. Custom CSS for Styling
st.markdown("""
    <style>
        /* Next button green */
        div.stButton > button[kind="primary"]#next_btn {
            background-color: #22c55e !important;
            color: white !important;
        }
        /* Back button green (Updated) */
        div.stButton > button#back_btn {
            background-color: #22c55e !important;
            color: white !important;
        }
        /* Submit button red */
        div.stButton > button[kind="primary"]#submit_btn {
            background-color: #ef4444 !important;
            color: white !important;
        }
        /* Email box outline */
        .stTextInput > div > div > input {
            border: 2px solid #333 !important;
            border-radius: 4px;
        }
    </style>
""", unsafe_allow_html=True)

# Layout
col_left, col_right = st.columns([1, 1], gap="large")

# --- LEFT PANEL ---
with col_left:
    st.title(quiz_data.get("title", "Quiz Portal"))
    if quiz_data.get("video_url"):
        st.video(quiz_data["video_url"])
    
    if st.session_state.page == 1:
        st.markdown("**Enter your school email**")
        student_email = st.text_input("", key="email_input", label_visibility="collapsed")
    else:
        # Green Back button
        if st.button("Back", key="back_btn"):
            st.session_state.page = 1
            st.rerun()

# --- RIGHT PANEL ---
with col_right:
    if st.session_state.page == 1:
        st.subheader("Part 1: Multiple Choice")
        
        with st.container(height=650):
            for item in quiz_data.get("multiple_choice", []):
                q_num = item["question_num"]
                st.markdown(f"**Q{q_num}:** {item['text']}")
                st.radio("Options", [item["A"], item["B"], item["C"], item["D"]], 
                         index=None, label_visibility="collapsed", key=f"mc_{q_num}")
                st.write("")
            
            if st.button("Next", type="primary", key="next_btn", use_container_width=True):
                st.session_state.page = 2
                st.rerun()
    
    else:
        st.subheader("Part 2: Long Answer")
        la_data = quiz_data.get("long_answer", {})
        st.markdown(f"**Q{la_data.get('question_num')}:** {la_data.get('text')}")
        student_long_text = st.text_area("Your response:", height=300, key="la_input")
        
        # Red Submit button
        if st.button("Submit Assignment", type="primary", key="submit_btn"):
            st.success("Assignment submitted!")
