#!/usr/bin/env python3
"""
random_resume_pdf_templates.py

Generate random (but realistic-looking) tech worker resumes as PDFs,
with multiple layout templates and role profiles.

New in this version:
- Batch generation: create N PDFs in one go
- Optional output directory and filename pattern
- Random template/profile when omitted (max variety), still reproducible with --seed

Install:
  pip install reportlab

Examples:
  # Generate 10 PDFs with random templates + profiles
  python random_resume_pdf_templates.py --out-dir ./out --count 10

  # Reproducible batch
  python random_resume_pdf_templates.py --out-dir ./out --count 10 --seed 42

  # Fixed template/profile for all
  python random_resume_pdf_templates.py --out-dir ./out --count 5 --template sidebar --profile sre

  # Random per-file even if you provide template/profile? Use --randomize-template/profile
  python random_resume_pdf_templates.py --out-dir ./out --count 20 --template classic --randomize-template

  # Single file (still supported)
  python random_resume_pdf_templates.py --out resume.pdf
"""

from __future__ import annotations

import argparse
import os
import random
from dataclasses import dataclass
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    SimpleDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)

# -----------------------------
# Random resume data
# -----------------------------

FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Casey", "Riley", "Morgan", "Jamie", "Avery",
    "Cameron", "Quinn", "Drew", "Parker", "Emerson", "Reese", "Finley",
]
LAST_NAMES = [
    "Nguyen", "Martin", "Bernard", "Dubois", "Lefevre", "Garcia", "Rossi",
    "Patel", "Kim", "Singh", "Lopez", "Hernandez", "Kowalski", "Andersen",
    "Novak",
]

CITIES = [
    "Paris, FR", "Lyon, FR", "Berlin, DE", "Amsterdam, NL", "London, UK",
    "Dublin, IE", "Barcelona, ES", "Lisbon, PT", "Zurich, CH", "Stockholm, SE",
]
EMAIL_DOMAINS = ["example.com", "mail.com", "proton.me", "company.dev"]
PHONE_PREFIXES = ["+33 6", "+33 7", "+44 7", "+49 15", "+31 6", "+34 6", "+351 9"]

ROLE_TITLES = [
    "Software Engineer", "Senior Software Engineer", "Backend Engineer",
    "Full Stack Engineer", "Platform Engineer", "Site Reliability Engineer",
    "Data Engineer", "Machine Learning Engineer", "DevOps Engineer",
    "Security Engineer", "Frontend Engineer",
]

SUMMARY_TEMPLATES = [
    "Tech worker with {years}+ years building {domain} systems. Strong in {focus} with a track record of shipping reliable products and improving developer velocity.",
    "Engineer with {years}+ years of experience in {domain}. Focused on {focus}, pragmatic architecture, and measurable outcomes.",
    "{role} with {years}+ years delivering {domain} solutions. Known for {focus} and cross-functional collaboration.",
]

DOMAINS = [
    "B2B SaaS", "fintech", "e-commerce", "healthtech", "developer tooling",
    "data platforms", "observability", "payments", "logistics", "media streaming",
]
FOCUS_AREAS = [
    "distributed systems", "cloud infrastructure", "API design", "data pipelines",
    "performance tuning", "security hardening", "MLOps", "CI/CD automation",
    "product-minded engineering", "incident response",
]

SKILL_BUCKETS = {
    "Languages": ["Python", "TypeScript", "Go", "Java", "Kotlin", "C#", "SQL", "Bash"],
    "Frameworks": ["Node.js", "FastAPI", "Spring Boot", "React", "Next.js", "Django", "gRPC"],
    "Cloud": ["AWS", "GCP", "Azure", "Terraform", "Kubernetes", "Docker", "Helm"],
    "Data": ["PostgreSQL", "Redis", "Kafka", "BigQuery", "Snowflake", "Airflow", "dbt"],
    "Practices": ["TDD", "DDD", "Clean Architecture", "Observability", "SRE", "Threat Modeling"],
}

COMPANIES = [
    "CloudHarbor", "DataSpring", "PayLattice", "StreamForge", "MedNova",
    "LogiPilot", "InsightWorks", "DevBay", "SecureStack", "MarketPulse",
]
INDUSTRIES = [
    "Fintech", "E-commerce", "Healthtech", "Developer Tools", "Logistics",
    "Media", "Security", "SaaS",
]

DEGREES = [
    ("BSc", "Computer Science"),
    ("BEng", "Software Engineering"),
    ("MSc", "Data Science"),
    ("MSc", "Cybersecurity"),
    ("BSc", "Mathematics"),
]
SCHOOLS = [
    "Sorbonne Universite", "EPITA", "INSA Lyon", "TU Berlin", "University College Dublin",
    "Imperial College London", "Universitat Politecnica de Catalunya", "University of Amsterdam",
]

