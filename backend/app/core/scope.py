"""Product scope shared by API validation, retrieval, and local ingestion."""
import re
from typing import Annotated, Literal

from pydantic import BeforeValidator

SUPPORTED_LANGUAGES = ("C", "C++", "Java", "Python")
LANGUAGE_FILTERS = ("All", *SUPPORTED_LANGUAGES)
SCOPE_MESSAGE = "TechQuery supports programming help for C, C++, Java, and Python. Please ask about one of these languages."


def normalize_language(value, *, allow_all=True):
    if not isinstance(value, str):
        raise ValueError(SCOPE_MESSAGE)
    aliases = {name.casefold(): name for name in LANGUAGE_FILTERS}
    aliases.update({"cpp": "C++", "cplusplus": "C++", "c plus plus": "C++"})
    result = aliases.get(value.strip().casefold())
    if result is None or (result == "All" and not allow_all):
        raise ValueError("Choose C, C++, Java, or Python for this PDF." if not allow_all else SCOPE_MESSAGE)
    return result


def legacy_language_filter(value):
    """Read old preferences/conversations without rewriting stored history."""
    try:
        return normalize_language(value)
    except ValueError:
        return "All"


ProgrammingLanguage = Annotated[
    Literal["C", "C++", "Java", "Python"],
    BeforeValidator(lambda value: normalize_language(value, allow_all=False)),
]
LanguageFilter = Annotated[
    Literal["All", "C", "C++", "Java", "Python"], BeforeValidator(normalize_language),
]


def normalize_subject(value):
    if not isinstance(value, str):
        raise ValueError('Enter a subject name.')
    name = ' '.join(value.split())
    if not name or len(name) > 100 or any(ord(char) < 32 for char in value):
        raise ValueError('Subject names must contain 1 to 100 characters without control characters.')
    try:
        return normalize_language(name)
    except ValueError:
        return name


SubjectName = Annotated[str, BeforeValidator(normalize_subject)]


def question_language(question):
    """A single explicit language can narrow the default All search.

    Ignore fenced code and avoid treating a standalone variable named C as a
    language. Comparisons naming multiple languages keep the All scope.
    """
    prose = re.sub(r'```[\s\S]*?```', '', question).casefold()
    patterns = {
        'C++': r'(?<![\w])(?:c\+\+|cpp|cplusplus|c plus plus)(?![\w+#])',
        'C': r'\b(?:in|using|for|with)\s+c(?![\w+#])|\bc\s+(?:programming|language)\b',
        'Java': r'\bjava\b',
        'Python': r'\bpython\b',
    }
    matches = [name for name, pattern in patterns.items() if re.search(pattern, prose)]
    return matches[0] if len(matches) == 1 else None


def question_outside_scope(question):
    """Catch explicit unsupported requests locally, including during provider outages.

    This is a conservative guard, not a general-purpose topic classifier. Generic
    programming questions remain eligible for retrieval from the four-language
    corpus. The generation instruction independently checks relevance to scope.
    """
    # Ignore code blocks: string literals and comments can mention other languages.
    prose = re.sub(r"```[\s\S]*?```", "", question).casefold()
    unsupported = r"(?<![\w])(?:javascript|typescript|c\#|csharp|c sharp|objective-c|swift|kotlin|ruby|php|rust|dart|perl|lua|scala|haskell|elixir|golang)(?![\w])"
    if re.search(unsupported, prose):
        return True
    if re.search(r"\b(?:in|using|learn|teach|explain)\s+(?:go|r)\b|\b(?:go|r)\s+(?:programming|language|code)\b", prose):
        return True
    supported = re.search(r"(?<![\w])(?:c\+\+|c|java|python)(?![\w+#])", prose)
    # Related APIs/concepts are allowed when tied to a supported language, e.g.
    # Python's sqlite3 or Java JDBC. They are not separate subject offerings.
    standalone = r"\b(?:sql|dbms|database normalization|acid properties|operating systems?|cpu scheduling|cloud computing|computer networks?)\b"
    return bool(not supported and re.search(standalone, prose))
