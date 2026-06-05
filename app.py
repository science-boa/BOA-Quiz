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

# 3. Custom CSS for Green Button & Balanced Layout
st.markdown("""
    <style>
        /* Make 'Next' button green */
        div.stButton > button[kind="primary"] {
            background-color: #22c55e !important;
            color: white !important;
        }
        /* Fix column spacing */
        .stColumn { padding: 10px; }
    </style>
""", unsafe_allow_html=True)

# Layout: Equal widths (1:1)
col_left, col_right = st.columns([1, 1], gap="large")

# --- LEFT PANEL (Common to both pages) ---
with col_left:
    st.title(quiz_data.get("title", "Quiz Portal"))
    if quiz_data.get("video_url"):
        st.video(quiz_data["video_url"])
    
    if st.session_state.page == 1:
        student_email = st.text_input("Institutional Email:", key="email_input")
    else:
        if st.button("⬅️ Back to Multiple Choice"):
            st.session_state.page = 1
            st.rerun()

# --- RIGHT PANEL (Page dependent) ---
with col_right:
    # PAGE 1: SCROLLABLE MULTIPLE CHOICE
    if st.session_state.page == 1:
        st.subheader("📝 Part 1: Multiple Choice")
        
        # Scrollable container
        with st.container(height=650):
            for item in quiz_data.get("multiple_choice", []):
                q_num = item["question_num"]
                st.markdown(f"**Q{q_num}:** {item['text']}")
                st.radio("Options", [item["A"], item["B"], item["C"], item["D"]], 
                         index=None, label_visibility="collapsed", key=f"mc_{q_num}")
                st.write("")
            
            # Next button at the bottom of the scrollable panel
            if st.button("Next: Long Answer ➡️", type="primary", use_container_width=True):
                st.session_state.page = 2
                st.rerun()
    
    # PAGE 2: NON-SCROLLABLE LONG ANSWER
    else:
        st.subheader("📝 Part 2: Long Answer")
        la_data = quiz_data.get("long_answer", {})
        st.markdown(f"**Q{la_data.get('question_num')}:** {la_data.get('text')}")
        student_long_text = st.text_area("Your response:", height=300, key="la_input")
        
        if st.button("Submit Assignment", type="primary"):
            st.success("Assignment submitted!")
