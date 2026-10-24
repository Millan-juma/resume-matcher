from app.services.matcher import score

job = """We need a backend developer with Python, FastAPI, PostgreSQL and Docker
experience. Knowledge of Redis and AWS is a plus."""

strong = """Backend developer with 3 years of experience building APIs in Python
and FastAPI. Worked with PostgreSQL, Redis and Docker. Deployed on AWS."""

weak = """Graphic designer experienced in Photoshop, Illustrator and branding.
Created marketing material for local businesses."""

print("STRONG:", score(strong, job))
print("WEAK:  ", score(weak, job))
