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
    "Blake", "Hayden", "Logan", "Carter", "Sage", "Rowan", "Phoenix", "River",
    "Skyler", "Aidan", "Jesse", "Mackenzie", "Harper", "Elliot", "Nico",
    "Valentina", "Isabella", "Sofia", "Camila", "Gabriela", "Lucia", "Carla",
    "Ana", "Maria", "Elena", "Cristina", "Monica", "Patricia", "Silvia",
    "Hiroshi", "Kenji", "Takeshi", "Yuki", "Haruki", "Satoshi", "Akira",
    "Wei", "Li", "Zhang", "Chen", "Liu", "Yang", "Xu", "Huang", "Zhao",
    "Ahmed", "Mohammed", "Ali", "Omar", "Youssef", "Hassan", "Karim", "Samir",
    "Olga", "Natalia", "Ekaterina", "Anastasia", "Marina", "Svetlana", "Irina",
    "Lars", "Anders", "Johan", "Erik", "Magnus", "Sven", "Bjorn", "Nils",
    "Luca", "Matteo", "Alessandro", "Francesco", "Antonio", "Giovanni", "Marco",
    "Juan", "Carlos", "Miguel", "Javier", "Jose", "Francisco", "Pedro", "Luis",
]
LAST_NAMES = [
    "Nguyen", "Martin", "Bernard", "Dubois", "Lefevre", "Garcia", "Rossi",
    "Patel", "Kim", "Singh", "Lopez", "Hernandez", "Kowalski", "Andersen",
    "Novak", "Sato", "Suzuki", "Takahashi", "Tanaka", "Watanabe", "Ito",
    "Zhang", "Li", "Wang", "Chen", "Liu", "Yang", "Huang", "Zhao", "Wu",
    "Ahmed", "Mohammed", "Ali", "Hassan", "Khan", "Abdullah", "Ibrahim", "Saleh",
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson",
    "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee",
    "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez",
    "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright",
    "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson",
    "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts",
    "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker", "Cruz", "Edwards",
    "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy", "Cook",
    "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson", "Bailey",
    "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson",
    "Watson", "Brooks", "Chavez", "Wood", "Mendoza", "Ruiz", "Hughes", "Price",
    "Alvarez", "Castillo", "Sanders", "Gonzales", "Harrison", "Fernandez",
    "Castillo", "Schmidt", "Muller", "Schneider", "Fischer", "Weber", "Meyer",
    "Wagner", "Becker", "Schulz", "Hoffmann", "Schwarz", "Klein", "Richter",
    "Braun", "Hofmann", "Koch", "Gonzalez", "Gomez", "Fernandez", "Torres",
    "Diaz", "Perez", "Sanchez", "Ramirez", "Vargas", "Mendoza", "Castro",
    "Rojas", "Silva", "Romero", "Suarez", "Jimenez", "Cruz", "Lopez", "Gomez",
    "Peterson", "Johansson", "Karlsson", "Nilsson", "Eriksson", "Larsson",
    "Olsson", "Persson", "Svensson", "Gustafsson", "Pettersson", "Jonsson",
    "Jansson", "Hansson", "Jensen", "Nielsen", "Hansen", "Pedersen", "Andersen",
    "Christensen", "Larsen", "Sorensen", "Rasmussen", "Ivanov", "Petrov",
    "Sidorov", "Smirnov", "Kuznetsov", "Popov", "Vasiliev", "Romanov", "Nikolaev",
    "Sergeev", "Pavlov", "Stepanov", "Kuzmina", "Ivanova", "Petrova", "Sidorova",
    "Moreau", "Leroy", "Bertrand", "Dupont", "Martin", "Simon", "Durand",
    "Michel", "Lefevre", "Lopez", "Garcia", "Sanchez", "Martin", "Gonzalez",
    "Rodriguez", "Fernandez", "Lopez", "Gomez", "Martin", "Jimenez", "Sanchez",
    "Perez", "Garcia", "Gonzalez", "Rodriguez", "Fernandez", "Lopez", "Gomez",
]