PROJECT_NOUNS = [
    "Feature Flag Platform", "Realtime Metrics Pipeline", "Billing Reconciliation",
    "Identity Gateway", "Search Relevance", "Cost Optimizer", "Release Orchestrator",
    "Fraud Detection Service", "Developer Portal", "Data Quality Monitor",
]

CERTIFICATIONS = [
    "AWS Certified Solutions Architect - Associate",
    "CKA: Certified Kubernetes Administrator",
    "HashiCorp Certified: Terraform Associate",
    "Google Professional Cloud Architect",
    "Azure Fundamentals (AZ-900)",
]

LANGUAGES = [
    ("English", "Fluent"),
    ("French", "Native"),
    ("Spanish", "Professional"),
    ("German", "Intermediate"),
    ("Italian", "Intermediate"),
]

BULLET_LIBRARY = [
    "Designed and shipped {thing}, improving {metric} by {pct}%.",
    "Reduced {metric} latency from {from_}ms to {to}ms via profiling and caching.",
    "Led migration from {old} to {new}, cutting monthly infra cost by {pct}%.",
    "Built {thing} with {tech}, enabling {outcome}.",
    "Introduced {practice} across the team; increased release frequency by {pct}%.",
    "Partnered with product and security to deliver {thing} without regressions.",
    "Implemented SLOs and dashboards; decreased incident volume by {pct}%.",
]

THINGS = [
    "a multi-tenant API gateway", "a Kafka-based event bus", "an internal developer portal",
    "a payment risk rules engine", "a data lineage service", "a CI/CD pipeline",
    "an authorization service", "a realtime aggregation service", "a search indexing pipeline",
    "a UI component library", "a design system", "a GraphQL BFF layer",
]
METRICS = ["p95", "p99", "error rate", "build time", "time-to-recovery", "CPU usage", "query time", "bundle size"]
PRACTICES = ["code review standards", "trunk-based development", "on-call playbooks", "service ownership", "feature flags"]
TECHS = ["Kubernetes", "Terraform", "FastAPI", "Go", "TypeScript", "PostgreSQL", "Redis", "Kafka", "gRPC", "React"]
OUTCOMES = [
    "self-serve onboarding for new teams",
    "safer deploys with progressive delivery",
    "near real-time reporting for stakeholders",
    "better auditability and compliance",
    "faster incident triage",
    "faster UI iteration with reusable components",
]

# -----------------------------
# Profiles (bias content/skills)
# -----------------------------

PROFILES = {
    "backend": {
        "titles": ["Backend Engineer", "Software Engineer", "Senior Software Engineer", "Platform Engineer"],
        "focus": ["distributed systems", "API design", "performance tuning", "cloud infrastructure"],
        "bias": {
            "Languages": ["Go", "Java", "Kotlin", "Python", "SQL"],
            "Frameworks": ["Spring Boot", "FastAPI", "gRPC", "Django", "Node.js"],
            "Data": ["PostgreSQL", "Redis", "Kafka"],
            "Cloud": ["AWS", "Kubernetes", "Terraform", "Docker"],
        },
    },
    "frontend": {
        "titles": ["Frontend Engineer", "Full Stack Engineer", "Software Engineer"],
        "focus": ["product-minded engineering", "performance tuning", "API design"],
        "bias": {
            "Languages": ["TypeScript", "JavaScript", "HTML/CSS", "Python"],
            "Frameworks": ["React", "Next.js", "Node.js"],
            "Practices": ["TDD", "Observability"],
        },
    },
    "fullstack": {
        "titles": ["Full Stack Engineer", "Software Engineer", "Senior Software Engineer"],
        "focus": ["product-minded engineering", "API design", "cloud infrastructure"],
        "bias": {
            "Languages": ["TypeScript", "Python", "Go", "SQL"],
            "Frameworks": ["React", "Next.js", "FastAPI", "Node.js"],
            "Cloud": ["AWS", "Docker", "Terraform"],
            "Data": ["PostgreSQL", "Redis"],
        },
    },
    "sre": {
        "titles": ["Site Reliability Engineer", "Platform Engineer", "DevOps Engineer"],
        "focus": ["incident response", "observability", "cloud infrastructure", "performance tuning"],
        "bias": {
            "Cloud": ["Kubernetes", "Terraform", "AWS", "GCP", "Docker", "Helm"],
            "Practices": ["SRE", "Observability", "Threat Modeling"],
            "Languages": ["Go", "Python", "Bash", "SQL"],
        },
    },
    "devops": {
        "titles": ["DevOps Engineer", "Platform Engineer", "Site Reliability Engineer"],
        "focus": ["CI/CD automation", "cloud infrastructure", "observability"],
        "bias": {
            "Cloud": ["Terraform", "Kubernetes", "Docker", "Helm", "AWS", "Azure"],
            "Languages": ["Bash", "Python", "Go"],
            "Data": ["PostgreSQL", "Redis"],
        },
    },
    "data": {
        "titles": ["Data Engineer", "Software Engineer", "Platform Engineer"],
        "focus": ["data pipelines", "distributed systems", "cloud infrastructure"],
        "bias": {
            "Languages": ["Python", "SQL", "Go"],
            "Data": ["Kafka", "Airflow", "dbt", "BigQuery", "Snowflake", "PostgreSQL"],
            "Cloud": ["GCP", "AWS", "Terraform", "Kubernetes"],
        },
    },
    "ml": {
        "titles": ["Machine Learning Engineer", "Data Engineer", "Software Engineer"],
        "focus": ["MLOps", "data pipelines", "cloud infrastructure"],
        "bias": {
            "Languages": ["Python", "SQL"],
            "Data": ["BigQuery", "Snowflake", "Airflow", "Kafka"],
            "Cloud": ["AWS", "GCP", "Docker", "Kubernetes"],
            "Practices": ["Observability", "TDD"],
        },
    },
    "security": {
        "titles": ["Security Engineer", "Platform Engineer", "Software Engineer"],
        "focus": ["security hardening", "threat modeling", "cloud infrastructure"],
        "bias": {
            "Cloud": ["AWS", "GCP", "Terraform", "Kubernetes"],
            "Practices": ["Threat Modeling", "Observability"],
            "Languages": ["Python", "Go", "Bash"],
        },
    },
}
PROFILE_NAMES = tuple(PROFILES.keys())

