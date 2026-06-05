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

# 2. State & Config Init
if "page" not in st.session_state: st.session_state.page = 1
if "email_error" not in st.session_state: st.session_state.email_error = False
if "mc_answers" not in st.session_state: st.session_state.mc_answers = {}
if "grading_results" not in st.session_state: st.session_state.grading_results = None

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    config = {"response_mime_type": "application/json"}
    model_primary = genai.GenerativeModel('gemini-3.5-flash', generation_config=config)
    model_fallback = genai.GenerativeModel('gemini-2.5-flash', generation_config=config)

# 3. Data
@st.cache_data(show_spinner="Loading...")
def fetch_quiz_schema(q_id):
    url = f"https://raw.githubusercontent.com/science-boa/BOA-Quiz/main/quizzes/QUIZ_{q_id}.yaml"
    try:
        response = requests.get(url)
        return yaml.safe_load(response.text)
    except: return None

quiz_id = st.query_params.get("quiz", "101")
quiz_data = fetch_quiz_schema(quiz_id)

if not quiz_data:
    st.error("Invalid Quiz ID.")
    st.stop()

# 4. Styling
st.markdown("""<style>
    #next_btn, #back_btn { background-color: #22c55e !important; color: white !important; }
    #submit_btn { background-color: #ef4444 !important; color: white !important; }
</style>""", unsafe_allow_html=True)

# 5. Routing
if st.session_state.page == 3:
    st.title("Assignment Results")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(height=600):
            for item in quiz_data.get("multiple_choice", []):
                q = item["question_num"]
                ans = st.session_state.mc_answers.get(q)
                st.write(f"**Q{q}:** {item['text']}")
                st.write(f"Your answer: {ans} | Correct: {item['correct']}")
                if ans != item['correct']: st.warning(f"Exp: {item.get('explanation')}")
                st.divider()
    with c2:
        res = st.session_state.grading_results
        st.write(f"**Score:** {res.get('score')}")
        st.write(f"**Feedback:** {res.get('feedback')}")
    if st.button("Close"): st.info("You may close the tab.")

else:
    col_left, col_right = st.columns(2)
    with col_left:
        st.title(quiz_data.get("title"))
        st.video(quiz_data.get("video_url"))
        if st.session_state.page == 1:
            st.text_input("Enter your school email", key="student_email")
        elif st.button("Back", key="back_btn"):
            st.session_state.page = 1; st.rerun()

    with col_right:
        if st.session_state.page == 1:
            with st.container(height=600):
                for item in quiz_data.get("multiple_choice", []):
                    q = item["question_num"]
                    st.session_state.mc_answers[q] = st.radio(item["text"], ["A", "B", "C", "D"], index=None, key=f"r{q}")
                if st.button("Next", type="primary", key="next_btn"):
                    if not st.session_state.get("student_email"): st.session_state.email_error = True
                    else: st.session_state.page = 2; st.rerun()
        else:
            la_data = quiz_data.get("long_answer", {})
            st.write(la_data.get("text"))
            la_text = st.text_area("Response", key="la_input")
            if st.button("Submit", type="primary", key="submit_btn"):
                with st.spinner("Grading..."):
                    try:
                        prompt = f"Rubric: {la_data.get('rubric')}. Resp: {la_text}. Output JSON: {{'score': 0, 'feedback': ''}}"
                        try: res = model_primary.generate_content(prompt).text
                        except: res = model_fallback.generate_content(prompt).text
                        st.session_state.grading_results = json.loads(res)
                        st.session_state.page = 3; st.rerun()
                    except Exception as e: st.error(str(e))