CITIES = [
    # France
    "Paris, FR", "Lyon, FR", "Marseille, FR", "Toulouse, FR", "Nantes, FR",
    "Bordeaux, FR", "Lille, FR", "Strasbourg, FR", "Rennes, FR", "Grenoble, FR",
    # Germany
    "Berlin, DE", "Munich, DE", "Hamburg, DE", "Frankfurt, DE", "Cologne, DE",
    "Stuttgart, DE", "Dusseldorf, DE", "Leipzig, DE", "Nuremberg, DE", "Dresden, DE",
    # Netherlands & Belgium
    "Amsterdam, NL", "Rotterdam, NL", "The Hague, NL", "Utrecht, NL", "Eindhoven, NL",
    "Brussels, BE", "Antwerp, BE", "Ghent, BE",
    # UK & Ireland
    "London, UK", "Manchester, UK", "Edinburgh, UK", "Bristol, UK", "Birmingham, UK",
    "Leeds, UK", "Glasgow, UK", "Cambridge, UK", "Oxford, UK",
    "Dublin, IE", "Cork, IE", "Galway, IE",
    # Spain & Portugal
    "Barcelona, ES", "Madrid, ES", "Valencia, ES", "Seville, ES", "Bilbao, ES",
    "Lisbon, PT", "Porto, PT",
    # Switzerland & Austria
    "Zurich, CH", "Geneva, CH", "Basel, CH", "Bern, CH",
    "Vienna, AT", "Graz, AT",
    # Nordics
    "Stockholm, SE", "Gothenburg, SE", "Malmo, SE",
    "Copenhagen, DK", "Aarhus, DK",
    "Oslo, NO", "Bergen, NO",
    "Helsinki, FI", "Espoo, FI",
    "Reykjavik, IS",
    # Italy
    "Milan, IT", "Rome, IT", "Turin, IT", "Florence, IT", "Bologna, IT",
    # Poland & Czech Republic
    "Warsaw, PL", "Krakow, PL", "Wroclaw, PL", "Gdansk, PL",
    "Prague, CZ", "Brno, CZ",
    # US
    "San Francisco, US", "New York, US", "Seattle, US", "Austin, US", "Boston, US",
    "Chicago, US", "Los Angeles, US", "Denver, US", "Atlanta, US", "Miami, US",
    "Portland, US", "San Diego, US", "Washington DC, US", "Minneapolis, US",
    # Canada
    "Toronto, CA", "Vancouver, CA", "Montreal, CA", "Ottawa, CA", "Calgary, CA",
    # Asia-Pacific
    "Tokyo, JP", "Osaka, JP", "Fukuoka, JP",
    "Singapore, SG",
    "Sydney, AU", "Melbourne, AU", "Brisbane, AU",
    "Seoul, KR", "Busan, KR",
    "Bangalore, IN", "Hyderabad, IN", "Pune, IN", "Mumbai, IN", "Chennai, IN",
    "Taipei, TW",
    "Hong Kong, HK",
    "Auckland, NZ",
    # Other
    "Tel Aviv, IL",
    "Dubai, AE",
    "Cape Town, ZA", "Johannesburg, ZA",
    "Sao Paulo, BR", "Buenos Aires, AR",
    "Mexico City, MX",
]
EMAIL_DOMAINS = [
    "example.com", "mail.com", "proton.me", "company.dev",
    "gmail.com", "outlook.com", "icloud.com", "hey.com",
    "dev.io", "eng.io", "tech.co", "work.dev",
    "fastmail.com", "tutanota.com", "pm.me",
    "live.com", "yahoo.com", "zoho.com",
]
PHONE_PREFIXES = [
    # France
    "+33 6", "+33 7",
    # UK
    "+44 7",
    # Germany
    "+49 15", "+49 16", "+49 17",
    # Netherlands
    "+31 6",
    # Spain
    "+34 6",
    # Portugal
    "+351 9",
    # Belgium
    "+32 4",
    # Switzerland
    "+41 7",
    # Sweden
    "+46 7",
    # Norway
    "+47 4", "+47 9",
    # Denmark
    "+45 2", "+45 3",
    # Finland
    "+358 4", "+358 5",
    # Italy
    "+39 3",
    # Poland
    "+48 5", "+48 6",
    # Ireland
    "+353 8",
    # Austria
    "+43 6",
    # US / Canada
    "+1 415", "+1 212", "+1 206", "+1 512", "+1 617",
    "+1 312", "+1 213", "+1 416", "+1 604",
    # India
    "+91 9", "+91 8",
    # Singapore
    "+65 8", "+65 9",
    # Australia
    "+61 4",
    # Japan
    "+81 9",
    # South Korea
    "+82 1",
    # Israel
    "+972 5",
    # UAE
    "+971 5",
    # Brazil
    "+55 11",
]

