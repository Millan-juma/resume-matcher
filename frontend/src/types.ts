export type Stage = "applied" | "interview" | "rejected" | "hired";

export type Job = { id: string; title: string; description: string; org_id: string };

export type Breakdown = { score: number; matched_skills: string[]; missing_skills: string[] };

export type Applicant = {
  id: string;
  job_id: string;
  stage: Stage;
  score: number | null;
  score_breakdown: Breakdown | null;
  scoring_status: "pending" | "done" | "failed";
  scoring_error?: string | null;
};

export type Explanation = {
  summary: string;
  strengths: string[];
  gaps: string[];
  suggestions: string[];
  cached: boolean;
  provider: string;
  note: string;
};

export type SkillsResponse = {
  custom: { id: string; name: string }[];
  using_defaults: boolean;
  defaults: string[];
};

export type StaffMember = { id: string; email: string; role: "admin" | "recruiter"; is_active: boolean };
