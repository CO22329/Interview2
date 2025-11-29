import importlib, traceback
from functools import wraps

def agent(fn):
    return fn

def task(agent=None):
    def decorator(fn):
        return fn
    return decorator

def crew(fn):
    return fn

class Agent:
    def __init__(self, name=None, description=None):
        self.name = name
        self.description = description
    def __repr__(self):
        return f"<Agent {self.name!r}>"

class Task:
    def __init__(self, result=None):
        self.result = result or {}
    def __repr__(self):
        return f"<Task keys={list(self.result.keys())}>"

class Crew:
    def __init__(self, agents=None):
        self.agents = agents or []

    def kickoff(self, inputs: dict):
        """
        Minimal kickoff: try to call functions defined in crew_agents.py:
          - generate_questions_task(inputs)
          - evaluate_answers_task(inputs)
        If those return Task instances, return .result. Otherwise fallbacks.
        """
        try:
            crew_mod = importlib.import_module("crew_agents")
        except Exception:
            traceback.print_exc()
            return {}

        action = inputs.get("action", "")
        if action == "generate_questions":
            fn = getattr(crew_mod, "generate_questions_task", None)
            if callable(fn):
                try:
                    out = fn(inputs)
                    if isinstance(out, Task):
                        return out.result
                    if isinstance(out, dict):
                        return out
                except Exception:
                    traceback.print_exc()
            # fallback
            company = inputs.get("company", "Company")
            role = inputs.get("role", "Role")
            return {"questions": [
                {"question": f"What are the key programming concepts for a {role} at {company}?"},
                {"question": f"How would you design a scalable web app for {company}?"},
                {"question": f"Which databases suit {company} and why?"},
                {"question": f"Describe solving a large-scale performance issue at {company}."}
            ]}

        if action == "evaluate_answers":
            fn = getattr(crew_mod, "evaluate_answers_task", None)
            if callable(fn):
                try:
                    out = fn(inputs)
                    if isinstance(out, Task):
                        return out.result
                    if isinstance(out, dict):
                        return out
                except Exception:
                    traceback.print_exc()
        
            answers = inputs.get("answers", [])
            total_chars = sum(len(a.get("answer","")) for a in answers)
            avg = total_chars / (len(answers) or 1)
            base = 8 if avg>400 else 7 if avg>250 else 6 if avg>150 else 5
            return {"report":{
                "overall_score": base,
                "strengths": ["Clear problem solving", "Good technical foundation"],
                "weaknesses": [f"Add more {inputs.get('company','company')}-specific examples"],
                "topic_scores": {
                    "technical_knowledge": base,
                    "problem_solving": base+1,
                    "communication": max(base-1,1),
                    "code_quality": base,
                    "system_design": base
                }
            }}

        return {}