ROLE_TITLES = [
    # Individual contributor - general
    "Software Engineer", "Senior Software Engineer", "Staff Software Engineer",
    "Principal Software Engineer", "Distinguished Engineer",
    "Senior Staff Software Engineer", "Principal Engineer II",
    "Software Engineer II", "Software Engineer III",
    # Specialisations - backend
    "Backend Engineer", "Senior Backend Engineer", "Staff Backend Engineer",
    "API Engineer", "Microservices Engineer", "Backend Platform Engineer",
    # Specialisations - frontend
    "Frontend Engineer", "Senior Frontend Engineer", "Staff Frontend Engineer",
    "UI Engineer", "Web Engineer", "React Engineer",
    "Frontend Infrastructure Engineer", "Web Performance Engineer",
    # Full stack
    "Full Stack Engineer", "Senior Full Stack Engineer",
    "Full Stack Developer", "Software Developer",
    # Mobile
    "Mobile Engineer", "iOS Engineer", "Android Engineer",
    "Senior Mobile Engineer", "Staff Mobile Engineer",
    "React Native Engineer", "Flutter Engineer",
    "Mobile Platform Engineer", "Mobile SDK Engineer",
    # Embedded / systems
    "Embedded Systems Engineer", "Systems Engineer", "Firmware Engineer",
    "Low-Level Systems Engineer", "Kernel Engineer",
    # Platform / infra
    "Platform Engineer", "Senior Platform Engineer", "Staff Platform Engineer",
    "Infrastructure Engineer", "Cloud Infrastructure Engineer",
    "Site Reliability Engineer", "Senior Site Reliability Engineer",
    "Production Engineer", "Cloud Engineer", "Senior Cloud Engineer",
    "DevOps Engineer", "Senior DevOps Engineer",
    "Build & Release Engineer", "Release Engineer",
    "Infrastructure Automation Engineer",
    # Data & analytics
    "Data Engineer", "Senior Data Engineer", "Staff Data Engineer",
    "Analytics Engineer", "Senior Analytics Engineer",
    "Business Intelligence Engineer", "Data Platform Engineer",
    "Streaming Data Engineer", "Data Infrastructure Engineer",
    "ETL Engineer", "Data Warehouse Engineer",
    # AI / ML
    "Machine Learning Engineer", "Senior Machine Learning Engineer",
    "ML Platform Engineer", "AI/ML Engineer",
    "Data Scientist", "Senior Data Scientist", "Applied Scientist",
    "Research Engineer", "Research Scientist",
    "MLOps Engineer", "Computer Vision Engineer", "NLP Engineer",
    "LLM Engineer", "Generative AI Engineer", "AI Infrastructure Engineer",
    "Recommendation Systems Engineer", "Ranking Engineer",
    # Security
    "Security Engineer", "Senior Security Engineer", "Staff Security Engineer",
    "Application Security Engineer", "AppSec Engineer",
    "Cloud Security Engineer", "Infrastructure Security Engineer",
    "Security Software Engineer", "Product Security Engineer",
    "Penetration Tester", "Security Analyst",
    "Cryptography Engineer", "Identity & Access Engineer",
    # Quality & testing
    "Software Engineer in Test", "Senior Software Engineer in Test",
    "QA Engineer", "Senior QA Engineer", "QA Automation Engineer",
    "Automation Engineer", "Performance Test Engineer",
    "Quality Engineer", "Reliability Test Engineer",
    # Specialised IC
    "API Platform Engineer", "Developer Experience Engineer",
    "Database Engineer", "Senior Database Engineer",
    "Search Engineer", "Payments Engineer", "Commerce Engineer",
    "Distributed Systems Engineer", "Observability Engineer",
    "Performance Engineer", "Reliability Engineer",
    "Networking Engineer", "Storage Engineer",
    "Developer Productivity Engineer", "Internal Tools Engineer",
    "Developer Tools Engineer", "SDK Engineer",
    "Compiler Engineer", "Runtime Engineer",
    "Open Source Engineer", "Ecosystem Engineer",
    # Leadership / management
    "Tech Lead", "Senior Tech Lead", "Technical Lead",
    "Engineering Manager", "Senior Engineering Manager",
    "Director of Engineering", "Senior Director of Engineering",
    "VP of Engineering", "SVP of Engineering", "CTO",
    "Head of Platform", "Head of Data Engineering",
    "Head of Frontend", "Head of Backend",
    "Head of Infrastructure", "Head of Security",
    "Head of Developer Experience", "Group Engineering Manager",
    "Engineering Lead", "Principal Engineer",
    # Product / design-adjacent
    "Product Engineer", "Growth Engineer", "Founding Engineer",
    "Solutions Engineer", "Integration Engineer",
    "Technical Program Manager", "Staff Technical Program Manager",
]

SUMMARY_TEMPLATES = [
    "Tech worker with {years}+ years building {domain} systems. Strong in {focus} with a track record of shipping reliable products and improving developer velocity.",
    "Engineer with {years}+ years of experience in {domain}. Focused on {focus}, pragmatic architecture, and measurable outcomes.",
    "{role} with {years}+ years delivering {domain} solutions. Known for {focus} and cross-functional collaboration.",
    "Passionate {role} with {years}+ years in {domain}. Expertise in {focus}, scaling systems, and mentoring engineers.",
    "Hands-on {role} with {years}+ years of industry experience in {domain}. Champion of {focus} and continuous improvement.",
    "Versatile engineer with {years}+ years spanning {domain} and beyond. Driven by {focus} and a bias for pragmatic solutions.",
    "{years}+ year veteran of {domain} engineering. Deep specialization in {focus}; passionate about developer experience and system reliability.",
    "Builder and problem-solver with {years}+ years in {domain}. Committed to {focus}, clean APIs, and shipping with confidence.",
    "{role} with a {years}+ year track record in {domain}. Focused on {focus}, technical excellence, and high-impact delivery.",
    "Curious and delivery-focused {role} with {years}+ years in {domain}. Known for {focus}, strong ownership, and pragmatic trade-offs.",
]

DOMAINS = [
    "B2B SaaS", "fintech", "e-commerce", "healthtech", "developer tooling",
    "data platforms", "observability", "payments", "logistics", "media streaming",
    "adtech", "edtech", "legaltech", "proptech", "insuretech",
    "open-source infrastructure", "gaming", "cybersecurity", "IoT", "autonomous systems",
    "supply chain", "real estate tech", "climate tech", "HR tech", "martech",
    "embedded finance", "crypto / Web3", "retail tech", "travel tech", "foodtech",
]

