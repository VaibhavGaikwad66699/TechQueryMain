"""Narrow reviewed exclusions; PDFs, saved chunks and citations stay original.

Java PDF p. 77 overstates allocation for case conversion; the same book p. 747
qualifies toUpperCase with possible reuse. OpenJDK 8 String's
toLowerCase/toUpperCase can return this when unchanged:
https://github.com/openjdk/jdk8u/blob/master/jdk/src/share/classes/java/lang/String.java
Exclude the faulty clause rather than attributing outside facts to a book.
Python p. 59's introductory notation/example is scoped similarly; its detailed
tuple section (pp. 185-187) supplies the qualified syntax and examples.
"""
import re

from app.services.embedding_service import read_metadata

JAVA_BOOK_SHA256 = '8751bee1658e8b2a247311eb9179625a4216b62f76d4b21545fb68e495dba706'
ALLOCATION_CLAUSE = re.compile(
    r'These\s+methods\s+both\s+return\s+the\s+converted\s+strings\s+as\s+new\s+String\s+instances\s*:\s*')
SOURCE_CAUTION = (
    'Source note: this book overstates allocation for String case conversion. '
    'Its claim about new instances is excluded from the explanation; the original PDF is unchanged.')
PYTHON_BOOK_SHA256 = 'f5e2868ad977858fa0fa3eb123282f15a06f6eb4dd2b7c3a883e1dd1e138f61f'
TUPLE_CAUTION = (
    'Source note: the introductory tuple notation on this page is simplified. '
    'Its parentheses wording and misleading single-item example are excluded from the explanation; '
    'the original PDF is unchanged.')
TUPLE_CLAUSE = re.compile(r'tuples\s+are\s+enclosed\s+in\s+parentheses\s*\(\s*\)\s+and\s+')
TUPLE_EXAMPLE = re.compile(r"\btuple\s*=\s*\(123,\s*'hello'\)[\s\S]*?(?=GoalKicker\.com|$)")


def reviewed_passage(chunk, document):
    """Return permitted generation evidence and an optional editorial caution.

    Scope by default status, language, fingerprint, page and exact faulty prose;
    an unrelated/private reference with a similar title must never be rewritten.
    """
    if (document.is_default and document.subject == 'Java' and chunk.page_number == 77
            and read_metadata(chunk.metadata_json).get('source_sha256') == JAVA_BOOK_SHA256):
        text, count = ALLOCATION_CLAUSE.subn('', chunk.content)
        if count:
            return text, SOURCE_CAUTION
    if (document.is_default and document.subject == 'Python' and chunk.page_number == 59
            and read_metadata(chunk.metadata_json).get('source_sha256') == PYTHON_BOOK_SHA256):
        text, clauses = TUPLE_CLAUSE.subn('tuples ', chunk.content)
        text, examples = TUPLE_EXAMPLE.subn('', text)
        if clauses or examples:
            return text, TUPLE_CAUTION
    return chunk.content, None


def exclusion_instruction(caution):
    if caution == SOURCE_CAUTION:
        return ('An allocation claim was excluded as a reviewed source error. Use only retained text. '
            'It does not establish whether a new object is allocated. Do not infer identity from immutability; '
            'allocation claims require explicit support in another supplied passage.')
    return ('Simplified parentheses wording and a faulty singleton example were excluded. '
        'Use retained text for mutability, and supplied detailed tuple passages for notation. '
        'Do not infer required parentheses or copy the excluded example.')


def reintroduces_excluded_claim(caution, text):
    if caution == SOURCE_CAUTION:
        return bool(re.search(r'\b(?:new|fresh)\s+(?:String\s+)?(?:objects?|instances?|strings?)\b|\ballocat\w*\b', text, re.I))
    return bool(re.search(r'\btuples?\s+(?:are|must\s+be)\s+(?:always\s+)?(?:enclosed|written|created)\s+(?:in|with)\s+parentheses\b', text, re.I)
        and not re.search(r'\b(?:optional|often|commonly|usually|not\s+required)\b', text, re.I))


def tuple_precision_issue(claims):
    """Flag two concrete overgeneralizations, not arbitrary semantic errors."""
    if not any(re.search(r'\btuples?\b', claim.text, re.I) for claim in claims):
        return None
    for claim in claims:
        if re.search(r'\bcomma\s+alone\b|\bjust\s+a\s+comma\b', claim.text, re.I):
            return ('Do not say comma alone or just a comma. Describe the value(s) with their comma(s), '
                'using the actual supplied example. For a singleton say a value followed by a comma.')
        if re.search(r'\bparentheses\s+(?:are\s+)?not\s+required\s+to\s+(?:construct|create)\s+(?:a\s+)?(?:Python\s+)?tuple\b', claim.text, re.I):
            return ('Do not generalize optional grouping to every tuple form. If the evidence demonstrates '
                'a single-item tuple, say specifically that parentheses around that value are optional '
                'and a comma follows the value. Do not add an empty-tuple rule unless supported by evidence.')
    return None