# -----------------------------
# Helpers
# -----------------------------

def pick_many(rng: random.Random, items: list[str], k_min: int, k_max: int) -> list[str]:
    k = rng.randint(k_min, k_max)
    if not items:
        return []
    if k >= len(items):
        items2 = items[:]
        rng.shuffle(items2)
        return items2
    return rng.sample(items, k=k)

def make_email(first: str, last: str, rng: random.Random) -> str:
    local = f"{first}.{last}".lower().replace(" ", "").replace("'", "")
    return f"{local}@{rng.choice(EMAIL_DOMAINS)}"

def make_phone(rng: random.Random) -> str:
    prefix = rng.choice(PHONE_PREFIXES)
    groups = [rng.randint(0, 99) for _ in range(4)]
    return f"{prefix} " + " ".join(f"{g:02d}" for g in groups)

def month_year(rng: random.Random, start_year: int, end_year: int) -> str:
    y = rng.randint(start_year, end_year)
    m = rng.randint(1, 12)
    return f"{date(y, m, 1):%b %Y}"

def make_date_range(rng: random.Random, end_year: int) -> tuple[str, str]:
    start_y = rng.randint(end_year - 8, end_year - 2)
    end_y = rng.randint(start_y + 1, end_year)
    start = month_year(rng, start_y, start_y)
    end = "Present" if (end_y == end_year and rng.random() < 0.35) else month_year(rng, end_y, end_y)
    return start, end

def safe_text(s: str) -> str:
    return (s.replace("–", "-")
             .replace("—", "-")
             .replace("’", "'")
             .replace("“", '"')
             .replace("”", '"'))

def weighted_unique_pick(rng: random.Random, base: list[str], bias: list[str], k: int) -> list[str]:
    pool = base[:] + bias[:] + bias[:]  # bias x2
    out: list[str] = []
    seen = set()
    attempts = 0
    while len(out) < k and attempts < 500:
        attempts += 1
        item = rng.choice(pool)
        if item in seen:
            continue
        if item not in base and item not in bias:
            continue
        seen.add(item)
        out.append(item)
    if len(out) < k:
        leftovers = [x for x in base if x not in seen]
        rng.shuffle(leftovers)
        out.extend(leftovers[: (k - len(out))])
    return out

# -----------------------------
# Resume model
# -----------------------------

@dataclass
class Resume:
    name: str
    title: str
    location: str
    email: str
    phone: str
    links: list[str]
    summary: str
    skills: dict[str, list[str]]
    experience: list[dict]
    education: list[dict]
    projects: list[dict]
    certifications: list[str]
    languages: list[tuple[str, str]]
    profile: str
    template: str