FOCUS_AREAS = [
    "distributed systems", "cloud infrastructure", "API design", "data pipelines",
    "performance tuning", "security hardening", "MLOps", "CI/CD automation",
    "product-minded engineering", "incident response",
    "platform reliability", "developer experience", "cost optimisation",
    "event-driven architecture", "microservices design", "zero-downtime deployments",
    "data governance", "real-time processing", "shift-left testing",
    "infrastructure as code", "chaos engineering", "capacity planning",
    "service mesh adoption", "multi-cloud strategy", "edge computing",
    "privacy engineering", "accessibility engineering", "mobile performance",
]

SKILL_BUCKETS = {
    "Languages": [
        "Python", "TypeScript", "Go", "Java", "Kotlin", "C#", "SQL", "Bash",
        "Rust", "C++", "Ruby", "Scala", "Elixir", "Swift", "Dart", "R",
        "JavaScript", "PHP", "Lua", "Groovy", "Haskell", "Clojure",
    ],
    "Frameworks": [
        "Node.js", "FastAPI", "Spring Boot", "React", "Next.js", "Django", "gRPC",
        "Express.js", "NestJS", "Flask", "Gin", "Echo", "Fiber", "Actix",
        "Vue.js", "Angular", "Svelte", "Remix", "Astro", "SvelteKit",
        "Rails", "Phoenix", "Ktor", "Micronaut", "Quarkus", "Axum",
        "GraphQL", "tRPC", "Temporal", "Celery", "Sidekiq",
    ],
    "Cloud": [
        "AWS", "GCP", "Azure", "Terraform", "Kubernetes", "Docker", "Helm",
        "Pulumi", "Ansible", "ArgoCD", "Flux", "Istio", "Linkerd",
        "Prometheus", "Grafana", "Datadog", "New Relic", "Splunk",
        "Cloudflare", "Vercel", "Fly.io", "Render", "Railway",
        "AWS Lambda", "GCP Cloud Run", "Azure Functions",
        "OpenTelemetry", "Jaeger", "Loki", "Tempo",
    ],
    "Data": [
        "PostgreSQL", "Redis", "Kafka", "BigQuery", "Snowflake", "Airflow", "dbt",
        "MySQL", "MongoDB", "Cassandra", "Elasticsearch", "ClickHouse", "DuckDB",
        "Spark", "Flink", "Debezium", "Iceberg", "Delta Lake", "Hudi",
        "Redshift", "Databricks", "Fivetran", "Stitch", "Airbyte",
        "RabbitMQ", "NATS", "Pulsar", "EventBridge", "Kinesis",
        "Pinecone", "Weaviate", "Qdrant", "pgvector",
    ],
    "Practices": [
        "TDD", "DDD", "Clean Architecture", "Observability", "SRE", "Threat Modeling",
        "BDD", "Event Storming", "Hexagonal Architecture", "CQRS", "Event Sourcing",
        "GitOps", "Trunk-Based Development", "Pair Programming", "Mob Programming",
        "ADR (Architecture Decision Records)", "API-First Design", "Contract Testing",
        "Chaos Engineering", "Game Days", "Blameless Post-mortems",
        "Feature Flags", "Progressive Delivery", "Blue-Green Deployments",
        "Zero-Trust Security", "Supply Chain Security", "DORA Metrics",
    ],
}

COMPANIES = [
    # Original
    "CloudHarbor", "DataSpring", "PayLattice", "StreamForge", "MedNova",
    "LogiPilot", "InsightWorks", "DevBay", "SecureStack", "MarketPulse",
    # New fictitious tech companies
    "Nexlify", "Corewave", "Infraloop", "Vaultline", "Edgelayer",
    "Synapse IO", "Gridlock Labs", "Peakflow", "Argonaut Systems", "Driftwood AI",
    "Mintbase", "Prism Analytics", "Cobalt Platform", "Wavefront", "Ironclad Data",
    "Luminary Cloud", "Polaris Infra", "Horizon Payments", "Canopy Health", "Strata Security",
    "Orbit DevTools", "Cascade SaaS", "Apogee Logistics", "Vertex Media", "Zenith Finance",
    "Sprout Labs", "Torchlight AI", "Basecamp Platform", "Aether Networks", "Signal Commerce",
    "Ember AI", "Skyline DevOps", "Paragon Data", "Meridian Health", "Apex Security",
    "Flux Systems", "Nova Analytics", "Helix Platform", "Pinnacle SaaS", "Starboard Fintech",
]

INDUSTRIES = [
    "Fintech", "E-commerce", "Healthtech", "Developer Tools", "Logistics",
    "Media", "Security", "SaaS",
    "Adtech", "Edtech", "Legaltech", "Proptech", "Insuretech",
    "Gaming", "IoT", "Climate Tech", "HR Tech", "Martech",
    "Open Source", "AI / ML", "Crypto / Web3", "Retail Tech", "Travel Tech",
    "Automotive", "Telecommunications", "Government / Public Sector", "Non-profit Tech",
]

