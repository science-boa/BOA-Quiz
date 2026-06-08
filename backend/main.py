import os
import json
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types

app = FastAPI(title="Homework Portal Backend")

# Enable CORS globally to ensure the GitHub Pages frontend can access all endpoints cleanly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

def send_feedback_email_via_http(payload: SubmissionPayload, grading: dict):
    """
    HTTP Email Delivery Engine with aggressive diagnostic logging.
    """
    print("\n--- STARTING DIAGNOSTIC EMAIL DISPATCH ---")
    try:
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
        
        bridge_url = os.environ.get("GMAIL_BRIDGE_URL", "").strip()
        bridge_key = os.environ.get("GMAIL_BRIDGE_KEY", "").strip()
        
        if not bridge_url or not bridge_key:
            print("[DIAGNOSTIC] ERROR: Missing GMAIL_BRIDGE_URL or GMAIL_BRIDGE_KEY.")
            return

        # Prepare payloads
        student_payload = {"key": bridge_key, "to": payload.student_email.strip(), "subject": f"Feedback: {quiz_data.get('title')}", "body": body}
        admin_payload = {"key": bridge_key, "to": "science.boa@gmail.com", "subject": f"Result-{payload.quiz_id}", "body": body}

        # Dispatch with explicit connection verification
        for label, p in [("Student", student_payload), ("Admin", admin_payload)]:
            print(f"[DIAGNOSTIC] Sending {label} email to {p['to']}...")
            try:
                response = requests.post(bridge_url, json=p, timeout=20)
                print(f"[DIAGNOSTIC] {label} Response Code: {response.status_code}")
                print(f"[DIAGNOSTIC] {label} Raw Response Text: {response.text}")
                
                if response.status_code != 200:
                    print(f"[DIAGNOSTIC] ALERT: {label} request failed with status {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"[DIAGNOSTIC] ALERT: {label} request raised exception: {e}")

    except Exception as e:
        print(f"HTTP MAIL ERROR: {str(e)}")
    finally:
        print("--- END OF DIAGNOSTIC EMAIL DISPATCH ---\n")

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"message": "Homework Portal Backend is online."}

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "healthy"}

@app.post("/submit")
async def process_submission(payload: SubmissionPayload, background_tasks: BackgroundTasks):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Gemini API Key missing.")
        
    la_data = payload.quiz_schema.get("long_answer")
    grading = {"score": "N/A", "feedback": "No long answer validation."}
    
    if la_data:
        try:
            ai_client = genai.Client(api_key=api_key)
            prompt = f"Evaluate: Question: {la_data.get('text')}. Rubric: {la_data.get('rubric')}. Answer: {payload.la_input}. JSON format: {{'score': 0, 'feedback': ''}}"
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            grading = json.loads(response.text)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"AI Evaluator failed: {str(e)}")
            
    background_tasks.add_task(send_feedback_email_via_http, payload, grading)
    return {"status": "success"}
