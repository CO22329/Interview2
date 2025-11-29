
from crewai import agent, task, crew, Agent, Task, Crew  
import os, json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY missing")
genai.configure(api_key=GEMINI_API_KEY)

@agent
def question_generator() -> Agent:
    return Agent(
        name="question_generator",
        description="Generate 6-8 technical interview questions for a role at a company."
    )

@task(agent=question_generator)
def generate_questions_task(inputs: dict) -> Task:
    """
    inputs expected: {"company": "...", "role": "..."}
    returns: {"questions": [ {"question":"..."} , ... ]}
    """
    company = inputs["company"]
    role = inputs["role"]

    model_names = [
        "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-pro-latest"
    ]
    prompt = f"""
    Generate 6-8 TECHNICAL interview questions for a {role} position at {company}.
    Return ONLY a JSON array where each object has a 'question' field.
    Example: [{{"question":"Q1"}},{{"question":"Q2"}}]
    """

    for model_name in model_names:
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(prompt)
            text = resp.text.strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start != -1 and end != -1:
                arr = json.loads(text[start:end])
                if isinstance(arr, list) and len(arr) >= 4:
                    return Task(result={"questions": arr})
        except Exception:
            continue

    fallback = [
        {"question": f"What are the key programming concepts for {role} at {company}?"},
        {"question": f"How would you design a scalable web app for {company}?"},
        {"question": f"Which databases suit {company} and why?"},
        {"question": f"Describe solving a large-scale performance issue at {company}."}
    ]
    return Task(result={"questions": fallback})



@agent
def evaluator() -> Agent:
    return Agent(
        name="answer_evaluator",
        description="Evaluate candidate answers and produce a JSON report"
    )

@task(agent=evaluator)
def evaluate_answers_task(inputs: dict) -> Task:
    """
    inputs: {"company": "...", "role":"...", "answers":[{"question":"...","answer":"..."}]}
    returns: {"report": {...} }
    """
    company = inputs["company"]
    role = inputs["role"]
    answers = inputs.get("answers", [])

    model_names = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-pro-latest"]
    answers_text = "\n\n".join([f"Q: {a['question']}\nA: {a['answer']}" for a in answers])
    prompt = f"""
    Evaluate the following answers for a {role} role at {company}:
    {answers_text}

    Return ONLY a JSON object like:
    {{
      "overall_score": 8.5,
      "strengths": ["..."],
      "weaknesses": ["..."],
      "topic_scores": {{
        "technical_knowledge": 8,
        "problem_solving": 9,
        "communication": 7,
        "code_quality": 8,
        "system_design": 7
      }}
    }}
    """

    for model_name in model_names:
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(prompt)
            text = resp.text.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end != -1:
                report = json.loads(text[start:end])
                return Task(result={"report": report})
        except Exception:
            continue

    # local fallback scoring (simple heuristic)
    total_chars = sum(len(a.get("answer","")) for a in answers)
    avg = total_chars / (len(answers) or 1)
    if avg > 400:
        base = 8
    elif avg > 250:
        base = 7
    elif avg > 120:
        base = 6
    else:
        base = 5

    report = {
        "overall_score": base,
        "strengths": ["Clear explanations", "Good problem solving"],
        "weaknesses": [f"Could include more {company}-specific examples"],
        "topic_scores": {
            "technical_knowledge": base,
            "problem_solving": base + 1,
            "communication": max(base - 1, 1),
            "code_quality": base,
            "system_design": base
        }
    }
    return Task(result={"report": report})


# ------------------------
# Crew: combine agents
# ------------------------
@crew
def interview_crew() -> Crew:
    """
    Crew orchestrates tasks:
    1. generate_questions_task
    2. evaluate_answers_task
    Crew API expected to provide a kickoff / run entrypoint.
    """
    return Crew(agents=[question_generator(), evaluator()])