def generate_resume(rng: random.Random, profile: str, template: str) -> Resume:
    prof = PROFILES[profile]

    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    name = f"{first} {last}"

    title = rng.choice(prof["titles"])
    location = rng.choice(CITIES)
    email = make_email(first, last, rng)
    phone = make_phone(rng)

    links = [
        f"linkedin.com/in/{first.lower()}{last.lower()}",
        f"github.com/{first.lower()}{last.lower()}",
    ]
    if rng.random() < 0.35:
        links.append(f"{first.lower()}{last.lower()}.dev")

    years = rng.randint(2, 12)
    domain = rng.choice(DOMAINS)
    focus = rng.choice(prof["focus"])
    summary = rng.choice(SUMMARY_TEMPLATES).format(years=years, domain=domain, focus=focus, role=title)

    skills: dict[str, list[str]] = {}
    for bucket, items in SKILL_BUCKETS.items():
        bias = prof["bias"].get(bucket, [])
        k = rng.randint(4, 6) if bucket in ("Languages", "Cloud") else rng.randint(3, 6)
        skills[bucket] = weighted_unique_pick(rng, items, bias, k)

    exp_count = rng.randint(2, 4)
    experience = []
    current_year = date.today().year
    flat_skills = list({x for xs in skills.values() for x in xs})
    bias_flat = list({x for xs in prof["bias"].values() for x in xs})

    for i in range(exp_count):
        company = rng.choice(COMPANIES)
        industry = rng.choice(INDUSTRIES)
        role = rng.choice(prof["titles"] if i == 0 else ROLE_TITLES)
        start, end = make_date_range(rng, current_year)

        bullets = []
        for _ in range(rng.randint(3, 5)):
            t = rng.choice(BULLET_LIBRARY)
            bullets.append(t.format(
                thing=rng.choice(THINGS),
                metric=rng.choice(METRICS),
                pct=rng.randint(12, 65),
                from_=rng.randint(120, 950),
                to=rng.randint(30, 200),
                old=rng.choice(["VM-based services", "a monolith", "Jenkins pipelines", "manual deploys"]),
                new=rng.choice(["Kubernetes", "GitHub Actions", "Terraform", "service mesh", "event-driven architecture"]),
                tech=rng.choice(TECHS),
                outcome=rng.choice(OUTCOMES),
                practice=rng.choice(PRACTICES),
            ))

        stack = weighted_unique_pick(rng, flat_skills, bias_flat, rng.randint(6, 9))

        experience.append({
            "company": company,
            "industry": industry,
            "role": role,
            "start": start,
            "end": end,
            "stack": stack,
            "bullets": bullets,
        })

    edu_count = 1 if rng.random() < 0.75 else 2
    education = []
    for _ in range(edu_count):
        deg, major = rng.choice(DEGREES)
        school = rng.choice(SCHOOLS)
        grad_year = rng.randint(current_year - 14, current_year - 2)
        education.append({"degree": f"{deg} in {major}", "school": school, "year": str(grad_year)})

    proj_count = rng.randint(2, 3)
    projects = []
    for _ in range(proj_count):
        pn = rng.choice(PROJECT_NOUNS)
        focus2 = rng.choice(prof["focus"])
        techs = pick_many(rng, list({*TECHS, *flat_skills}), 2, 4)
        desc = (
            f"Built {pn.lower()} using {', '.join(techs)}. "
            f"Focused on {focus2} and {rng.choice(['DX', 'reliability', 'security', 'cost efficiency'])}."
        )
        projects.append({
            "name": pn,
            "desc": desc,
            "bullets": [
                f"Implemented core services and APIs; achieved {rng.randint(99, 999)} req/s in load tests.",
                f"Added observability (logs, metrics, traces); reduced triage time by {rng.randint(15, 60)}%.",
            ],
        })

    cert_pool = CERTIFICATIONS[:]
    if profile in ("sre", "devops"):
        cert_pool += ["AWS Certified DevOps Engineer - Professional", "CKS: Certified Kubernetes Security Specialist"]
    if profile == "security":
        cert_pool += ["(ISC)² CC (Certified in Cybersecurity)", "CompTIA Security+"]
    if profile in ("data", "ml"):
        cert_pool += ["Google Professional Data Engineer", "Databricks Certified Associate Developer"]

    certs = pick_many(rng, cert_pool, 0, 2)

    langs = pick_many(rng, [f"{l} ({lvl})" for l, lvl in LANGUAGES], 2, 3)
    languages: list[tuple[str, str]] = []
    for item in langs:
        if "(" in item and item.endswith(")"):
            lang = item.split(" (", 1)[0]
            lvl = item.split(" (", 1)[1][:-1]
            languages.append((lang, lvl))
        else:
            languages.append((item, ""))

    return Resume(
        name=safe_text(name),
        title=safe_text(title),
        location=safe_text(location),
        email=safe_text(email),
        phone=safe_text(phone),
        links=[safe_text(x) for x in links],
        summary=safe_text(summary),
        skills={k: [safe_text(x) for x in v] for k, v in skills.items()},
        experience=[{
            **e,
            "company": safe_text(e["company"]),
            "industry": safe_text(e["industry"]),
            "role": safe_text(e["role"]),
            "start": safe_text(e["start"]),
            "end": safe_text(e["end"]),
            "stack": [safe_text(x) for x in e["stack"]],
            "bullets": [safe_text(x) for x in e["bullets"]],
        } for e in experience],
        education=[{k: safe_text(v) for k, v in ed.items()} for ed in education],
        projects=[{
            **p,
            "name": safe_text(p["name"]),
            "desc": safe_text(p["desc"]),
            "bullets": [safe_text(x) for x in p["bullets"]],
        } for p in projects],
        certifications=[safe_text(x) for x in certs],
        languages=languages,
        profile=profile,
        template=template,
    )

