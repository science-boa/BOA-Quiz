import streamlit as st
import requests
import yaml
import json
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 1. Page Configuration & Aesthetic Setup
st.set_page_config(page_title="Homework Evaluation Portal", layout="wide")

# Configure Google Gemini Client from secure backend parameters
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Missing Gemini API Key configuration.")

# Hardcoded Target Email Sink for Database Capture
TARGET_AUDIT_EMAIL = "science.boa@gmail.com"

# 2. Dynamic Git Data Layer Ingestion
quiz_id = st.query_params.get("quiz", "101")

# Set cache TTL to 1 second so updates are pulled from GitHub instantly during testing
@st.cache_data(ttl=1, show_spinner="Loading Assignment Resource File...")
def fetch_quiz_schema(q_id):
    # Auto-check both common path naming conventions to prevent route errors
    paths_to_test = [
        f"https://raw.githubusercontent.com/science-boa/BOA-Quiz/main/quizzes/QUIZ_{q_id}.yaml",
        f"https://raw.githubusercontent.com/science-boa/BOA-Quiz/main/quizs/QUIZ_{q_id}.yaml"
    ]
    
    st.session_state["attempted_urls"] = paths_to_test
    
    for url in paths_to_test:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                st.session_state["active_url"] = url
                return yaml.safe_load(response.text)
        except Exception:
            pass
    return None

quiz_data = fetch_quiz_schema(quiz_id)

# ─── 🛠️ MAIN PAGE DIAGNOSTIC PANEL ───
st.info("🔧 SYSTEM DIAGNOSTIC PANEL (Temporary Deployment tool)")
diag_col1, diag_col2 = st.columns(2)

with diag_col1:
    if quiz_data is None:
        st.error("❌ Data Status: quiz_data is empty. Both tested paths failed.")
    else:
        st.success("✅ Data Status: YAML loaded successfully!")
        st.write(f"**Connected Path:** `{st.session_state.get('active_url')}`")

