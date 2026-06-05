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

if not quiz_data:
    st.error("Unable to load quiz data.")
    st.stop()

# 3. CSS Styling
st.markdown("""
    <style>
        #next_btn { background-color: #22c55e !important; color: white !important; }
        #back_btn { background-color: #22c55e !important; color: white !important; }
        #submit_btn { background-color: #ef4444 !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

# --- PAGE 3: RESULTS ---
if st.session_state.page == 3:
    st.title("Assignment Results")
    c1, c2 = st.columns([1, 1], gap="large")
    
    with c1:
        st.subheader("Multiple Choice Review")
        with st.container(height=600):
            for item in quiz_data.get("multiple_choice", []):
                q = item["question_num"]
                ans = st.session_state.mc_answers.get(q)
                st.markdown(f"**Q{q}:** {item['text']}")
                st.write(f"Your choice: {ans} | Correct: {item['correct']}")
                if ans != item['correct']:
                    st.error(f"Explanation: {item.get('explanation', 'No explanation provided.')}")
                else:
                    st.success("Correct!")
                st.divider()
                
    with c2:
        st.subheader("Long Answer Review")
        la = quiz_data.get("long_answer", {})
        st.markdown(f"**Question:** {la.get('text')}")
        st.info(f"Your response: {st.session_state.get('la_input', 'N/A')}")
        if st.session_state.grading_results:
            st.markdown(f"**Rubric:** {la.get('rubric')}")
            st.write(f"**Score:** {st.session_state.grading_results.get('score')}")
            st.write(f"**Feedback:** {st.session_state.grading_results.get('feedback')}")
    
    if st.button("Close App"):
        st.write("You may now close this tab.")

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
                        try: res = model_primary.generate_content(prompt).text
                        except: res = model_fallback.generate_content(prompt).text
                        
                        st.session_state.grading_results = json.loads(res)
                        
                        # SMTP Logic
                        msg = MIMEMultipart()
                        msg["Subject"] = f"Assignment Results: {quiz_data['title']}"
                        msg["To"] = st.session_state.student_email
                        msg.attach(MIMEText(f"Your score: {st.session_state.grading_results.get('score')}<br>Feedback: {st.session_state.grading_results.get('feedback')}", "html"))
                        
                        server = smtplib.SMTP(st.secrets["SMTP_SERVER"], st.secrets["SMTP_PORT"])
                        server.starttls()
                        server.login(st.secrets["SMTP_USERNAME"], st.secrets["SMTP_PASSWORD"])
                        server.sendmail(st.secrets["SMTP_USERNAME"], [st.session_state.student_email, "science.boa@gmail.com"], msg.as_string())
                        server.quit()
                        
                        st.session_state.page = 3
                        st.rerun()
                    except Exception as e:
                        st.error(f"Submission failed: {e}")