DEGREES = [
    ("BSc", "Computer Science"),
    ("BEng", "Software Engineering"),
    ("MSc", "Data Science"),
    ("MSc", "Cybersecurity"),
    ("BSc", "Mathematics"),
    ("BSc", "Information Systems"),
    ("BEng", "Computer Engineering"),
    ("MSc", "Artificial Intelligence"),
    ("MSc", "Computer Science"),
    ("MSc", "Software Engineering"),
    ("BSc", "Statistics"),
    ("BSc", "Physics"),
    ("MEng", "Software Engineering"),
    ("MBA", "Technology Management"),
    ("PhD", "Computer Science"),
    ("BSc", "Electrical Engineering"),
    ("BSc", "Cognitive Science"),
    ("MSc", "Human-Computer Interaction"),
    ("BSc", "Data Science"),
    ("MSc", "Information Security"),
]

SCHOOLS = [
    # France
    "Sorbonne Universite", "EPITA", "INSA Lyon", "Ecole Polytechnique", "CentraleSupelec",
    "Telecom Paris", "ENPC", "Paris-Saclay", "Grenoble INP",
    # Germany
    "TU Berlin", "TU Munich", "KIT (Karlsruhe)", "RWTH Aachen", "TU Dresden",
    "Hasso Plattner Institute", "TU Darmstadt",
    # UK & Ireland
    "University College Dublin", "Imperial College London", "University of Cambridge",
    "University of Oxford", "University of Edinburgh", "University College London",
    "University of Manchester", "University of Bristol",
    # Spain & Portugal
    "Universitat Politecnica de Catalunya", "Universidad Politecnica de Madrid",
    "Universidade do Porto",
    # Nordics
    "KTH Royal Institute of Technology", "Aalto University", "DTU (Denmark)",
    "NTNU (Norway)", "Uppsala University",
    # Netherlands & Belgium
    "University of Amsterdam", "TU Delft", "KU Leuven", "Ghent University",
    # Switzerland
    "ETH Zurich", "EPFL",
    # Italy & Poland
    "Politecnico di Milano", "University of Warsaw", "AGH University",
    # Asia & Americas
    "National University of Singapore", "IIT Bombay", "University of Toronto",
    "McGill University", "University of British Columbia",
    "Carnegie Mellon University", "MIT", "Stanford University",
    "UC Berkeley", "Georgia Tech",
]

PROJECT_NOUNS = [
    # Original
    "Feature Flag Platform", "Realtime Metrics Pipeline", "Billing Reconciliation",
    "Identity Gateway", "Search Relevance", "Cost Optimizer", "Release Orchestrator",
    "Fraud Detection Service", "Developer Portal", "Data Quality Monitor",
    # New
    "Rate Limiting Service", "Notification Fanout System", "Schema Registry",
    "API Mocking Framework", "Event Replay Engine", "Secrets Manager",
    "Multi-Region Failover Controller", "Traffic Shadowing Tool",
    "Observability SDK", "Self-Service Infrastructure Catalog",
    "License Compliance Scanner", "Dependency Vulnerability Tracker",
    "AI-Powered On-Call Assistant", "Automated Runbook Engine",
    "Zero-Downtime Migration Toolkit", "Canary Deployment Operator",
    "Internal Audit Trail Service", "Unified Logging Aggregator",
    "Service Mesh Migration Tool", "Distributed Tracing Dashboard",
    "ML Model Registry", "Feature Store", "Embedding Search Service",
    "LLM Gateway", "Prompt Versioning System",
    "Mobile SDK", "Design Token Pipeline", "Accessibility Linter",
]

CERTIFICATIONS = [
    "AWS Certified Solutions Architect - Associate",
    "AWS Certified Solutions Architect - Professional",
    "AWS Certified Developer - Associate",
    "AWS Certified SysOps Administrator - Associate",
    "AWS Certified DevOps Engineer - Professional",
    "AWS Certified Security - Specialty",
    "AWS Certified Machine Learning - Specialty",
    "CKA: Certified Kubernetes Administrator",
    "CKAD: Certified Kubernetes Application Developer",
    "CKS: Certified Kubernetes Security Specialist",
    "HashiCorp Certified: Terraform Associate",
    "HashiCorp Certified: Vault Associate",
    "Google Professional Cloud Architect",
    "Google Professional Data Engineer",
    "Google Professional Cloud DevOps Engineer",
    "Google Professional Cloud Security Engineer",
    "Azure Fundamentals (AZ-900)",
    "Azure Administrator (AZ-104)",
    "Azure Solutions Architect Expert (AZ-305)",
    "Azure DevOps Engineer Expert (AZ-400)",
    "Databricks Certified Associate Developer",
    "Databricks Certified Data Engineer Associate",
    "dbt Analytics Engineering Certification",
    "Confluent Certified Developer for Apache Kafka",
    "Linux Foundation Certified System Administrator (LFCS)",
    "Certified Information Systems Security Professional (CISSP)",
    "CompTIA Security+",
    "CompTIA Cloud+",
    "(ISC)2 Certified in Cybersecurity (CC)",
    "GIAC Security Essentials (GSEC)",
    "Professional Scrum Master I (PSM I)",
    "PMI Agile Certified Practitioner (PMI-ACP)",
]

