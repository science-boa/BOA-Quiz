import os
import json
import smtplib
from email.message import EmailMessage
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types

app = FastAPI(title="Homework Portal Stateless Evaluator")

# Critical for security: Allows your GitHub Pages frontend to communicate with this API safely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, swap with ["https://science-boa.github.io"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SubmissionPayload(BaseModel):
    quiz_id: str
    student_email: str
    mc_answers: dict
    la_input: str
    quiz_schema: dict

def send_feedback_email(payload: SubmissionPayload, grading: dict):
    quiz_data = payload.quiz_schema
    total_questions = len(quiz_data.get('multiple_choice', []))
    correct_count = sum(1 for item in quiz_data.get('multiple_choice', []) 
                       if payload.mc_answers.get(str(item['question_num'])) == item.get('answer'))
    
    percent = round((correct_count / total_questions) * 100) if total_questions > 0 else 0
    body = f"Multiple Choice Score: {percent}%<br><br>"
    
    for item in quiz_data.get('multiple_choice', []):
        q_num = str(item['question_num'])
        user_ans = payload.mc_answers.get(q_num)
        correct = item.get('answer')
        
        body += f"Question Number: {item['text']}<br>"
        body += f"Your Answer: {user_ans}<br>"
        if user_ans == correct:
            body += "Correct<br><br>"
        else:
            body += f"The correct answer was: {correct}<br><br>"
            
    la_data = quiz_data.get('long_answer', {})
    body += "<b>Long Answer Question</b><br>"
    body += f"{la_data.get('text')}<br>"
    body += f"Answer: {payload.la_input}<br>"
    body += f"Feedback: {grading.get('feedback')}<br>"
    
    sender_email = os.environ.get("SMTP_USERNAME", "").strip()
    student_email = payload.student_email.strip()
    admin_email = "science.boa@gmail.com"
    
    msg_student = EmailMessage()
    msg_student.set_content(body, subtype="html")
    msg_student["Subject"] = f"Feedback from quiz {quiz_data.get('title')}"
    msg_student["From"] = sender_email
    msg_student["To"] = student_email
    
    msg_admin = EmailMessage()
    msg_admin.set_content(body, subtype="html")
    msg_admin["Subject"] = f"Result-{payload.quiz_id}-{student_email}"
    msg_admin["From"] = sender_email
    msg_admin["To"] = admin_email
    
    server = smtplib.SMTP(os.environ.get("SMTP_SERVER"), int(os.environ.get("SMTP_PORT", 587)))
    server.starttls()
    server.login(sender_email, os.environ.get("SMTP_PASSWORD"))
    server.send_message(msg_student)
    server.send_message(msg_admin)
    server.quit()

@app.post("/submit")
async def process_submission(payload: SubmissionPayload):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Gemini API Key missing on server container.")
        
    la_data = payload.quiz_schema.get("long_answer")
    if not la_data:
        # Quiz doesn't have a long answer component, grade MC directly
        grading = {"score": "N/A", "feedback": "No long answer validation required."}
    else:
        try:
            # Modern unified SDK implementation
            ai_client = genai.Client(api_key=api_key)
            prompt = (f"Evaluate: Question: {la_data.get('text')}. Rubric: {la_data.get('rubric')}. "
                      f"Answer: {payload.la_input}. JSON format: {{'score': 0, 'feedback': ''}}")
            
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            grading = json.loads(response.text)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"AI Evaluator failed: {str(e)}")
            
    try:
        send_feedback_email(payload, grading)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation complete, but email delivery failed: {str(e)}")
        
    return {"status": "success"}