# -----------------------------
# Styling / Themes
# -----------------------------

@dataclass
class Theme:
    name: str
    accent: colors.Color
    text: colors.Color
    subtle: colors.Color
    rule: colors.Color
    sidebar_bg: colors.Color | None = None

THEMES = {
    "classic": Theme("classic", colors.HexColor("#111111"), colors.HexColor("#111111"),
                     colors.HexColor("#444444"), colors.HexColor("#DDDDDD")),
    "modern": Theme("modern", colors.HexColor("#0B5FFF"), colors.HexColor("#111111"),
                    colors.HexColor("#404040"), colors.HexColor("#E6E6E6")),
    "sidebar": Theme("sidebar", colors.HexColor("#2D6A4F"), colors.HexColor("#111111"),
                     colors.HexColor("#3A3A3A"), colors.HexColor("#E6E6E6"),
                     sidebar_bg=colors.HexColor("#F4F7F6")),
    "mono": Theme("mono", colors.HexColor("#000000"), colors.HexColor("#111111"),
                  colors.HexColor("#444444"), colors.HexColor("#E1E1E1")),
    "warm": Theme("warm", colors.HexColor("#8C2F39"), colors.HexColor("#111111"),
                  colors.HexColor("#3E3E3E"), colors.HexColor("#E6E6E6")),
}

def build_styles(theme: Theme):
    base = getSampleStyleSheet()
    s_name = ParagraphStyle("Name", parent=base["Title"], fontName="Helvetica-Bold",
                            fontSize=20, leading=24, spaceAfter=4, textColor=theme.text)
    s_title = ParagraphStyle("RoleTitle", parent=base["Normal"], fontName="Helvetica",
                             fontSize=11, leading=14, spaceAfter=8, textColor=theme.subtle)
    s_meta = ParagraphStyle("Meta", parent=base["Normal"], fontName="Helvetica",
                            fontSize=9.5, leading=12, textColor=theme.subtle)
    s_h2 = ParagraphStyle("H2", parent=base["Heading2"], fontName="Helvetica-Bold",
                          fontSize=10.8, leading=14, spaceBefore=10, spaceAfter=6,
                          textColor=theme.accent if theme.name != "classic" else theme.text,
                          letterSpacing=0.2)
    s_body = ParagraphStyle("Body", parent=base["Normal"], fontName="Helvetica",
                            fontSize=10, leading=13, textColor=theme.text)
    s_small = ParagraphStyle("Small", parent=s_body, fontSize=9, leading=11, textColor=theme.subtle)
    s_bullet = ParagraphStyle("Bullet", parent=s_body, leftIndent=12, bulletIndent=0, spaceBefore=1, spaceAfter=1)
    return {"name": s_name, "title": s_title, "meta": s_meta, "h2": s_h2, "body": s_body, "small": s_small, "bullet": s_bullet, "theme": theme}

# -----------------------------
# Content blocks (shared)
# -----------------------------

def block_header(resume: Resume, st) -> list:
    theme: Theme = st["theme"]
    story = [
        Paragraph(resume.name, st["name"]),
        Paragraph(resume.title, st["title"]),
    ]
    meta_left = f"{resume.location}  |  {resume.email}  |  {resume.phone}"
    meta_right = "  |  ".join(resume.links)
    meta_tbl = Table([[Paragraph(meta_left, st["meta"]), Paragraph(meta_right, st["meta"])]],
                     colWidths=[3.4 * inch, 3.6 * inch])
    meta_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                  ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [meta_tbl, Spacer(1, 8), HRFlowable(width="100%", thickness=1, color=theme.rule), Spacer(1, 10)]
    return story

def block_summary(resume: Resume, st) -> list:
    return [Paragraph("SUMMARY", st["h2"]), Paragraph(resume.summary, st["body"])]

def block_skills_table(resume: Resume, st) -> list:
    rows = []
    for bucket in ["Languages", "Frameworks", "Cloud", "Data", "Practices"]:
        items = resume.skills.get(bucket, [])
        if items:
            rows.append([Paragraph(f"<b>{bucket}:</b>", st["small"]),
                         Paragraph(", ".join(items), st["small"])])
    tbl = Table(rows, colWidths=[1.35 * inch, 5.65 * inch])
    tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                             ("TOPPADDING", (0, 0), (-1, -1), 2),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return [Paragraph("SKILLS", st["h2"]), tbl]

def block_experience(resume: Resume, st) -> list:
    story = [Paragraph("EXPERIENCE", st["h2"])]
    for e in resume.experience:
        header = f"<b>{e['role']}</b> - {e['company']} ({e['industry']})"
        daterange = f"{e['start']} - {e['end']}"
        header_tbl = Table([[Paragraph(header, st["body"]), Paragraph(daterange, st["body"])]],
                           colWidths=[5.2 * inch, 1.8 * inch])
        header_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        bullets = [Paragraph(f"<i>Tech:</i> {', '.join(e['stack'])}", st["small"])]
        for b in e["bullets"]:
            bullets.append(Paragraph(b, st["bullet"], bulletText="-"))
        story.append(KeepTogether([header_tbl] + bullets + [Spacer(1, 6)]))
    return story

