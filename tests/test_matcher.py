from app.services.matcher import score

JOB = "Backend developer with Python, FastAPI, PostgreSQL and Docker experience."


def test_strong_beats_weak():
    strong = "Python developer building FastAPI services with PostgreSQL and Docker."
    weak = "Graphic designer skilled in Photoshop, Illustrator and branding."
    assert score(strong, JOB)["score"] > score(weak, JOB)["score"] + 30


def test_missing_skills_reported():
    result = score("Python developer.", JOB)
    assert "python" in result["matched_skills"]
    assert "docker" in result["missing_skills"]
