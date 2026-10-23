"""Local lexical ranking; never changes saved text or embedding provenance."""
from collections import Counter
from dataclasses import dataclass
import math
import re
import unicodedata

STOP_WORDS = set('a an the is are was were be been being do does did can could should would will of to on for and or it its as at by from with how what why when where which who explain describe give tell please about some also using use used example simple book textbook'.split())
QUERY_FILLER = set('work works working difference differences between versus vs compare compared happen happens dynamically called behave behavior behaviour this that these those me my mine your yours our ours us just still too'.split())
# Deliberately bounded English concept inflections. Do not stem identifiers such
# as equals, contains, getBytes, is_default, class or address by stripping "s".
INFLECTIONS = dict(pair.split(':') for pair in (
    'constructors:constructor destructors:destructor classes:class objects:object '
    'methods:method functions:function parameters:parameter arguments:argument '
    'resources:resource exceptions:exception pointers:pointer arrays:array '
    'lists:list tuples:tuple strings:string interfaces:interface values:value '
    'references:reference threads:thread variables:variable allocations:allocation '
    'elements:element keys:key dictionaries:dictionary files:file types:type '
    'members:member calls:call indices:index indexes:index indexing:index '
    'boundaries:bound boundary:bound bounds:bound outside:out dict:dictionary checks:check '
    'change:modify changes:modify changed:modify changing:modify modifies:modify modified:modify modifying:modify'
).split())

# Search vocabulary, not answer templates. These related actions help a broad
# lifecycle question find an explanatory application as well as signatures.
CONCEPT_ACTIONS = {
    'constructor': set('initialize initializes initialization initialised initializing allocate allocated allocates acquire acquired acquires lock locks'.split()),
    'destructor': set('deallocate deallocated deallocates release released releases cleanup unlock unlocks delete'.split()),
}


def terms(text):
    normalized = unicodedata.normalize('NFKC', text).casefold()
    return [INFLECTIONS.get(word, word) for word in re.findall(r'[a-z0-9_+#]+', normalized)
        if word not in STOP_WORDS and len(word) > 1]


def query_terms(query, subject='All'):
    # Remove a containment connective, not the concepts it connects. The
    # original question is retained unchanged for grounded generation.
    focused = re.sub(r'\b(?:stored|contained|held)\s+(?:inside|within|in)\b', 'in', query, flags=re.I)
    focused = re.sub(r'^\s*if\s+(?=(?:a|an|the|i|we|you|my|our)\b)', '', focused, flags=re.I)
    # For yes/no requirement questions both "required" and "optional" prose
    # can answer the question. Keep the named concepts, not one polarity.
    focused = re.sub(r'^\s*(?:are|is)\s+(.+?)\s+(?:required|necessary|optional)\b', r'\1', focused, flags=re.I)
    words = set(terms(focused)) - QUERY_FILLER
    # Conversational "this reference" is filler; the named this keyword/pointer
    # and explicitly quoted identifiers still carry programming meaning.
    quoted = set(terms(' '.join(re.findall(r"[`\"']([^`\"']+)[`\"']", query))))
    words |= quoted & QUERY_FILLER
    if re.search(r'\bthis\s+(?:keyword|pointer)\b|\bkeyword\s+this\b|\bthis\s+(?:in\s+(?:java|c\+\+))?[?.]?\s*$', query, re.I):
        words.add('this')
    if not re.search(r'\bin\s+operator\b|\boperator\s+[`\'"]?in\b|[`\'"]in[`\'"]', query, re.I):
        words.discard('in')
    else:
        # The named keyword is the concept; generic "operator" would favor
        # unrelated operator-module prose over examples using that keyword.
        words.discard('operator')
    # The SQL scope already enforces the selected subject. Its name is not an
    # extra concept every supporting paragraph needs to repeat.
    if subject and subject != 'All':
        words -= set(terms(subject))
        if subject == 'C++':
            words -= {'cpp', 'cplusplus'}
    return words


