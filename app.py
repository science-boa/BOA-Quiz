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
# Reads '?quiz=XYZ' from the URL bar, defaults to quiz number '101' if omitted
quiz_id = st.query_params.get("quiz", "101")

@st.cache_data(show_spinner="Loading Assignment Resource File...")
def fetch_quiz_schema(q_id):
    # Adjust this path matching your target public GitHub configuration profile
    # Format: https://raw.githubusercontent.com/[USER]/[REPO]/main/quizzes/QUIZ_[ID].yaml
    raw_git_url = f"https://raw.githubusercontent.com/science-boa/BOA-Quiz/main/quizzes/QUIZ_{q_id}.yaml"
    try:
        response = requests.get(raw_git_url)
        if response.status_code == 200:
            return yaml.safe_load(response.text)
    except Exception:
        return None
    return None

quiz_data = fetch_quiz_schema(quiz_id)

# 3. View Interface Architecture Rendering
if not quiz_data:
    st.error(f"⚠️ Unable to load Assignment ID: **{quiz_id}**. Please check the URL link or contact your teacher.")
else:
    st.title(quiz_data.get("title", f"Quiz Portal (ID: {quiz_id})"))
    
    # Implementing Layout 2: Two-Column Split Screen Workspace
    col_left, col_right = st.columns([2, 3], gap="large")
    
    # ─── LEFT COLUMN: Media Anchor Panel ───
    with col_left:
        st.subheader("📺 Video Source Material")
        st.video(quiz_data["video_url"])
        st.info("💡 Pro-Tip: You can pause or scrub this timeline freely while filling out your answers on the right side panel.")
        
        st.subheader("👤 Your Identity Details")
        student_email = st.text_input("Enter your institutional email address:", placeholder="e.g., student@school.ac.uk")
    
    # ─── RIGHT COLUMN: Bounded Scrollable Question Panel ───
    with col_right:
        st.subheader("📝 Assignment Questions")
        
        mc_user_selections = {}
        
        # Enforcing fixed height container translates this panel into a sleek scroll pane
        with st.container(height=620):
            
            # Phase A: Render Multiple Choice Questions
            if "multiple_choice" in quiz_data and quiz_data["multiple_choice"]:
                st.markdown("### Part 1: Quick-Check Selection Questions")
                for item in quiz_data["multiple_choice"]:
                    q_num = item["question_num"]
                    st.markdown(f"**Question {q_num}:** {item['text']} *({item.get('points', 5)} Marks)*")
                    
                    # Dynamically collect option texts
                    options_list = [item["A"], item["B"], item["C"], item["D"]]
                    
                    # Store user response natively
                    mc_user_selections[q_num] = st.radio(
                        label=f"Options for Q{q_num}",
                        options=options_list,
                        index=None,  # Forces radio to be unselected by default
                        label_visibility="collapsed",
                        key=f"mc_radio_{q_num}"
                    )
                    st.write("")
            
            # Phase B: Render Long Answer Question
            if "long_answer" in quiz_data and quiz_data["long_answer"]:
                la_data = quiz_data["long_answer"]
                st.markdown("---")
                st.markdown("### Part 2: Long-Form Written Explanation")
                st.markdown(f"**Question {la_data['question_num']}:** {la_data['text']} *({la_data.get('points', 10)} Marks)*")
                student_long_text = st.text_area(
                    "Type your complete analytical response below:", 
                    placeholder="Provide detailed explanations or evidence...",
                    height=180,
                    key="student_long_answer"
                )
            
            st.write("")
            submit_trigger = st.button("Finalize and Submit Assignment", type="primary", use_container_width=True)

        # 4. Grading Evaluation & SMTP Delivery Runtime Block
        if submit_trigger:
            if not student_email or "@" not in student_email:
                st.error("❌ Submission Failed: You must provide a valid email address to receive your grades.")
            elif not student_long_text.strip():
                st.error("❌ Submission Failed: Please write a response for the long answer question before finalizing.")
            else:
                with st.spinner("Processing submissions and invoking automated semantic grader..."):
                    
                    # Step A: Tabulate Multiple Choice Locally
                    mc_score = 0
                    mc_possible = 0
                    mc_breakdown_html = "<h3>Part 1: Multiple Choice Results</h3><ul>"
                    
                    for item in quiz_data["multiple_choice"]:
                        q_num = item["question_num"]
                        points_allotted = item.get("points", 5)
                        mc_possible += points_allotted
                        
                        selected_string = mc_user_selections[q_num]
                        correct_letter = item["answer"]  # e.g., 'B'
                        correct_string = item[correct_letter] # e.g., option content matching 'B'
                        
                        if selected_string == correct_string:
                            mc_score += points_allotted
                            mc_breakdown_html += f"<li><b>Q{q_num}:</b> Correct (+{points_allotted} Marks)<br><small><i>Explanation: {item['explanation']}</i></small></li>"
                        else:
                            mc_breakdown_html += f"<li><b>Q{q_num}:</b> Incorrect (0/{points_allotted} Marks)<br>Your Answer: {selected_string if selected_string else 'Skipped'}<br>Correct Answer: {correct_string}<br><small><i>Explanation: {item['explanation']}</i></small></li>"
                    
                    mc_breakdown_html += f"</ul><p><b>Multiple Choice Total: {mc_score} / {mc_possible} Marks</b></p>"
                    
                    # Step B: Tabulate Long Answer via Gemini 1.5 Flash Model API Call
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
                        - Question Target: {la_data['text']}
                        - Evaluation Rubric: {la_data['rubric']}
                        - Max Points Available
