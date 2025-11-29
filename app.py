# app.py
import os
import json
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, request, session, redirect, url_for

# load env
load_dotenv()

# Flask config
app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET", "harman_secret")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)

# import the crew (your crew_agents.py)
# it should expose a function decorated with @crew named interview_crew
try:
    from crew_agents import interview_crew
except Exception as e:
    print("⚠️ Could not import interview_crew from crew_agents.py:", e)
    interview_crew = None


def call_crew(inputs):
    """
    Defensive caller wrapper for your crew object.
    Expected behaviors it tries (in order):
      - interview_crew().kickoff(inputs)
      - interview_crew.kickoff(inputs)
      - interview_crew(inputs)  # if crew decorated function is itself callable
    Returns dict (possibly empty) or raises.
    """
    if interview_crew is None:
        raise RuntimeError("Crew not available")

    # If interview_crew is a function that returns a Crew instance:
    try:
        crew_obj = interview_crew()
    except TypeError:
        # maybe interview_crew is not callable and already a Crew instance
        crew_obj = interview_crew
    except Exception:
        # last resort: treat interview_crew as the callable to run
        crew_obj = interview_crew

    # Try kickoff / run / call patterns
    try:
        if hasattr(crew_obj, "kickoff"):
            return crew_obj.kickoff(inputs)
        if hasattr(crew_obj, "run"):
            return crew_obj.run(inputs)
        # if crew_obj is directly callable and returns result dict
        if callable(crew_obj):
            return crew_obj(inputs)
    except Exception as e:
        print("⚠️ crew call failed:", e)
        raise

    raise RuntimeError("Crew object does not expose kickoff/run/callable interface")


# Fallback simple generator (in case crew fails)
def fallback_generate_questions(company, role):
    return [
        {"question": f"What are the key programming concepts for a {role} at {company}?"},
        {"question": f"How would you design a scalable web application for {company}?"},
        {"question": f"What database technology would you pick for {company} and why?"},
        {"question": f"Explain an algorithmic optimization you'd apply to a {company}-scale system."}
    ]


def fallback_evaluate(answers, company, role):
    # simple heuristic-based evaluation
    total_chars = sum(len(a.get("answer", "")) for a in answers)
    avg = total_chars / (len(answers) or 1)
    if avg > 400:
        base = 8
    elif avg > 250:
        base = 7
    elif avg > 150:
        base = 6
    else:
        base = 5

    return {
        "overall_score": base,
        "strengths": ["Clear problem solving", "Good technical foundation"],
        "weaknesses": [f"Add more {company}-specific examples", "Give more code-level details"],
        "topic_scores": {
            "technical_knowledge": base,
            "problem_solving": base + 1,
            "communication": max(base - 1, 1),
            "code_quality": base,
            "system_design": base
        }
    }


# ---------- ROUTES ----------
@app.route("/")
def index():
    session.clear()
    return render_template("index.html")


@app.route("/begin", methods=["POST"])
def begin():
    company = request.form.get("company", "").strip()
    role = request.form.get("role", "").strip()

    if not company or not role:
        return redirect(url_for("index"))

    # Try to generate questions via crew
    try:
        result = call_crew({"action": "generate_questions", "company": company, "role": role})
        # Some crew implementations might return {"questions": [...]}
        questions = result.get("questions") if isinstance(result, dict) else None
        if not questions:
            # Some crews might return {"result": {...}} or have a nested structure
            # try to be permissive
            questions = result
        if not isinstance(questions, list):
            raise ValueError("No questions returned from crew")
    except Exception as e:
        print("❌ Crew generation failed:", e)
        questions = fallback_generate_questions(company, role)

    # Save session state
    session["company"] = company
    session["role"] = role
    session["questions"] = questions
    session["current_question"] = 0
    session["answers"] = []
    session.modified = True

    return redirect(url_for("interview"))


@app.route("/interview", methods=["GET", "POST"])
def interview():
    if "questions" not in session or not session["questions"]:
        return redirect(url_for("index"))

    idx = int(session.get("current_question", 0))
    questions = session["questions"]

    if request.method == "POST":
        answer_text = request.form.get("answer", "").strip()
        if not answer_text:
            # re-render with error
            progress = int((idx / len(questions)) * 100)
            return render_template(
                "interview.html",
                company=session.get("company"),
                role=session.get("role"),
                question=questions[idx]["question"],
                question_number=idx + 1,
                total_questions=len(questions),
                progress=progress,
                error="Please provide an answer before proceeding."
            )

        session["answers"].append({"question": questions[idx]["question"], "answer": answer_text})
        session["current_question"] = idx + 1
        session.modified = True

        if session["current_question"] >= len(questions):
            return redirect(url_for("report"))
        return redirect(url_for("interview"))

    # GET
    if idx >= len(questions):
        return redirect(url_for("report"))

    progress = int((idx / len(questions)) * 100)
    return render_template(
        "interview.html",
        company=session.get("company"),
        role=session.get("role"),
        question=questions[idx]["question"],
        question_number=idx + 1,
        total_questions=len(questions),
        progress=progress
    )


@app.route("/report")
def report():
    if "answers" not in session or not session["answers"]:
        return redirect(url_for("index"))

    company = session.get("company", "Unknown Company")
    role = session.get("role", "Unknown Role")
    answers = session.get("answers", [])

    # Attempt to call the crew evaluator
    try:
        result = call_crew({"action": "evaluate_answers", "company": company, "role": role, "answers": answers})
        # common expected return: {"report": {...}}
        report_data = None
        if isinstance(result, dict):
            if "report" in result:
                report_data = result["report"]
            elif "result" in result and isinstance(result["result"], dict):
                report_data = result["result"].get("report") or result["result"]
            elif all(k in result for k in ("overall_score", "strengths")):
                # crew returned report directly
                report_data = result
        if not report_data:
            raise ValueError("Invalid report returned from crew")
    except Exception as e:
        print("❌ Crew evaluation failed:", e)
        report_data = fallback_evaluate(answers, company, role)

    return render_template("report.html", report=report_data, company=company, role=role)


@app.route("/restart")
def restart():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    # ensure templates exist
    if not os.path.isdir("templates"):
        print("⚠️ templates/ folder not found. Make sure index.html, interview.html and report.html are in templates/")
    app.run(debug=True, host="0.0.0.0", port=5000)