LANGUAGES = [
    ("English", "Fluent"),
    ("English", "Native"),
    ("French", "Native"),
    ("French", "Fluent"),
    ("French", "Professional"),
    ("Spanish", "Professional"),
    ("Spanish", "Native"),
    ("Spanish", "Fluent"),
    ("German", "Intermediate"),
    ("German", "Professional"),
    ("German", "Native"),
    ("Italian", "Intermediate"),
    ("Italian", "Professional"),
    ("Portuguese", "Native"),
    ("Portuguese", "Professional"),
    ("Dutch", "Intermediate"),
    ("Dutch", "Professional"),
    ("Swedish", "Intermediate"),
    ("Norwegian", "Intermediate"),
    ("Polish", "Native"),
    ("Czech", "Intermediate"),
    ("Russian", "Professional"),
    ("Russian", "Native"),
    ("Mandarin", "Intermediate"),
    ("Mandarin", "Professional"),
    ("Japanese", "Intermediate"),
    ("Korean", "Intermediate"),
    ("Arabic", "Professional"),
    ("Hindi", "Native"),
    ("Hindi", "Professional"),
]

BULLET_LIBRARY = [
    "Designed and shipped {thing}, improving {metric} by {pct}%.",
    "Reduced {metric} latency from {from_}ms to {to}ms via profiling and caching.",
    "Led migration from {old} to {new}, cutting monthly infra cost by {pct}%.",
    "Built {thing} with {tech}, enabling {outcome}.",
    "Introduced {practice} across the team; increased release frequency by {pct}%.",
    "Partnered with product and security to deliver {thing} without regressions.",
    "Implemented SLOs and dashboards; decreased incident volume by {pct}%.",
    "Refactored {thing} to use {tech}; reduced {metric} by {pct}% with no downtime.",
    "Authored internal RFC for {thing}; drove adoption across {pct} engineering teams.",
    "Mentored {pct} junior engineers through {practice}; two were promoted within the year.",
    "Established {practice}; onboarding time for new engineers dropped by {pct}%.",
    "Delivered {thing} ahead of schedule; directly contributed to {outcome}.",
    "Collaborated with {pct} cross-functional squads to align on {practice}.",
    "Automated {thing} using {tech}; eliminated {pct}% of manual toil.",
    "Optimised {thing} query plans; {metric} improved from {from_}ms to {to}ms.",
    "Ran chaos experiments on {thing}; uncovered and fixed {pct} critical failure modes.",
    "Rolled out {practice} org-wide; decreased post-deploy incidents by {pct}%.",
    "Designed {thing} with {tech}; system now handles {from_} req/s at p99 below {to}ms.",
    "Coordinated with security team to threat-model {thing}; zero high-severity findings at audit.",
    "Shipped {thing} as open-source; gained {pct}+ GitHub stars within 3 months.",
]

THINGS = [
    "a multi-tenant API gateway", "a Kafka-based event bus", "an internal developer portal",
    "a payment risk rules engine", "a data lineage service", "a CI/CD pipeline",
    "an authorization service", "a realtime aggregation service", "a search indexing pipeline",
    "a UI component library", "a design system", "a GraphQL BFF layer",
    "a zero-downtime schema migration tool", "a distributed rate limiter",
    "a secrets rotation service", "a canary deployment controller",
    "a multi-region active-active database layer", "a self-healing job scheduler",
    "a service mesh observability layer", "an AI-assisted on-call bot",
    "a feature store for ML models", "an LLM prompt management API",
    "a unified audit trail service", "a cost attribution dashboard",
    "a developer CLI toolkit", "a contract testing harness",
    "a mobile offline-sync engine", "a browser extension for internal tooling",
    "a cross-platform design token pipeline", "a chaos engineering framework",
    # Additional things
    "a distributed config management service", "an event-sourced order management system",
    "a multi-cloud cost governance dashboard", "a zero-trust network access layer",
    "a self-service ML training pipeline", "a Kubernetes admission controller",
    "a gRPC transcoding proxy", "an async job processing platform",
    "a vector similarity search API", "a model serving platform",
    "a synthetic data generation tool", "a privacy-preserving analytics pipeline",
    "a GraphQL federation gateway", "a streaming ETL framework",
    "a no-code workflow automation engine", "a SaaS usage metering service",
    "a tenant isolation framework", "a database proxy with connection pooling",
    "a WASM-based plugin system", "a distributed tracing SDK",
    "an internal platform CLI", "a feature experiment framework",
    "a SLO alerting engine", "a service dependency mapper",
    "a dark-launch traffic splitting layer", "a multi-tenant secrets vault",
    "an API mocking and contract registry", "a cross-region data replication service",
    "a reactive state management library", "an infrastructure drift detection tool",
]

METRICS = [
    "p95", "p99", "p50", "error rate", "build time", "time-to-recovery",
    "CPU usage", "query time", "bundle size", "cold start time",
    "deployment frequency", "mean time to detect (MTTD)",
    "mean time to resolve (MTTR)", "lead time for changes",
    "change failure rate", "memory footprint", "network egress cost",
    "cache hit ratio", "throughput", "availability (uptime)",
    "API error rate", "database connection pool saturation",
]