with diag_col2:
    if quiz_data and "long_answer" in quiz_data:
        st.success("🎯 'long_answer' key detected! Rendering logic is active.")
    else:
        st.error("❌ 'long_answer' key is MISSING from the currently fetched file structure.")
    
    if st.button("🔄 Force Global Cache Clear & Refresh App", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# 3. View Interface Architecture Rendering
if not quiz_data:
    st.error(f"⚠️ Unable to load Assignment ID: **{quiz_id}**. Please verify your GitHub file paths.")
else:
    st.title(quiz_data.get("title", f"Quiz Portal (ID: {quiz_id})"))
    
    col_left, col_right = st.columns([2, 3], gap="large")
    
    # ─── LEFT COLUMN: Media Anchor Panel ───
    with col_left:
        st.subheader("📺 Video Source Material")
        if quiz_data.get("video_url") and quiz_data["video_url"].strip() != "":
            st.video(quiz_data["video_url"])
            st.info("💡 Pro-Tip: You can pause or scrub this timeline freely while filling out your answers on the right side panel.")
        else:
            st.warning("⚠️ No instructional video link was provided for this assignment. Proceed directly to the questions.")
        
        st.subheader("👤 Your Identity Details")
        student_email = st.text_input("Enter your institutional email address:", placeholder="e.g., student@school.ac.uk")
    
    # ─── RIGHT COLUMN: Assignment Questions ───
    with col_right:
        st.subheader("📝 Assignment Questions")
        
        mc_user_selections = {}
        student_long_text = ""  # Initialized to block NameError crashes
        
        # REMOVED fixed height container so the whole column scrolls naturally.
        
        # Phase A: Render Multiple Choice Questions
        if "multiple_choice" in quiz_data and quiz_data["multiple_choice"]:
            st.markdown("### Part 1: Quick-Check Selection Questions")
            for item in quiz_data["multiple_choice"]:
                q_num = item["question_num"]
                st.markdown(f"**Question {q_num}:** {item['text']} *({item.get('points', 5)} Marks)*")
                
                options_list = [item["A"], item["B"], item["C"], item["D"]]
                
                mc_user_selections[q_num] = st.radio(
                    label=f"Options for Q{q_num}",
                    options=options_list,
                    index=None,  
                    label_visibility="collapsed",
                    key=f"mc_radio_{q_num}"
                )
                st.write("")
        
        # Phase B: REWRITTEN Long Answer Question
        # Uses explicit dictionary checks and a native UI divider for a clean break
        if "long_answer" in quiz_data and isinstance(quiz_data["long_answer"], dict):
            st.divider() 
            st.markdown("### Part 2: Long-Form Written Explanation")
            
            # Safely extract dictionary elements
            la_q_num = quiz_data["long_answer"].get("question_num", "N/A")
            la_text = quiz_data["long_answer"].get("text", "Question text missing.")
            la_points = quiz_data["long_answer"].get("points", 10)
            
            st.markdown(f"**Question {la_q_num}:** {la_text} *({la_points} Marks)*")
            
            student_long_text = st.text_area(
                label="Type your complete analytical response below:", 
                placeholder="Provide detailed explanations or evidence...",
                height=220, # Added vertical space for detailed writing
                key="student_long_answer_input" # Unique key to prevent conflict
            )
        
        st.write("")
        # Submit button flows naturally underneath the long answer box
        submit_trigger = st.button("Finalize and Submit Assignment", type="primary", use_container_width=True)

        # 4. Grading Evaluation & SMTP Delivery Runtime Block
        if submit_trigger:
            if not student_email or "@" not in student_email:
                st.error("❌ Submission Failed: You must provide a valid email address to receive your grades.")
            elif "long_answer" in quiz_data and not student_long_text.strip():
                st.error("❌ Submission Failed: Please write a response for the long answer question before finalizing.")
            else:
                with st.spinner("Processing submissions and invoking automated semantic grader..."):
                    
                    # Step A: Tabulate Multiple Choice Locally
                    mc_score = 0
                    mc_possible = 0
                    mc_breakdown_html = "<h3>Part 1: Multiple Choice Results</h3><ul>"
                    
                    for item in quiz_data.get("multiple_choice", []):
                        q_num = item["question_num"]
                        points_allotted = item.get("points", 5)
                        mc_possible += points_allotted
                        
                        selected_string = mc_user_selections[q_num]
                        correct_letter = item["answer"]  
                        correct_string = item[correct_letter] 
                        
                        if selected_string == correct_string:
                            mc_score += points_allotted
                            mc_breakdown_html += f"<li><b>Q{q_num}:</b> Correct (+{points_allotted} Marks)<br><small><i>Explanation: {item['explanation']}</i></small></li>"
                        else:
                            mc_breakdown_html += f"<li><b>Q{q_num}:</b> Incorrect (0/{points_allotted} Marks)<br>Your Answer: {selected_string if selected_string else 'Skipped'}<br>Correct Answer: {correct_string}<br><small><i>Explanation: {item['explanation']}</i></small></li>"
                    
                    mc_breakdown_html += f"</ul><p><b>Multiple Choice Total: {mc_score} / {mc_possible} Marks</b></p>"
                    
                    # Step B: Tabulate Long Answer via Gemini 1.5 Flash Model API Call
                    la_score = 0
                    la_feedback = "No open-ended component structured for evaluation."
                    
                    if "long_answer" in quiz_data and isinstance(quiz_data["long_answer"], dict):
                        la_rubric = quiz_data["long_answer"].get("rubric", "")
                        
                        try:
                            model = genai.GenerativeModel(
                                'gemini-1.5-flash',
                                generation_config={"response_mime_type": "application/json"}
                            )
                            
                            ai_grading_prompt = f"""
                            You are a professional educational assessment engine. Grade the student's open-ended response against the provided rubric parameters.
                            
                            CRITICAL: Return your final response in valid JSON matching exactly these two root keys:
                            "score": An integer data value representing marks awarded. It cannot exceed the max available points.
                            "feedback": A short paragraph explaining item criteria met or missing, offering direct improvement suggestions.
                            
                            INPUT SPECIFICATIONS:
                            - Question Target: {la_text}
                            - Evaluation Rubric: {la_rubric}
                            - Max Points Available: {la_points}
                            - Student Written Input: {student_long_text}
                            """
                            
                            ai_raw_payload = model.generate_content(ai_grading_prompt).text
                            ai_parsed_data = json.loads(ai_raw_payload)
                            
                            la_score = int(ai_parsed_data.get("score", 0))
                            la_feedback = ai_parsed_data.get("feedback", "No comment provided.")
                        except Exception as e:
                            la_score = 0
                            la_feedback = f"Automated grading connection timeout. Raw log details: {str(e)}"
                    
                    # Step C: Formulate Email and Execute Outbound SMTP Transmission
                    total_marks_earned = mc_score + la_score
                    total_marks_possible = mc_possible + (la_points if "long_answer" in quiz_data else 0)
                    
                    email_html_body = f"""
                    <html>
                    <body style="font-family: sans-serif; color: #333; line-height: 1.5;">
                        <div style="background-color: #0f172a; color: white; padding: 20px; border-radius: 6px 6px 0 0;">
                            <h2 style="margin: 0;">Assignment Performance Ledger</h2>
                            <p style="margin: 5px 0 0 0; color: #94a3b8;">Quiz ID Reference: {quiz_id} | Student: {student_email}</p>
                        </div>
                        <div style="padding: 20px; border: 1px solid #cbd5e1; border-top: none; border-radius: 0 0 6px 6px; background-color: #f8fafc;">
                            <h2 style="color: #0284c7; margin-top: 0;">Overall Grade: {total_marks_earned} / {total_marks_possible} Marks</h2>
                            <hr style="border: 0; border-top: 1px solid #cbd5e1; margin: 20px 0;">
                            
                            {mc_breakdown_html}
                            
                            <hr style="border: 0; border-top: 1px solid #cbd5e1; margin: 20px 0;">
                            <h3>Part 2: Long Answer Assessment Details</h3>
                            <p><b>Student Response:</b> <i>"{student_long_text}"</i></p>
                            <p><b>Score Awarded: {la_score} Marks</b></p>
                            <div style="background-color: #f1f5f9; padding: 12px; border-left: 4px solid #0284c7; font-style: italic;">
                                <b>Gemini Teacher Evaluation:</b> {la_feedback}
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                    
                    try:
                        msg = MIMEMultipart("alternative")
                        msg["Subject"] = f"📚 Homework Feedback - Quiz {quiz_id} Results"
                        msg["From"] = st.secrets["SMTP_USERNAME"]
                        msg["To"] = student_email
                        msg["Bcc"] = TARGET_AUDIT_EMAIL 
                        
                        msg.attach(MIMEText(email_html_body, "html"))
                        
                        server = smtplib.SMTP(st.secrets["SMTP_SERVER"], st.secrets["SMTP_PORT"])
                        server.starttls() 
                        server.login(st.secrets["SMTP_USERNAME"], st.secrets["SMTP_PASSWORD"])
                        
                        recipients = [student_email, TARGET_AUDIT_EMAIL]
                        server.sendmail(st.secrets["SMTP_USERNAME"], recipients, msg.as_string())
                        server.quit()
                        
                        st.balloons()
                        st.success(f"🎉 Quiz Submitted! Immediate feedback has been dispatched. Check your email (**{student_email}**).")
                        
                        st.markdown("### 📊 Summary View of Results")
                        st.markdown(f"**Total Marks: {total_marks_earned} / {total_marks_possible}**")
                        st.markdown(f"**Long Answer Score:** {la_score} Marks")
                        st.info(f"**Gemini Marker Review:** {la_feedback}")
                        
                    except Exception as smtp_err:
                        st.error(f"Data tabulated successfully, but transaction email delivery failed. System log: {str(smtp_err)}")