def block_projects(resume: Resume, st) -> list:
    story = [Paragraph("PROJECTS", st["h2"])]
    for p in resume.projects:
        story.append(Paragraph(f"<b>{p['name']}</b>", st["body"]))
        story.append(Paragraph(p["desc"], st["small"]))
        for b in p["bullets"]:
            story.append(Paragraph(b, st["bullet"], bulletText="-"))
        story.append(Spacer(1, 6))
    return story

def block_education(resume: Resume, st) -> list:
    story = [Paragraph("EDUCATION", st["h2"])]
    for ed in resume.education:
        story.append(Paragraph(f"<b>{ed['degree']}</b> - {ed['school']} ({ed['year']})", st["body"]))
    return story

def block_certs_and_langs(resume: Resume, st) -> list:
    story = []
    if resume.certifications:
        story.append(Paragraph("CERTIFICATIONS", st["h2"]))
        for c in resume.certifications:
            story.append(Paragraph(c, st["bullet"], bulletText="-"))
    story.append(Paragraph("LANGUAGES", st["h2"]))
    lang_line = ", ".join([f"{l} ({lvl})" if lvl else l for l, lvl in resume.languages])
    story.append(Paragraph(lang_line, st["body"]))
    return story

# -----------------------------
# Templates
# -----------------------------

TEMPLATES = ("classic", "sidebar", "modern", "clean", "split")

def build_pdf_classic(resume: Resume, out_path: str) -> None:
    st = build_styles(THEMES["classic"])
    doc = SimpleDocTemplate(out_path, pagesize=LETTER,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.65 * inch, bottomMargin=0.65 * inch,
                            title=f"Resume - {resume.name}", author=resume.name)
    story = []
    story += block_header(resume, st)
    story += block_summary(resume, st)
    story += block_skills_table(resume, st)
    story += block_experience(resume, st)
    story += block_projects(resume, st)
    story += block_education(resume, st)
    story += block_certs_and_langs(resume, st)
    doc.build(story)

def build_pdf_sidebar(resume: Resume, out_path: str) -> None:
    st = build_styles(THEMES["sidebar"])
    theme: Theme = st["theme"]

    page_w, page_h = LETTER
    margin_l = 0.6 * inch
    margin_r = 0.6 * inch
    margin_t = 0.6 * inch
    margin_b = 0.6 * inch
    gutter = 0.25 * inch
    sidebar_w = 2.05 * inch

    main_w = page_w - margin_l - margin_r - gutter - sidebar_w
    height = page_h - margin_t - margin_b

    sidebar_frame = Frame(margin_l, margin_b, sidebar_w, height, 0, 0, 0, 0, showBoundary=0)
    main_frame = Frame(margin_l + sidebar_w + gutter, margin_b, main_w, height, 0, 0, 0, 0, showBoundary=0)

    def on_page(canvas, doc_):
        canvas.saveState()
        canvas.setFillColor(theme.sidebar_bg or colors.HexColor("#F5F5F5"))
        canvas.rect(margin_l - 0.12 * inch, margin_b - 0.12 * inch,
                    sidebar_w + 0.24 * inch, height + 0.24 * inch, stroke=0, fill=1)
        canvas.restoreState()

    doc = BaseDocTemplate(out_path, pagesize=LETTER,
                          leftMargin=margin_l, rightMargin=margin_r, topMargin=margin_t, bottomMargin=margin_b,
                          title=f"Resume - {resume.name}", author=resume.name)
    doc.addPageTemplates([PageTemplate(id="TwoCol", frames=[sidebar_frame, main_frame], onPage=on_page)])

    sb_name = ParagraphStyle("SBName", parent=st["name"], fontSize=16, leading=19, spaceAfter=2)
    sb_title = ParagraphStyle("SBTitle", parent=st["title"], fontSize=10, leading=12, spaceAfter=8)
    sb_h = ParagraphStyle("SBH", parent=st["h2"], fontSize=9.5, spaceBefore=6, spaceAfter=4, textColor=theme.accent)
    sb_item = ParagraphStyle("SBItem", parent=st["small"], leftIndent=0)

    story = []
    story.append(Paragraph(resume.name, sb_name))
    story.append(Paragraph(resume.title, sb_title))

    story.append(Paragraph("<b>CONTACT</b>", sb_h))
    story.append(Paragraph(resume.location, sb_item))
    story.append(Paragraph(resume.email, sb_item))
    story.append(Paragraph(resume.phone, sb_item))
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>LINKS</b>", sb_h))
    for link in resume.links:
        story.append(Paragraph(link, sb_item))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>SKILLS</b>", sb_h))
    for bucket in ["Languages", "Frameworks", "Cloud", "Data", "Practices"]:
        items = resume.skills.get(bucket, [])
        if items:
            story.append(Paragraph(f"<b>{bucket}</b>", ParagraphStyle(f"SB{bucket}", parent=st["small"],
                                                                     spaceBefore=4, spaceAfter=1, textColor=theme.text)))
            story.append(Paragraph(", ".join(items), sb_item))

    story.append(Spacer(1, 10))
    if resume.certifications:
        story.append(Paragraph("<b>CERTS</b>", sb_h))
        for c in resume.certifications:
            story.append(Paragraph(c, ParagraphStyle("SBCert", parent=st["small"], leftIndent=8), bulletText="•"))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>LANGUAGES</b>", sb_h))
    for l, lvl in resume.languages:
        story.append(Paragraph(f"{l} - {lvl}", sb_item))

    story.append(Spacer(1, 2))
    story.append(Paragraph("SUMMARY", st["h2"]))
    story.append(Paragraph(resume.summary, st["body"]))
    story.append(Spacer(1, 4))
    story += block_experience(resume, st)
    story += block_projects(resume, st)
    story += block_education(resume, st)

    doc.build(story)