PRACTICES = [
    "code review standards", "trunk-based development", "on-call playbooks",
    "service ownership", "feature flags",
    "blameless post-mortems", "architecture decision records",
    "contract testing", "chaos engineering", "game days",
    "pair programming", "mob programming", "event storming",
    "API-first design", "infrastructure as code",
    "progressive delivery", "blue-green deployments",
    "zero-trust security", "threat modelling", "DORA metrics tracking",
    "dependency review", "shift-left security scanning",
    # Additional practices
    "canary releases", "dark launches", "spike-and-stabilize cycles",
    "internal open-source contribution model", "golden path templates",
    "service level objectives (SLOs)", "error budget management",
    "on-call rotations with SLA tracking", "runbook-driven incident response",
    "automated regression testing", "property-based testing",
    "mutation testing", "load and stress testing",
    "capacity reviews", "cost efficiency reviews",
    "engineering effectiveness metrics", "developer satisfaction surveys",
    "technical debt sprints", "engineering guilds",
    "tech radar maintenance", "domain-driven design workshops",
    "internal tech talks and knowledge sharing", "RFC-driven decision making",
    "security champions programme", "bug bounty programme",
    "SOC 2 compliance automation", "GDPR-by-design",
    "privacy impact assessments", "supply chain security reviews",
    "weekly SRE reviews", "monthly reliability retrospectives",
    "quarterly architecture reviews", "continuous profiling",
    "distributed system walkthroughs", "disaster recovery drills",
]

TECHS = [
    # Orchestration & infra
    "Kubernetes", "Terraform", "Helm", "Docker", "Pulumi", "Ansible",
    "ArgoCD", "Flux", "Crossplane", "OpenTofu",
    # Service mesh & networking
    "Istio", "Linkerd", "Envoy", "Cilium", "Consul",
    # Observability
    "OpenTelemetry", "Prometheus", "Grafana", "Datadog", "New Relic",
    "Jaeger", "Zipkin", "Loki", "Tempo", "Splunk",
    "Dynatrace", "Honeycomb", "Lightstep",
    # Databases - relational
    "PostgreSQL", "MySQL", "SQLite", "CockroachDB", "PlanetScale",
    # Databases - NoSQL / document
    "MongoDB", "Cassandra", "DynamoDB", "Couchbase", "FaunaDB",
    # Databases - columnar / analytics
    "ClickHouse", "BigQuery", "Snowflake", "Redshift", "DuckDB",
    "Druid", "Pinot",
    # Cache / in-memory
    "Redis", "Memcached", "Valkey", "Hazelcast",
    # Search
    "Elasticsearch", "OpenSearch", "Meilisearch", "Typesense",
    # Streaming & messaging
    "Kafka", "RabbitMQ", "NATS", "Pulsar", "AWS SQS", "AWS SNS",
    "Google Pub/Sub", "Azure Service Bus", "Kinesis", "EventBridge",
    # ETL / data pipeline
    "Airflow", "dbt", "Spark", "Flink", "Debezium", "Airbyte",
    "Fivetran", "Stitch", "Dagster", "Prefect", "Mage",
    # Data lakehouse
    "Iceberg", "Delta Lake", "Hudi", "Hive Metastore",
    # ML / AI
    "PyTorch", "TensorFlow", "scikit-learn", "Hugging Face", "LangChain",
    "LlamaIndex", "Ray", "MLflow", "Kubeflow", "BentoML",
    "Triton Inference Server", "ONNX", "vLLM",
    # Vector databases
    "Pinecone", "Weaviate", "Qdrant", "Chroma", "pgvector", "Milvus",
    # Backend frameworks
    "FastAPI", "Django", "Flask", "Spring Boot", "Gin", "Echo",
    "Fiber", "Actix", "Axum", "NestJS", "Express.js", "Hono",
    "Ktor", "Micronaut", "Quarkus", "gRPC", "Temporal", "Celery",
    # Frontend frameworks
    "React", "Next.js", "Vue.js", "Nuxt.js", "Angular", "Svelte",
    "SvelteKit", "Remix", "Astro", "Solid.js", "Qwik",
    # Mobile
    "React Native", "Flutter", "Swift", "Kotlin (Android)", "Expo",
    # Languages (as tech items)
    "TypeScript", "Go", "Rust", "Python", "Java", "Kotlin",
    "Elixir", "Scala", "C++", "Ruby",
    # CI/CD
    "GitHub Actions", "GitLab CI", "CircleCI", "Jenkins", "Buildkite",
    "Tekton", "Argo Workflows", "Drone CI",
    # Security
    "Vault", "Falco", "OPA (Open Policy Agent)", "Trivy", "Snyk",
    "Cosign", "SPIRE", "cert-manager",
    # Cloud-native serverless / PaaS
    "AWS Lambda", "GCP Cloud Run", "Azure Functions", "Cloudflare Workers",
    "Vercel", "Fly.io", "Railway", "Render",
    # API / gateway
    "Kong", "Traefik", "NGINX", "Envoy Gateway", "AWS API Gateway",
    "Apigee", "Tyk",
    # Feature flags / experimentation
    "LaunchDarkly", "Unleash", "Flagsmith", "Growthbook",
    # Other tooling
    "GraphQL", "tRPC", "WebSockets", "Server-Sent Events",
    "Protocol Buffers", "Avro", "Parquet",
]

