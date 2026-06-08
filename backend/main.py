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
    allow_origins=["*"],  # In production, swap with ["https://science-boa.github.io"]
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
    HTTP Email Delivery Engine. 
    Instead of SMTP, this opens a standard web request (Port 443) to your private Google Apps Script.
    Because it behaves like standard web browsing, Render's firewall will never block it.
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
        
        # Load HTTP Bridge credentials from Render environment variables
        bridge_url = os.environ.get("GMAIL_BRIDGE_URL", "").strip()
        bridge_key = os.environ.get("GMAIL_BRIDGE_KEY", "").strip()
        
        # DIAGNOSTIC LOG 1: Check environment variables
        if not bridge_url:
            print("[DIAGNOSTIC] CONFIG ERROR: GMAIL_BRIDGE_URL environment variable is empty or missing.")
        else:
            print(f"[DIAGNOSTIC] Loaded URL: {bridge_url[:25]}... (length: {len(bridge_url)})")
            
        if not bridge_key:
            print("[DIAGNOSTIC] CONFIG ERROR: GMAIL_BRIDGE_KEY environment variable is empty or missing.")
        else:
            print(f"[DIAGNOSTIC] Loaded Key: {bridge_key[:3]}... (length: {len(bridge_key)})")

        if not bridge_url or not bridge_key:
            return

        student_email = payload.student_email.strip()
        admin_email = "science.boa@gmail.com"

        # 1. Dispatch Email to Student
        student_payload = {
            "key": bridge_key,
            "to": student_email,
            "subject": f"Feedback from quiz {quiz_data.get('title')}",
            "body": body
        }
        
        # 2. Dispatch Administrative archive copy
        admin_payload = {
            "key": bridge_key,
            "to": admin_email,
            "subject": f"Result-{payload.quiz_id}-{student_email}",
            "body": body
        }

        # Fire off standard HTTP POST requests directly to Google (Port 443) with explicit redirect handling
        print("[DIAGNOSTIC] Dispatching student feedback email request to Google Web App...")
        response_student = requests.post(bridge_url, json=student_payload, timeout=15)
        print(f"[DIAGNOSTIC] Student Email Response: Code {response_student.status_code}")
        print(f"[DIAGNOSTIC] Student Email Body: {response_student.text}")

        print("[DIAGNOSTIC] Dispatching administrative feedback email request to Google Web App...")
        response_admin = requests.post(bridge_url, json=admin_payload, timeout=15)
        print(f"[DIAGNOSTIC] Admin Email Response: Code {response_admin.status_code}")
        print(f"[DIAGNOSTIC] Admin Email Body: {response_admin.text}")

        if response_student.status_code == 200 and response_admin.status_code == 200:
            if "Success" in response_student.text and "Success" in response_admin.text:
                print(f"SUCCESS: Result emails successfully processed and sent by Google to {student_email} and {admin_email}")
            else:
                print("WARNING: Requests completed but Google returned script errors. Check the bodies printed above.")
        else:
            print(f"DELIVERY ERROR: Google Web App returned non-200 statuses.")

    except Exception as http_err:
        print(f"HTTP MAIL ERROR: Failed to dispatch emails. Details: {http_err}")
    finally:
        print("--- END OF DIAGNOSTIC EMAIL DISPATCH ---\n")

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    """
    Root endpoint added to satisfy Render's default health checking.
    Supports both GET and HEAD methods to avoid 405 Method Not Allowed exceptions.
    """
    return {"message": "Homework Portal Backend is online and running successfully."}

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """
    Dedicated endpoint used by the Canvas frontend to verify the server status.
    Returns 200 OK with full CORS headers passing through the middleware chain cleanly.
    """
    return {"status": "healthy"}

@app.post("/submit")
async def process_submission(payload: SubmissionPayload, background_tasks: BackgroundTasks):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Gemini API Key missing on server container.")
        
    la_data = payload.quiz_schema.get("long_answer")
    if not la_data:
        grading = {"score": "N/A", "feedback": "No long answer validation required."}
    else:
        try:
            ai_client = genai.Client(api_key=api_key)
            prompt = (f"Evaluate: Question: {la_data.get('text')}. Rubric: {la_data.get('rubric')}. "
                      f"Answer: {payload.la_input}. JSON format: {{'score': 0, 'feedback': ''}}")
            
            gen_config = types.GenerateContentConfig(response_mime_type="application/json")
            
            try:
                response = ai_client.models.generate_content(
                    model='gemini-3.1-flash-lite',
                    contents=prompt,
                    config=gen_config
                )
                grading = json.loads(response.text)
            except Exception:
                try:
                    response = ai_client.models.generate_content(
                        model='gemini-3.5-flash',
                        contents=prompt,
                        config=gen_config
                    )
                    grading = json.loads(response.text)
                except Exception:
                    response = ai_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                        config=gen_config
                    )
                    grading = json.loads(response.text)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"AI Evaluator failed: {str(e)}")
            
    # Queue the HTTP email delivery in an isolated background task
    background_tasks.add_task(send_feedback_email_via_http, payload, grading)
        
    return {"status": "success"}
