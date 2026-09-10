"""
aggregator/skills.py - Skill extraction from job descriptions.

Keyword-based skill taxonomy. Extracts technology skills, tools, and
frameworks from job description text using word-boundary regex matching.
"""

import re

# Skill taxonomy: { canonical_name: [patterns] }
# Patterns are matched case-insensitively with word boundaries.
# Order doesn't matter - all matches are collected.
SKILL_TAXONOMY: dict[str, list[str]] = {
    # Programming languages
    "python":       ["python"],
    "javascript":   ["javascript", "js"],
    "typescript":   ["typescript", "ts"],
    "java":         ["java"],
    "c#":           [r"c\#", r"c\s*sharp", r"csharp"],
    "c++":          [r"c\+\+", "cpp"],
    "go":           [r"\bgo\b", "golang"],
    "rust":         ["rust"],
    "ruby":         ["ruby"],
    "php":          ["php"],
    "swift":        ["swift"],
    "kotlin":       ["kotlin"],
    "scala":        ["scala"],
    "r":            [r"\br\b"],
    "sql":          ["sql"],
    "bash":         ["bash", "shell scripting"],

    # Frontend frameworks
    "react":        ["react", "reactjs", "react.js"],
    "angular":      ["angular", "angularjs"],
    "vue":          ["vue", "vuejs", "vue.js"],
    "next.js":      ["next.js", "nextjs"],
    "svelte":       ["svelte"],
    "html":         ["html"],
    "css":          ["css"],
    "tailwind":     ["tailwind", "tailwindcss"],
    "sass":         ["sass", "scss"],

    # Backend frameworks
    "node.js":      ["node.js", "nodejs", "node"],
    "django":       ["django"],
    "flask":        ["flask"],
    "fastapi":      ["fastapi"],
    "spring":       ["spring", "spring boot", "springboot"],
    "express":      ["express", "expressjs"],
    ".net":         [r"\.net", "dotnet"],
    "rails":        ["rails", "ruby on rails"],
    "laravel":      ["laravel"],

    # Databases
    "postgresql":   ["postgresql", "postgres"],
    "mysql":        ["mysql"],
    "mongodb":      ["mongodb", "mongo"],
    "redis":        ["redis"],
    "elasticsearch": ["elasticsearch", "elastic search"],
    "sqlite":       ["sqlite"],
    "oracle":       ["oracle db", "oracle database"],
    "sql server":   ["sql server", "mssql"],
    "dynamodb":     ["dynamodb"],
    "cassandra":    ["cassandra"],

    # Cloud & DevOps
    "aws":          ["aws", "amazon web services"],
    "azure":        ["azure", "microsoft azure"],
    "gcp":          ["gcp", "google cloud"],
    "docker":       ["docker"],
    "kubernetes":   ["kubernetes", "k8s"],
    "terraform":    ["terraform"],
    "ansible":      ["ansible"],
    "jenkins":      ["jenkins"],
    "ci/cd":        [r"ci/cd", r"ci\/cd", "continuous integration", "continuous deployment"],
    "github actions": ["github actions"],
    "gitlab ci":    ["gitlab ci", "gitlab-ci"],
    "linux":        ["linux"],
    "nginx":        ["nginx"],
    "apache":       ["apache"],

    # Data & ML
    "machine learning":  ["machine learning", "ml"],
    "deep learning":     ["deep learning", "dl"],
    "tensorflow":   ["tensorflow"],
    "pytorch":      ["pytorch"],
    "pandas":       ["pandas"],
    "numpy":        ["numpy"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "spark":        ["spark", "apache spark", "pyspark"],
    "airflow":      ["airflow", "apache airflow"],
    "kafka":        ["kafka", "apache kafka"],
    "data engineering":  ["data engineering"],
    "etl":          ["etl"],
    "power bi":     ["power bi", "powerbi"],
    "tableau":      ["tableau"],

    # Tools & practices
    "git":          ["git"],
    "jira":         ["jira"],
    "confluence":   ["confluence"],
    "agile":        ["agile", "scrum"],
    "rest api":     ["rest api", "restful"],
    "graphql":      ["graphql"],
    "microservices": ["microservices", "micro-services"],
    "rabbitmq":     ["rabbitmq"],
    "grpc":         ["grpc"],

    # Security
    "cybersecurity": ["cybersecurity", "cyber security", "infosec"],
    "oauth":        ["oauth"],
    "sso":          ["sso", "single sign-on"],

    # Mobile
    "android":      ["android"],
    "ios":          ["ios"],
    "react native": ["react native"],
    "flutter":      ["flutter"],

    # SAP / Enterprise (common in German job market)
    "sap":          ["sap"],
    "salesforce":   ["salesforce"],
    "erp":          ["erp"],
}

# Pre-compiled patterns: list of (canonical_name, compiled_regex)
_COMPILED_PATTERNS: list[tuple[str, re.Pattern]] = []


def _compile_patterns() -> None:
    """Compile all skill patterns once on first use."""
    if _COMPILED_PATTERNS:
        return
    for skill, patterns in SKILL_TAXONOMY.items():
        combined = "|".join(rf"\b{p}\b" for p in patterns)
        _COMPILED_PATTERNS.append((skill, re.compile(combined, re.IGNORECASE)))


def extract_skills(text: str) -> list[str]:
    """Extract skill names from text. Returns deduplicated list of canonical skill names."""
    if not text:
        return []
    _compile_patterns()
    found = []
    for skill, pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            found.append(skill)
    return found
