import os

from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
import PyPDF2
import re
from PyPDF2.errors import PdfReadError

# ------------------ APP SETUP ------------------
app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///resumes.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ------------------ DATABASE MODEL ------------------
class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    score = db.Column(db.Integer)
    role = db.Column(db.String(100))
    skills_found = db.Column(db.Text)
    missing_skills = db.Column(db.Text)

# ------------------ CREATE DB (IMPORTANT FIX) ------------------
with app.app_context():
    db.create_all()

# ------------------ HELPERS ------------------
def has_skill(skill, text):
    pattern = r"\b" + re.escape(skill) + r"\b"
    return re.search(pattern, text) is not None

# ------------------ SKILL DEFINITIONS ------------------
FRONTEND_SKILLS = {"html", "css", "javascript", "react"}
BACKEND_SKILLS = {"python", "java", "flask", "django", "node", "sql"}
DATA_SKILLS = {"python", "sql", "pandas", "numpy", "excel"}

ROLE_SKILL_MAP = {
    "Frontend Developer": FRONTEND_SKILLS,
    "Backend Developer": BACKEND_SKILLS,
    "Data Analyst": DATA_SKILLS,
    "Full Stack Developer": FRONTEND_SKILLS | BACKEND_SKILLS,
}

SKILL_WEIGHTS = {
    "html": 10,
    "css": 10,
    "javascript": 15,
    "react": 20,
    "python": 15,
    "java": 15,
    "flask": 20,
    "django": 20,
    "node": 15,
    "sql": 15,
}

# ------------------ ROUTES ------------------
@app.route("/", methods=["GET", "POST"])
def home():
    skills = []
    missing_skills = []
    score = None
    role = "General"

    if request.method == "POST":
        file = request.files.get("resume")

        # -------- FILE VALIDATION --------
        if not file or file.filename == "":
            return render_template(
                "index.html",
                skills=[],
                score=0,
                role="No File",
                missing_skills=[]
            )

        if not file.filename.lower().endswith(".pdf"):
            return render_template(
                "index.html",
                skills=[],
                score=0,
                role="Upload PDF only",
                missing_skills=[]
            )

        # -------- SAFE PDF TEXT EXTRACTION --------
        text = ""
        try:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted
        except PdfReadError:
            return render_template(
                "index.html",
                skills=[],
                score=0,
                role="Invalid PDF",
                missing_skills=[]
            )

        text = text.lower()

        # -------- SKILL EXTRACTION --------
        all_skills = FRONTEND_SKILLS | BACKEND_SKILLS | DATA_SKILLS
        found_skills = set()

        for skill in all_skills:
            if has_skill(skill, text):
                found_skills.add(skill.capitalize())

        skills = sorted(found_skills)
        skills_set = {s.lower() for s in skills}

        # -------- SCORE CALCULATION --------
        score = sum(SKILL_WEIGHTS.get(s, 5) for s in skills_set)
        score = min(score, 100)

        # -------- ROLE DECISION (FIXED ORDER) --------
        if {"python", "javascript", "react", "sql"}.issubset(skills_set):
            role = "Full Stack Developer"
        elif {"python", "django", "sql"}.issubset(skills_set):
            role = "Backend Developer"
        elif {"react", "javascript", "html", "css"}.issubset(skills_set):
            role = "Frontend Developer"
        elif {"python", "sql"}.issubset(skills_set):
            role = "Data Analyst"
        else:
            role = "General"

        # -------- MISSING SKILLS --------
        if role in ROLE_SKILL_MAP:
            required = ROLE_SKILL_MAP[role]
            missing_skills = sorted([
                skill.capitalize()
                for skill in required
                if skill not in skills_set
            ])
        else:
            missing_skills = []

        # -------- SAVE TO DATABASE --------
        try:
            resume_entry = Resume(
                filename=file.filename,
                score=score,
                role=role,
                skills_found=", ".join(skills),
                missing_skills=", ".join(missing_skills)
            )

            db.session.add(resume_entry)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print("DB Error:", e)

    return render_template(
        "index.html",
        skills=skills,
        score=score,
        role=role,
        missing_skills=missing_skills
    )

@app.route("/history")
def history():
    resumes = Resume.query.order_by(Resume.id.desc()).all()
    return render_template("history.html", resumes=resumes)

# ------------------ RUN APP ------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)