OUTCOMES = [
    "self-serve onboarding for new teams",
    "safer deploys with progressive delivery",
    "near real-time reporting for stakeholders",
    "better auditability and compliance",
    "faster incident triage",
    "faster UI iteration with reusable components",
    "a 3x reduction in infrastructure spend",
    "zero-downtime database migrations at scale",
    "sub-100ms p99 latency for all critical paths",
    "full traceability across distributed services",
    "automated compliance evidence collection",
    "a developer experience score improvement of 40 points",
    "a 50% reduction in on-call pages",
    "multi-region failover with RTO under 30 seconds",
    "self-service environment provisioning in under 5 minutes",
    "end-to-end encryption for all data in transit and at rest",
    "a shared platform layer adopted by 8 engineering teams",
    # Additional outcomes
    "10x throughput improvement with zero additional hardware",
    "a fully automated release process with no manual gates",
    "a unified observability stack across all microservices",
    "a 70% reduction in time-to-first-deploy for new engineers",
    "first-class mobile support with offline-first capabilities",
    "real-time fraud signals processed at under 5ms latency",
    "a vendor-agnostic infrastructure layer portable across clouds",
    "a completely serverless data processing layer saving 40% monthly",
    "an internal platform that eliminated dependency on external consultants",
    "zero-regression rollouts thanks to contract testing coverage",
    "a design system adopted by all product squads within one quarter",
    "automated SOC 2 evidence collection cutting audit prep from weeks to days",
    "a data mesh architecture enabling domain-driven data ownership",
    "sub-second search results across 50M records",
    "a platform SLA of 99.99% sustained over 12 consecutive months",
    "LLM-powered features shipped to production with guardrails in place",
    "a cost attribution model revealing 35% of spend was untagged waste",
    "a shift-left security approach resulting in zero critical CVEs in prod",
    "continuous deployment to 15 environments with full rollback capability",
    "a developer portal that consolidated 12 internal wikis into one source of truth",
    "ML model serving at scale with under 20ms inference latency",
    "a multi-cloud active-active architecture with automated failover",
    "GDPR compliance achieved across all user data flows",
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
    "mobile": {
        "titles": ["Mobile Engineer", "iOS Engineer", "Android Engineer", "Full Stack Engineer"],
        "focus": ["mobile performance", "product-minded engineering", "API design"],
        "bias": {
            "Languages": ["Swift", "Kotlin", "TypeScript", "Dart"],
            "Frameworks": ["React Native", "Flutter", "Next.js"],
            "Cloud": ["AWS", "Firebase", "Docker"],
            "Practices": ["TDD", "Observability", "Progressive Delivery"],
        },
    },
    "platform": {
        "titles": ["Platform Engineer", "Staff Software Engineer", "Infrastructure Engineer", "Developer Experience Engineer"],
        "focus": ["developer experience", "infrastructure as code", "platform reliability", "CI/CD automation"],
        "bias": {
            "Cloud": ["Kubernetes", "Terraform", "AWS", "GCP", "ArgoCD", "Helm", "Pulumi"],
            "Languages": ["Go", "Python", "Bash", "TypeScript"],
            "Practices": ["GitOps", "DORA Metrics", "SRE", "Chaos Engineering"],
            "Data": ["PostgreSQL", "Redis"],
        },
    },
    "analytics": {
        "titles": ["Analytics Engineer", "Data Engineer", "Software Engineer", "Business Intelligence Engineer"],
        "focus": ["data pipelines", "data governance", "cost optimisation", "real-time processing"],
        "bias": {
            "Languages": ["SQL", "Python", "dbt"],
            "Data": ["dbt", "BigQuery", "Snowflake", "Redshift", "Airflow", "Databricks", "ClickHouse"],
            "Cloud": ["GCP", "AWS", "Terraform"],
            "Practices": ["DDD", "Observability", "DORA Metrics"],
        },
    },
    "ai": {
        "titles": ["AI/ML Engineer", "Machine Learning Engineer", "Research Engineer", "NLP Engineer"],
        "focus": ["MLOps", "data pipelines", "developer experience", "performance tuning"],
        "bias": {
            "Languages": ["Python", "Rust", "C++"],
            "Frameworks": ["PyTorch", "FastAPI", "gRPC", "LangChain"],
            "Data": ["Pinecone", "Weaviate", "Qdrant", "pgvector", "Kafka", "BigQuery"],
            "Cloud": ["AWS", "GCP", "Kubernetes", "Docker"],
            "Practices": ["Observability", "Contract Testing", "Feature Flags"],
        },
    },
    "dx": {
        "titles": ["Developer Experience Engineer", "Platform Engineer", "Staff Software Engineer", "Software Engineer in Test"],
        "focus": ["developer experience", "CI/CD automation", "infrastructure as code", "shift-left testing"],
        "bias": {
            "Languages": ["TypeScript", "Go", "Python", "Bash"],
            "Frameworks": ["Node.js", "NestJS", "React"],
            "Cloud": ["GitHub Actions", "Kubernetes", "Docker", "Terraform"],
            "Practices": ["Trunk-Based Development", "Contract Testing", "DORA Metrics", "Observability"],
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
