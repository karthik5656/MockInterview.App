import re
from typing import List, Set

# Common English stop words to exclude from keyword extraction
STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't",
    "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself",
    "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is",
    "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
    "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should",
    "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we",
    "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where",
    "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves",
    "experience", "years", "work", "worked", "team", "responsibilities", "skills", "knowledge", "role",
    "candidate", "job", "description", "requirements", "including", "using", "used", "strong", "good",
    "excellent", "ability", "proficient", "familiar", "hands-on", "understanding", "looking", "needed",
    "experienced", "senior", "junior", "lead", "staff", "principal", "engineer", "developer", "backend",
    "frontend", "fullstack", "position", "company", "project", "projects", "responsible", "building"
}

# Regex pattern for acronyms, capitalized technical terms, compound tech terms (e.g. CI/CD, CQRS, PostgreSQL, Node.js)
TECH_PATTERN = re.compile(
    r"\b(?:[A-Z]{2,}(?:/[A-Z]{2,})?|[A-Z][a-z]+(?:[A-Z][a-z]+)+|[A-Za-z0-9]+(?:\.[a-z]{2,})|C\+\+|C#|\.NET|[A-Z][a-zA-Z0-9_\-]+)\b"
)


class KeywordExtractor:
    """Utility to extract prominent technical keywords and jargon from Resume and Job Description."""

    @staticmethod
    def extract_keywords(resume_text: str, jd_text: str, max_keywords: int = 30) -> str:
        """Extracts unique high-priority technical terms and returns a comma-separated string."""
        combined_text = f"{jd_text}\n{resume_text}"
        if not combined_text.strip():
            return ""

        # Find pattern matches
        matches: List[str] = TECH_PATTERN.findall(combined_text)

        frequencies = {}
        for match in matches:
            clean = match.strip(".,;:()[]{}<>\"'")
            if len(clean) < 2 or clean.lower() in STOP_WORDS:
                continue
            # Preserve original casing, track frequency
            frequencies[clean] = frequencies.get(clean, 0) + 1

        # Also search for specific well-known tech keywords in lowercase/mixed text
        well_known_terms = [
            "Kubernetes", "Docker", "Kafka", "PostgreSQL", "MySQL", "MongoDB", "Redis",
            "RabbitMQ", "Prometheus", "Grafana", "Istio", "gRPC", "GraphQL", "REST",
            "Terraform", "Ansible", "AWS", "Azure", "GCP", "CI/CD", "CQRS", "idempotency",
            "microservices", "OAuth", "JWT", "WebSocket", "Celery", "Elasticsearch",
            "DynamoDB", "FastAPI", "Django", "Flask", "React", "Next.js", "Node.js", "TypeScript"
        ]
        for term in well_known_terms:
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            count = len(pattern.findall(combined_text))
            if count > 0 and term not in frequencies:
                frequencies[term] = count

        if not frequencies:
            return ""

        # Sort by frequency descending, then length descending
        sorted_terms = sorted(frequencies.keys(), key=lambda t: (frequencies[t], len(t)), reverse=True)
        top_terms = sorted_terms[:max_keywords]

        return ", ".join(top_terms)


keyword_extractor = KeywordExtractor()
