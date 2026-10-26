import re
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer("all-MiniLM-L6-v2")

SKILLS = {
    "python", "fastapi", "django", "flask", "sqlalchemy", "sql", "postgresql",
    "mysql", "mongodb", "redis", "docker", "kubernetes", "git", "aws", "azure",
    "gcp", "linux", "react", "javascript", "typescript", "node.js", "html", "css",
    "rest", "graphql", "pytest", "celery", "alembic", "machine learning",
    "pandas", "numpy", "pytorch", "tensorflow", "ci/cd", "java", "go",
}

def chunk(text, size=120, overlap=20):
    words = text.split()
    step = size - overlap
    return [" ".join(words[i:i + size]) for i in range(0, max(len(words), 1), step)]

def extract_skills(text):
    t = text.lower()
    return {s for s in SKILLS if re.search(rf"\b{re.escape(s)}\b", t)}

def score(resume_text, job_text):
    r_emb = model.encode(chunk(resume_text), convert_to_tensor=True)
    j_emb = model.encode(chunk(job_text), convert_to_tensor=True)
    sim = util.cos_sim(j_emb, r_emb)
    semantic = float(sim.max(dim=1).values.mean())

    need, have = extract_skills(job_text), extract_skills(resume_text)
    skill_score = len(need & have) / len(need) if need else 1.0

    final = 0.6 * semantic + 0.4 * skill_score
    return {
        "score": round(final * 100, 1),
        "matched_skills": sorted(need & have),
        "missing_skills": sorted(need - have),
    }
