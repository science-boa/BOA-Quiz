import streamlit as st
import requests
import yaml
import json
from google import genai
from google.genai import types
import smtplib
from email.message import EmailMessage

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

# Configure Gemini using the modern google-genai SDK
ai_client = None
if "GEMINI_API_KEY" in st.secrets:
    # Initialize the modern unified GenAI client
    ai_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

# 2. Data Ingestion (With GitHub Authentication & Robust Diagnostics)
@st.cache_data(show_spinner="Loading Assignment...")
def fetch_quiz_schema(q_id):
    q_id_str = str(q_id).strip()
    candidates = []
    
    # Generate variations of the quiz ID to circumvent raw.githubusercontent's strict case sensitivity
    variations = [q_id_str]
    if q_id_str.upper() not in variations:
        variations.append(q_id_str.upper())
    if q_id_str.lower() not in variations:
        variations.append(q_id_str.lower())
        
    # Combine variations with potential extensions and prefixes
    for var in variations:
        for ext in ["yaml", "yml"]:
            for prefix in ["QUIZ_", "quiz_"]:
                filename = f"{prefix}{var}.{ext}"
                if filename not in candidates:
                    candidates.append(filename)
                    
    headers = {}
    if "GITHUB_TOKEN" in st.secrets:
        headers["Authorization"] = f"token {st.secrets['GITHUB_TOKEN']}"
        
    errors = []
    for filename in candidates:
        url = f"https://raw.githubusercontent.com/science-boa/BOA-Quiz/main/quizzes/{filename}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                try:
                    # Attempt parsing the schema structure
                    data = yaml.safe_load(response.text)
                    return {"data": data, "errors": None}
                except Exception as parse_err:
                    errors.append(f"{filename} ➡️ YAML Parsing Error: {str(parse_err)}")
            else:
                errors.append(f"{filename} ➡️ HTTP Status {response.status_code}")
        except Exception as conn_err:
            errors.append(f"{filename} ➡️ Connection Error: {str(conn_err)}")
            
    return {"data": None, "errors": errors}

# Robust case-insensitive query parameter extraction
raw_params = st.query_params
quiz_id = None
for key in raw_params:
    if key.lower() == "quiz":
        val = raw_params[key]
        if isinstance(val, list):
            quiz_id = val[0] if val else None
        else:
            quiz_id = val
        break

# If no quiz ID is provided in the URL, don't silently default to "101"
if not quiz_id:
    st.warning("📋 No Quiz Specified")
    st.markdown("""
    To view a specific homework assignment, please append `?quiz=YOUR_QUIZ_CODE` to the URL.
    
    **Alternatively, you can manually enter your Quiz ID below to load the portal:**
    """)
    
    manual_input = st.text_input("Enter Quiz ID (e.g., B101, 101):", placeholder="B101")
    if st.button("Load Quiz", type="primary"):
        if manual_input.strip():
            st.query_params["quiz"] = manual_input.strip()
            st.rerun()
    st.stop()

# Fetch the specified quiz
quiz_result = fetch_quiz_schema(quiz_id)
quiz_data = quiz_result.get("data")