def coordinated_terms(query, words):
    facets = []
    for left, right in re.findall(r'([\w+#]+)\s+(?:and|versus|vs\.?|or)\s+([\w+#]+)', query.casefold()):
        a, b = terms(left), terms(right)
        if a and b and a[0] != b[0] and a[0] in words and b[0] in words:
            facets.extend((a[0], b[0]))
    return list(dict.fromkeys(facets))[:4]


@dataclass
class RankedPassage:
    chunk: object
    title: str
    score: float
    coverage: float
    contributions: dict
    definitions: set

    @property
    def key(self):
        return (self.chunk.document_id, self.chunk.chunk_index)


@dataclass
class KeywordRanking:
    passages: list
    priority_keys: list
    definition_focus: bool = False


def rank_passages(rows, question, subject='All', top_k=5, *, _split_clauses=True):
    words = query_terms(question, subject)
    ordered_words = [word for word in terms(question) if word in words]
    phrases = {tuple(ordered_words[start:start + size]) for size in range(2, 5)
        for start in range(len(ordered_words) - size + 1)}
    documents = [(chunk, title, Counter(terms(chunk.content))) for chunk, title in rows
        if not re.search(r'\.{8,}', chunk.content)]
    if not words or not documents or top_k <= 0:
        return KeywordRanking([], [])
    clause_anchors = []
    if _split_clauses:
        # Two explicit questions can be answered on different pages. Require
        # the normal evidence floor independently; never discard unknown
        # qualifiers from a single question or manufacture support for a part.
        clauses = re.split(r'\band\s+(?=(?:how|why|what|when|can|could|does|do|is|are)\b)|(?<=\?)\s+(?=(?:how|why|what|when|can|could|does|do|is|are)\b)', question, flags=re.I)
        if len(clauses) > 1:
            for clause in clauses[:3]:
                found = rank_passages(rows, clause, subject, top_k=1, _split_clauses=False)
                clause_anchors.extend(found.passages)
    df = {word: sum(word in counts for _, _, counts in documents) for word in words}
    weights = {word: math.log(1 + (len(documents) - df[word] + .5) / (df[word] + .5)) for word in words}
    total_weight = sum(weights.values())
    average_length = sum(sum(counts.values()) for _, _, counts in documents) / len(documents)
    short_concept_question = len(words) <= 3
    candidates = []
    for chunk, title, counts in documents:
        contributions = {word: weights[word] * counts[word] * 2.2 / (
            counts[word] + 1.2 * (.25 + .75 * sum(counts.values()) / max(average_length, 1)))
            for word in words if counts[word]}
        coverage = sum(weights[word] for word in contributions) / total_weight
        text = unicodedata.normalize('NFKC', chunk.content).casefold()
        definitions = {word for word in contributions if re.search(
            r'\b' + re.escape(word) + r'\s+(?:is|means|refers to)\b|\b'
            + re.escape(word) + r's\s+are\b', text)}
        # Only broad concept questions favor definitions. An explicit question
        # about virtual calls must retain its specific qualifiers.
        boost = 1 + .5 * len(definitions) / len(words) if short_concept_question else 1
        # Reward nearby concepts in the question's order. A paragraph about
        # "passed by value" is stronger than scattered matches for those words.
        tokens = terms(chunk.content)
        longest_phrase = max((size for size in range(2, min(4, len(ordered_words)) + 1)
            if any(tuple(tokens[start:start + size]) in phrases
                for start in range(len(tokens) - size + 1))), default=0)
        if longest_phrase:
            boost *= 1 + longest_phrase / len(ordered_words)
        candidates.append(RankedPassage(chunk, title, sum(contributions.values()) * boost,
            coverage, contributions, definitions))
    base = sorted((item for item in candidates if item.coverage >= .5), key=lambda item: item.score, reverse=True)
    if base and not short_concept_question:
        first = base[0]
        # Book explanations may continue after a keyword-heavy heading/example.
        # Retain the normal coverage floor and a bounded, forward-only window.
        for item in base[1:]:
            if item.chunk.document_id == first.chunk.document_id and 0 < item.chunk.chunk_index - first.chunk.chunk_index <= 2:
                item.score *= 1.5
        base = base[:1] + sorted(base[1:], key=lambda item: item.score, reverse=True)
    facets = coordinated_terms(question, words)
    anchors = []
    # Separate concept queries let "X and Y" retrieve a direct explanation of
    # each, even when X alone has <50% of the *combined* inverse-frequency weight.
    # Specific questions already covered by the best passage keep that ranking.
    needs_facets = facets and (short_concept_question or not base or
        not set(facets).issubset(base[0].contributions))
    if needs_facets:
        for facet in facets:
            matching = [item for item in candidates if facet in item.contributions]
            if matching:
                anchors.append(max(matching, key=lambda item: (
                    item.contributions[facet] + .25 * sum(score for word, score in item.contributions.items() if word != facet)
                ) * (1 + .5 * (facet in item.definitions))))
    application = []
    if anchors and all(facet in CONCEPT_ACTIONS for facet in facets):
        actions = set.union(*(CONCEPT_ACTIONS[facet] for facet in facets))
        action_df = {word: sum(word in counts for _, _, counts in documents) for word in actions}
        action_weights = {word: math.log(1 + len(documents) / (1 + freq)) for word, freq in action_df.items()}
        examples = []
        for item in candidates:
            counts = Counter(terms(item.chunk.content))
            if set(facets).issubset(counts) and all(CONCEPT_ACTIONS[facet] & counts.keys() for facet in facets):
                score = sum(action_weights[word] for word in actions & counts.keys()) / math.sqrt(sum(counts.values()))
                examples.append((score, item))
        if examples:
            application = [max(examples, key=lambda pair: pair[0])[1]]
    continuation = []
    if base:
        first = base[0]
        adjacent = [item for item in base[1:] if item.chunk.document_id == first.chunk.document_id
            and 0 < item.chunk.chunk_index - first.chunk.chunk_index <= 2]
        if adjacent:
            continuation = [max(adjacent, key=lambda item: (
                item.chunk.page_number > first.chunk.page_number, item.chunk.chunk_index))]
    priority = anchors + continuation if short_concept_question and anchors else base[:1] + application + anchors + continuation
    priority = clause_anchors + priority
    definition_focus = bool(facets and words == set(facets) and all(
        any(facet in item.definitions for item in anchors) for facet in facets))
    single_definition = bool(subject != 'All' and not facets and short_concept_question and base and base[0].definitions
        and re.match(r'\s*(?:what\s+(?:is|are)\s+(?:a|an|the)\b|define\b)', question, re.I))
    # When the entire question asks for two basic concepts and we found direct
    # definitions of both, do not pad context with keyword-heavy special cases.
    if single_definition:
        definition_focus = True
        ordered = base[:1] + continuation
        priority = ordered
    elif definition_focus:
        supporting = [] if application else [item for item in base if item.definitions]
        ordered = anchors + application + supporting
    else:
        ordered = priority + base
    priority_set = {item.key for item in priority}
    selected, deferred, seen, pages = [], [], set(), set()
    for item in ordered:
        page = (item.chunk.document_id, item.chunk.page_number)
        if item.key in seen:
            continue
        seen.add(item.key)
        if page in pages and item.key not in priority_set:
            deferred.append(item)
        else:
            selected.append(item)
            pages.add(page)
    selected = (selected + deferred)[:top_k]
    priorities = [item.key for item in priority if item in selected] if anchors or continuation or clause_anchors else []
    return KeywordRanking(selected, list(dict.fromkeys(priorities))[:4], definition_focus)


def diversify_sources(sources, top_k):
    """Prefer distinct physical pages, then fill remaining slots from that page."""
    distinct, repeated, pages = [], [], set()
    for source in sources:
        page = (source.document_id, source.page_number)
        if page in pages:
            repeated.append(source)
        else:
            distinct.append(source)
            pages.add(page)
    return (distinct + repeated)[:top_k]