def build_pdf_modern(resume: Resume, out_path: str) -> None:
    st = build_styles(THEMES["modern"])
    theme: Theme = st["theme"]

    page_w, page_h = LETTER
    margin_l = 0.75 * inch
    margin_r = 0.75 * inch
    margin_t = 0.85 * inch
    margin_b = 0.65 * inch

    def on_page(canvas, doc_):
        canvas.saveState()
        canvas.setFillColor(theme.accent)
        canvas.rect(0, page_h - 0.35 * inch, page_w, 0.35 * inch, stroke=0, fill=1)
        canvas.restoreState()

    doc = BaseDocTemplate(out_path, pagesize=LETTER,
                          leftMargin=margin_l, rightMargin=margin_r, topMargin=margin_t, bottomMargin=margin_b,
                          title=f"Resume - {resume.name}", author=resume.name)
    frame = Frame(margin_l, margin_b, page_w - margin_l - margin_r, page_h - margin_t - margin_b, 0, 0, 0, 0, showBoundary=0)
    doc.addPageTemplates([PageTemplate(id="Modern", frames=[frame], onPage=on_page)])

    st2 = dict(st)
    st2["name"] = ParagraphStyle("MName", parent=st["name"], fontSize=21, spaceAfter=2)
    st2["title"] = ParagraphStyle("MTitle", parent=st["title"], fontSize=10.8, spaceAfter=10)
    st2["h2"] = ParagraphStyle("MH2", parent=st["h2"], fontSize=11, spaceBefore=10, spaceAfter=6, textColor=theme.accent)

    story = []
    story.append(Paragraph(resume.name, st2["name"]))
    story.append(Paragraph(resume.title, st2["title"]))
    meta = f"{resume.location}  |  {resume.email}  |  {resume.phone}  |  " + "  |  ".join(resume.links)
    story.append(Paragraph(meta, st2["meta"]))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=theme.rule))
    story.append(Spacer(1, 10))

    story += block_summary(resume, st2)

    # 2-col skills rows
    story.append(Paragraph("SKILLS", st2["h2"]))
    pairs = []
    for b in ["Languages", "Frameworks", "Cloud", "Data", "Practices"]:
        items = resume.skills.get(b, [])
        if items:
            pairs.append(Paragraph(f"<b>{b}</b>: {', '.join(items)}", st2["small"]))
    col1 = pairs[::2]
    col2 = pairs[1::2]
    rows = []
    for i in range(max(len(col1), len(col2), 1)):
        rows.append([col1[i] if i < len(col1) else Paragraph("", st2["small"]),
                     col2[i] if i < len(col2) else Paragraph("", st2["small"])])
    tbl = Table(rows, colWidths=[3.35 * inch, 3.65 * inch])
    tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                             ("TOPPADDING", (0, 0), (-1, -1), 2),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story.append(tbl)

    story += block_experience(resume, st2)
    story += block_projects(resume, st2)
    story += block_education(resume, st2)
    story += block_certs_and_langs(resume, st2)

    doc.build(story)

def build_pdf_clean(resume: Resume, out_path: str) -> None:
    st = build_styles(THEMES["mono"])
    theme: Theme = st["theme"]
    st2 = dict(st)
    st2["h2"] = ParagraphStyle("CH2", parent=st["h2"], fontSize=10.2, spaceBefore=8, spaceAfter=4, textColor=theme.text)
    st2["title"] = ParagraphStyle("CTitle", parent=st["title"], spaceAfter=6)

    doc = SimpleDocTemplate(out_path, pagesize=LETTER,
                            leftMargin=0.8 * inch, rightMargin=0.8 * inch,
                            topMargin=0.65 * inch, bottomMargin=0.65 * inch,
                            title=f"Resume - {resume.name}", author=resume.name)
    story = []
    story += block_header(resume, st2)
    story += block_summary(resume, st2)
    story += block_skills_table(resume, st2)
    story += block_experience(resume, st2)
    story += block_education(resume, st2)
    story += block_projects(resume, st2)
    story += block_certs_and_langs(resume, st2)
    doc.build(story)