# Safety check: Prevent app crash if file is missing or cached as None
if quiz_data is None:
    st.error(f"⚠️ Could not load Quiz '{quiz_id}'.")
    st.markdown("### 🔍 Live Fetch Diagnostics")
    st.write("We attempted to fetch the quiz file from your GitHub repository using multiple variations, but all attempts failed:")
    for err in quiz_result.get("errors", []):
        st.code(err)
    st.info("💡 **Common Troubleshooting Steps:**\n\n"
            "1. **Confirm File Path:** Is the quiz document pushed to the `quizzes` folder in the `main` branch of `science-boa/BOA-Quiz`?\n"
            "2. **Check File Extension:** Is it saved exactly as a `.yaml` or `.yml` file (all lowercase)?\n"
            "3. **YAML Syntax Validation:** If you see a `YAML Parsing Error` above, your quiz file has an indentation or spacing mismatch. Correcting the formatting in your IDE and pushing it will solve the problem.\n"
            "4. **Private Repository Token:** If the repository is private, verify your Streamlit `GITHUB_TOKEN` secret is configured correctly.")
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
    
    sender_email = st.secrets["SMTP_USERNAME"].strip()
    student_email = st.session_state.student_email.strip()
    admin_email = "science.boa@gmail.com"
    
    # 1. Prepare Feedback Email using modern EmailMessage class
    msg_student = EmailMessage()
    msg_student.set_content(body, subtype="html")
    msg_student["Subject"] = f"Feedback from quiz {quiz_data.get('title')}"
    msg_student["From"] = sender_email
    msg_student["To"] = student_email
    
    # 2. Prepare Duplicated Admin Record Email
    msg_admin = EmailMessage()
    msg_admin.set_content(body, subtype="html")
    q_id_val = quiz_data.get('quiz_id', quiz_id)
    msg_admin["Subject"] = f"Result-{q_id_val}-{student_email}"
    msg_admin["From"] = sender_email
    msg_admin["To"] = admin_email
    
    # Send both messages using the safe send_message method
    server = smtplib.SMTP(st.secrets["SMTP_SERVER"], st.secrets["SMTP_PORT"])
    server.starttls()
    server.login(sender_email, st.secrets["SMTP_PASSWORD"])
    
    # send_message extracts the raw envelope paths cleanly, avoiding 555 errors
    server.send_message(msg_student)
    server.send_message(msg_admin)
    
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
            
            # Decoupled Widget: key="email_widget" prevents Streamlit from deleting "student_email"
            email_val = st.text_input("School Email Address", value=st.session_state.student_email, key="email_widget", label_visibility="collapsed")
            st.session_state.student_email = email_val
            
            if st.session_state.email_error: st.warning("⚠️ Enter a valid email.")
        else:
            # Display the collected student email on Page 2
            st.info(f"👤 **Student:** {st.session_state.student_email}")
            
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
                    ans = st.radio(item["text"], options, index=None, key=f"mc_widget_{q}")
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
            
            # Decoupled Widget: Prevents the answer from disappearing on Page 3
            la_val = st.text_area("Your response:", value=st.session_state.la_input, key="la_widget")
            st.session_state.la_input = la_val
            
            if st.button("Submit Assignment", type="primary", key="submit_btn"):
                if not st.session_state.la_input:
                    st.warning("Please provide an answer.")
                elif ai_client is None:
                    st.error("⚠️ AI Evaluation Service is currently unconfigured. Please ensure GEMINI_API_KEY is present in your Streamlit secrets.")
                else:
                    with st.spinner("Grading..."):
                        model_status = st.empty()
                        try:
                            prompt = (f"Evaluate: Question: {la_data.get('text')}. Rubric: {la_data.get('rubric')}. "
                                      f"Answer: {st.session_state.la_input}. JSON: {{'score': 0, 'feedback': ''}}")
                            
                            # Construct GenerateContentConfig using the modern google-genai structures
                            gen_config = types.GenerateContentConfig(
                                response_mime_type="application/json"
                            )
                            
                            try:
                                model_status.caption("Using model: `gemini-2.5-flash`...")
                                response = ai_client.models.generate_content(
                                    model='gemini-2.5-flash',
                                    contents=prompt,
                                    config=gen_config
                                )
                                res = response.text
                                active_model = "gemini-2.5-flash"
                            except Exception as e1:
                                try:
                                    model_status.caption("Using fallback model: `gemini-2.5-pro`...")
                                    response = ai_client.models.generate_content(
                                        model='gemini-2.5-pro',
                                        contents=prompt,
                                        config=gen_config
                                    )
                                    res = response.text
                                    active_model = "gemini-2.5-pro"
                                except Exception as e2:
                                    model_status.caption("Using fallback model: `gemini-1.5-flash`...")
                                    response = ai_client.models.generate_content(
                                        model='gemini-1.5-flash',
                                        contents=prompt,
                                        config=gen_config
                                    )
                                    res = response.text
                                    active_model = "gemini-1.5-flash"
                            
                            grading = json.loads(res)
                            send_feedback_email(st.session_state.mc_answers, la_data, st.session_state.la_input, grading)
                            st.session_state.grading_results = grading
                            st.session_state.model_used = active_model
                            st.session_state.page = 3
                            st.rerun()
                        except Exception as e:
                            st.error(f"Grading/Submission failed: {e}")
