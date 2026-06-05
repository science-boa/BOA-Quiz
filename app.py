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

# Configure Gemini 3.5 Flash
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-3.5-flash')
else:
    st.error("Missing Gemini API Key.")

# State Management
if "page" not in st.session_state: st.session_state.page = 1
if "email_error" not in st.session_state: st.session_state.email_error = False

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

# 3. Styling
border_color = "#ef4444" if st.session_state.email_error else "#333"
st.markdown(f"""
    <style>
        #next_btn {{ background-color: #22c55e !important; color: white !important; }}
        #back_btn {{ background-color: #22c55e !important; color: white !important; }}
        #submit_btn {{ background-color: #ef4444 !important; color: white !important; }}
        .stTextInput > div > div > input {{ border: 2px solid {border_color} !important; }}
    </style>
""", unsafe_allow_html=True)

# Layout
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.title(quiz_data.get("title", "Quiz Portal"))
    if quiz_data.get("video_url"): st.video(quiz_data["video_url"])
    
    if st.session_state.page == 1:
        st.markdown("**Enter your school email**")
        student_email = st.text_input("", key="email_input", label_visibility="collapsed")
        if st.session_state.email_error: st.warning("⚠️ Please enter a valid school email.")
    else:
        if st.button("Back", key="back_btn"):
            st.session_state.page = 1
            st.rerun()

with col_right:
    if st.session_state.page == 1:
        st.subheader("Part 1: Multiple Choice")
        with st.container(height=650):
            mc_answers = {}
            for item in quiz_data.get("multiple_choice", []):
                q_num = item["question_num"]
                st.markdown(f"**Q{q_num}:** {item['text']}")
                mc_answers[q_num] = st.radio("Options", [item["A"], item["B"], item["C"], item["D"]], 
                                            index=None, label_visibility="collapsed", key=f"mc_{q_num}")
            
            if st.button("Next", type="primary", key="next_btn", use_container_width=True):
                if not student_email or "@" not in student_email:
                    st.session_state.email_error = True
                    st.rerun()
                else:
                    st.session_state.page = 2
                    st.rerun()
    
    else:
        st.subheader("Part 2: Long Answer")
        la_data = quiz_data.get("long_answer", {})
        st.markdown(f"**Q{la_data.get('question_num')}:** {la_data.get('text')}")
        student_long_text = st.text_area("Your response:", height=300, key="la_input")
        
     if st.button("Submit Assignment", type="primary", key="submit_btn"):
            with st.spinner("Grading..."):
                # 1. Improved Prompt for Strict JSON
                prompt = f"""
                Grade the student response for '{la_data['text']}'. 
                Rubric: {la_data.get('rubric', 'General evaluation')}. 
                Response: {student_long_text}. 
                
                CRITICAL: Return ONLY raw JSON. No markdown, no backticks, no conversational text.
                Format: {{"score": 0, "feedback": "your feedback here"}}
                """
                
                ai_response = model.generate_content(prompt).text
                
                # 2. Cleanup & Parsing
                try:
                    # Remove potential markdown code blocks
                    cleaned_response = ai_response.replace("```json", "").replace("```", "").strip()
                    grading = json.loads(cleaned_response)
                    
                    # 3. SMTP Dispatch (Ensure your credentials are in st.secrets)
                    msg = MIMEMultipart()
                    msg["Subject"] = f"Assignment Results: {quiz_data['title']}"
                    msg["To"] = st.session_state.email_input
                    body = f"Your score: {grading['score']}<br>Feedback: {grading['feedback']}"
                    msg.attach(MIMEText(body, "html"))
                    
                    # ... [Insert your existing smtplib logic here] ...
                    
                    st.success("🎉 Assignment submitted! Results sent to your email.")
                    
                except json.JSONDecodeError:
                    st.error("The AI returned an invalid response. Please try submitting again.")
                    st.code(ai_response) # Shows you exactly what the AI returned so we can debug
