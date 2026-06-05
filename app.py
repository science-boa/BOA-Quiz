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

# Configure Google Gemini Client
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Missing Gemini API Key configuration.")

TARGET_AUDIT_EMAIL = "science.boa@gmail.com"
quiz_id = st.query_params.get("quiz", "101")

# 2. Data Ingestion
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

# 3. UI Rendering
if not quiz_data:
    st.error(f"⚠️ Unable to load Assignment ID: **{quiz_id}**.")
else:
    st.title(quiz_data.get("title", f"Quiz Portal (ID: {quiz_id})"))
    
    col_left, col_right = st.columns([2, 3], gap="large")
    
    # ─── LEFT COLUMN: ANCHORED CONTROLS ───
    with col_left:
        st.subheader("📺 Video Source Material")
        if quiz_data.get("video_url") and quiz_data["video_url"].strip() != "":
            st.video(quiz_data["video_url"])
        
        st.subheader("👤 Your Identity")
        student_email = st.text_input("Institutional Email:")
        
        # Submit button is anchored on the left
        submit_trigger = st.button("Finalize and Submit Assignment", type="primary", use_container_width=True)

    # ─── RIGHT COLUMN: SCROLLABLE QUESTIONS ───
    with col_right:
        st.subheader("📝 Assignment Questions")
        
        # CSS to ensure the container is scrollable and stable
        st.markdown("""
            <style>
                [data-testid="stVerticalBlock"] > [style*="height: 620px"] {
                    overflow-y: auto !important;
                    display: block !important;
                    padding-right: 15px;
                }
            </style>
        """, unsafe_allow_html=True)
        
        with st.container(height=620):
            mc_user_selections = {}
            
            # Part 1: Multiple Choice
            if "multiple_choice" in quiz_data:
                for item in quiz_data["multiple_choice"]:
                    q_num = item["question_num"]
                    st.markdown(f"**Q{q_num}:** {item['text']}")
                    mc_user_selections[q_num] = st.radio(
                        "Options", [item["A"], item["B"], item["C"], item["D"]],
                        index=None, label_visibility="collapsed", key=f"mc_{q_num}"
                    )
            
            # Part 2: Long Answer
            student_long_text = ""
            if "long_answer" in quiz_data:
                st.divider()
                st.markdown("### Part 2: Long-Form Explanation")
                la_data = quiz_data["long_answer"]
                st.markdown(f"**Q{la_data['question_num']}:** {la_data['text']}")
                student_long_text = st.text_area("Your response:", height=250, key="la_input")

    # 4. Grading Logic (Runs when button on LEFT is clicked)
    if submit_trigger:
        if not student_email or "@" not in student_email:
            st.error("❌ Submission Failed: You must provide a valid email.")
        elif "long_answer" in quiz_data and not student_long_text.strip():
            st.error("❌ Submission Failed: Please write a response for the long answer.")
        else:
            with st.spinner("Processing results..."):
                # (Your existing grading/SMTP logic would be placed here)
                st.success("Assignment processed successfully!")