def build_pdf_split(resume: Resume, out_path: str) -> None:
    st = build_styles(THEMES["warm"])
    theme: Theme = st["theme"]

    doc = SimpleDocTemplate(out_path, pagesize=LETTER,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.65 * inch, bottomMargin=0.65 * inch,
                            title=f"Resume - {resume.name}", author=resume.name)

    story = []

    left = [Paragraph(resume.name, st["name"]), Paragraph(resume.title, st["title"])]
    right_lines = [resume.location, resume.email, resume.phone, *resume.links]
    right = [Paragraph("<br/>".join(right_lines), st["meta"])]

    header_tbl = Table([[left, right]], colWidths=[4.2 * inch, 2.8 * inch])
    header_tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(header_tbl)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1, color=theme.rule))
    story.append(Spacer(1, 10))

    story += block_summary(resume, st)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=theme.rule))
    story.append(Spacer(1, 6))
    story += block_skills_table(resume, st)

    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=theme.rule))
    story.append(Spacer(1, 6))
    story += block_experience(resume, st)
    story += block_projects(resume, st)
    story += block_education(resume, st)
    story += block_certs_and_langs(resume, st)

    doc.build(story)

TEMPLATE_BUILDERS = {
    "classic": build_pdf_classic,
    "sidebar": build_pdf_sidebar,
    "modern": build_pdf_modern,
    "clean": build_pdf_clean,
    "split": build_pdf_split,
}

def build_pdf(resume: Resume, out_path: str, template: str) -> None:
    try:
        fn = TEMPLATE_BUILDERS[template]
    except KeyError:
        raise ValueError(f"Unknown template '{template}'. Choose one of: {', '.join(TEMPLATES)}")
    fn(resume, out_path)

# -----------------------------
# Batch generation
# -----------------------------

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def make_filename(pattern: str, i: int, resume: Resume) -> str:
    """
    pattern placeholders:
      {i}        -> 1-based index
      {profile}  -> chosen profile
      {template} -> chosen template
      {name}     -> "First_Last"
    """
    safe_name = resume.name.replace(" ", "_")
    return pattern.format(i=i, profile=resume.profile, template=resume.template, name=safe_name)

# -----------------------------
# CLI
# -----------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Generate random tech resume PDFs (batch supported).")
    ap.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")

    # Output: either --out for single, or --out-dir for batch
    ap.add_argument("--out", default=None, help="Output PDF path (single file). If omitted, batch mode is used.")
    ap.add_argument("--out-dir", default="out", help="Output directory for batch mode (default: ./out)")
    ap.add_argument("--count", type=int, default=10, help="How many PDFs to generate in batch mode (default: 10)")
    ap.add_argument("--pattern", default="resume_{i:03d}_{profile}_{template}_{name}.pdf",
                    help="Filename pattern in batch mode. Placeholders: {i}, {profile}, {template}, {name}")

    ap.add_argument("--template", choices=TEMPLATES, default=None, help="Template (random if omitted)")
    ap.add_argument("--profile", choices=PROFILE_NAMES, default=None, help="Profile (random if omitted)")

    # Optional: randomize per-file even if fixed template/profile provided
    ap.add_argument("--randomize-template", action="store_true",
                    help="Choose a random template per file (overrides --template per file)")
    ap.add_argument("--randomize-profile", action="store_true",
                    help="Choose a random profile per file (overrides --profile per file)")

    args = ap.parse_args()

    rng = random.Random(args.seed)

    # Single-file mode
    if args.out:
        template = args.template or rng.choice(TEMPLATES)
        profile = args.profile or rng.choice(PROFILE_NAMES)
        resume = generate_resume(rng=rng, profile=profile, template=template)
        build_pdf(resume, args.out, template=template)
        print(f"Wrote {args.out}")
        print(f"Template: {template}")
        print(f"Profile:  {profile}")
        return 0

    # Batch mode
    ensure_dir(args.out_dir)
    written = 0

    for idx in range(1, args.count + 1):
        template = rng.choice(TEMPLATES) if (args.randomize_template or args.template is None) else args.template
        profile = rng.choice(PROFILE_NAMES) if (args.randomize_profile or args.profile is None) else args.profile

        resume = generate_resume(rng=rng, profile=profile, template=template)
        filename = make_filename(args.pattern, idx, resume)
        out_path = os.path.join(args.out_dir, filename)

        build_pdf(resume, out_path, template=template)
        written += 1

    print(f"Wrote {written} PDFs to {args.out_dir}")
    if args.seed is None:
        print("Tip: pass --seed N to reproduce the same batch.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
