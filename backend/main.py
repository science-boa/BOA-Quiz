import os
import json
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types

app = FastAPI(title="Homework Portal Backend")

# Enable CORS globally
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

async def send_feedback_email_via_http(payload: SubmissionPayload, grading: dict):
    """
    HTTP Email Delivery Engine with structured Admin JSON.
    """
    print("\n--- STARTING DIAGNOSTIC EMAIL DISPATCH ---")
    try:
        quiz_data = payload.quiz_schema
        total_questions = len(quiz_data.get('multiple_choice', []))
        correct_count = sum(1 for item in quiz_data.get('multiple_choice', []) 
                            if payload.mc_answers.get(str(item['question_num'])) == item.get('answer'))
        
        percent = round((correct_count / total_questions) * 100) if total_questions > 0 else 0
        
        # Build human-readable body for the student
        body = f"Multiple Choice Score: {percent}%<br><br>"
        for item in quiz_data.get('multiple_choice', []):
            q_num = str(item['question_num'])
            user_ans = payload.mc_answers.get(q_num)
            correct = item.get('answer')
            body += f"Question: {item['text']}<br>"
            body += f"Your Answer: {user_ans}<br>"
            body += "Correct<br><br>" if user_ans == correct else f"The correct answer was: {correct}<br><br>"
                
        la_data = quiz_data.get('long_answer', {})
        body += "<b>Long Answer Question</b><br>"
        body += f"{la_data.get('text')}<br>"
        body += f"Answer: {payload.la_input}<br>"
        body += f"Feedback: {grading.get('feedback')}<br>"
        
        # STRUCTURED JSON for Admin (Easy for Power Automate)
        admin_json = {
            "quiz_id": payload.quiz_id,
            "student_email": payload.student_email,
            "mc_score_percent": percent,
            "long_answer": {
                "question": la_data.get('text'),
                "student_answer": payload.la_input,
                "feedback": grading.get('feedback')
            }
        }
        admin_body = f"--- BEGIN DATA ---\n{json.dumps(admin_json, indent=2)}\n--- END DATA ---"
        
        bridge_url = os.environ.get("GMAIL_BRIDGE_URL", "").strip()
        bridge_key = os.environ.get("GMAIL_BRIDGE_KEY", "").strip()
        
        if not bridge_url or not bridge_key:
            print("[DIAGNOSTIC] ERROR: Missing GMAIL_BRIDGE_URL or GMAIL_BRIDGE_KEY.")
            return

        student_payload = {"key": bridge_key, "to": payload.student_email.strip(), "subject": f"Feedback: {quiz_data.get('title')}", "body": body}
        admin_payload = {"key": bridge_key, "to": "richard.evans@boa-academy.co.uk", "subject": f"Result-{payload.quiz_id}", "body": admin_body}

        # Send payloads
        for label, p in [("Student", student_payload), ("Admin", admin_payload)]:
            print(f"[DIAGNOSTIC] Sending {label} email...")
            requests.post(bridge_url, json=p, timeout=20)

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
async def process_submission(payload: SubmissionPayload):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Gemini API Key missing.")
        
    la_data = payload.quiz_schema.get("long_answer")
    grading = {"score": "N/A", "feedback": "No long answer validation."}
    active_model = "none"
    
    if la_data:
        ai_client = genai.Client(api_key=api_key)
        prompt = f"Evaluate: Question: {la_data.get('text')}. Rubric: {la_data.get('rubric')}. Answer: {payload.la_input}. JSON format: {{'score': 0, 'feedback': ''}}"
        config = types.GenerateContentConfig(response_mime_type="application/json")
        
        models_to_try = ['gemma-4-26b-a4b-it', 'gemini-3.1-flash-lite', 'gemini-2.5-flash-lite', 'gemini-3-flash', 'gemini-2.5-flash']
        success = False

        for model_name in models_to_try:
            try:
                response = ai_client.models.generate_content(model=model_name, contents=prompt, config=config)
                grading = json.loads(response.text)
                success = True
                active_model = model_name
                break
            except Exception:
                continue
        
        if not success:
            raise HTTPException(status_code=502, detail="All AI models failed.")
            
    await send_feedback_email_via_http(payload, grading)
    return {"status": "success", "model_used": active_model}
