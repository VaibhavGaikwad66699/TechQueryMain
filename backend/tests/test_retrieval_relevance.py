import json
import pytest
from types import SimpleNamespace
from unittest.mock import Mock

from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import embedding_service
from app.services.rag_service import rag_service
from app.services.retrieval_ranking import terms, query_terms, rank_passages
from app.core.scope import question_language


def test_explicit_language_detection_ignores_code_variables_and_preserves_comparisons():
    assert question_language('How do constructors work in C++?') == 'C++'
    assert question_language('Explain malloc in C.') == 'C'
    assert question_language('Compare Java and Python lists.') is None
    assert question_language('What is the variable C? ```python\nC = 2\n```') is None


def rows(*texts):
    return [(SimpleNamespace(document_id=1, chunk_index=index, page_number=index + 1, content=text), 'Reference')
        for index, text in enumerate(texts)]


def test_inflections_and_pdf_ligatures_preserve_identifiers_and_distinct_terms():
    found = terms('Constructors destructors classes lists deﬁned equals contains getBytes is_default class address')
    assert found == ['constructor', 'destructor', 'class', 'list', 'defined', 'equals', 'contains', 'getbytes', 'is_default', 'class', 'address']


def test_in_operator_is_searchable_but_language_preposition_is_not_a_concept():
    assert 'in' in query_terms('Does the in operator check dictionary keys or values in Python?', 'Python')
    assert 'in' not in query_terms('How do constructors and destructors work in C++?', 'C++')
    suggestions = rag_service.suggested_questions('How do constructors and destructors work in C++?')
    assert suggestions[0].endswith('with a simple example in C++?')
    assert 'work in with' not in suggestions[0]


def test_basic_compound_question_prefers_both_definitions_to_keyword_heavy_edge_case():
    corpus = rows(
        'Virtual calls in constructors and destructors have unusual dispatch behavior. Constructors and destructors both call virtual functions.',
        'A constructor is a member function that initializes an object. Constructor initialization sets member values.',
        'A destructor is a member function called when an object is destroyed. It releases owned resources.',
    )
    ranked = rank_passages(corpus, 'How do constructors and destructors work in C++?', 'C++')
    assert [item.chunk.chunk_index for item in ranked.passages[:2]] == [1, 2]
    assert set(ranked.priority_keys) == {(1, 1), (1, 2)}


def test_broad_lifecycle_context_includes_explanatory_application_without_virtual_edge_cases():
    corpus = rows(
        'The behavior of virtual functions in constructors and destructors is confusing. '
        'Calling a virtual method from a constructor (or destructor) is dangerous.',
        'A constructor is a member function that initializes an object.',
        'A destructor is a member function called when an object is destroyed.',
        'The constructor acquires a lock. The destructor releases the lock at scope exit.',
    )
    ranked = rank_passages(corpus, 'How do constructors and destructors work in C++?', 'C++')
    assert {item.chunk.chunk_index for item in ranked.passages} == {1, 2, 3}


def test_explicit_virtual_dispatch_question_retains_its_qualifiers():
    corpus = rows(
        'Virtual function calls in constructors and destructors invoke the base implementation during base construction.',
        'A constructor is a member function that initializes an object.',
        'A destructor is a member function called when an object is destroyed.',
    )
    ranked = rank_passages(corpus, 'How do virtual function calls behave in constructors and destructors?', 'C++')
    assert ranked.passages[0].chunk.chunk_index == 0


def test_concept_phrase_beats_scattered_matches_for_parameter_passing():
    corpus = rows(
        'A function formats a numeric value using printf. An argument passed here controls display.',
        'Function arguments are passed by value. Modifying the argument does not modify the caller variable.',
    )
    ranked = rank_passages(corpus, 'Are function arguments passed by value in C?', 'C')
    assert ranked.passages[0].chunk.chunk_index == 1


def test_specific_question_includes_continued_explanation_after_heading():
    corpus = rows(
        'Section: Virtual function calls in constructors and destructors. '
        'Virtual function calls in constructors and destructors can be confusing.',
        'The constructor and destructor call the function of the current class. The derived function is not called.',
        'A constructor is a function. A destructor is a function. Virtual functions exist.',
        'Virtual functions are functions. Constructors and destructors are functions too.',
    )
    corpus[1][0].page_number = corpus[0][0].page_number
    ranked = rank_passages(corpus, 'How do virtual function calls behave in constructors and destructors?', 'C++', 2)
    assert [item.chunk.chunk_index for item in ranked.passages] == [0, 1]


def test_comparison_filler_and_repeated_subject_label_do_not_hide_relevant_passages():
    corpus = rows('malloc allocates memory without initialization. calloc allocates zero-initialized memory.')
    ranked = rank_passages(corpus, 'What is the difference between malloc and calloc in C?', 'C')
    assert ranked.passages[0].chunk.chunk_index == 0


def test_bounds_and_boundary_wording_retrieve_the_undefined_behavior_warning():
    corpus = rows(
        'C does not perform boundary checks. Accessing contents outside of the declared array is undefined.',
        'A graph uses an index to plot a value within its bounds using a function pointer.',
    )
    ranked = rank_passages(corpus, 'What happens when an array index is out of bounds in C?', 'C')
    assert ranked.passages[0].chunk.chunk_index == 0


def test_named_operator_and_dict_alias_find_membership_explanation():
    corpus = rows(
        'Dict is special: the normal in only checks the keys. Searching values requires specifying them.',
        'The operator module groups dictionary keys and values with itemgetter.',
    )
    ranked = rank_passages(corpus, 'Does the in operator check dictionary keys or values in Python?', 'Python')
    assert ranked.passages[0].chunk.chunk_index == 0


def test_short_definition_does_not_mix_in_an_unrelated_type_special_case():
    corpus = rows(
        'A default constructor is a constructor called without arguments.',
        'The default constructor can also have default arguments.',
        'An std::function default constructor omits the target instance.',
    )
    corpus[2][0].chunk_index = 200
    ranked = rank_passages(corpus, 'What is a default constructor in C++?', 'C++')
    assert ranked.definition_focus
    assert {item.chunk.chunk_index for item in ranked.passages} == {0, 1}


def test_unknown_topic_does_not_get_sources_from_filler_or_substrings():
    corpus = rows('Interfaces define contracts. Work on a class by implementing its methods.')
    for question in ['How does Neptune orbit work?', 'What is a face?', 'What is the difference between flarble and zorb?']:
        assert rank_passages(corpus, question, 'Java').passages == []


@pytest.mark.parametrize('question', [
    'What is the acceptance marker in this reference?',
    'Which marker does my reference give?',
    'Tell me about the marker in our reference.',
])
def test_personal_reference_questions_ignore_conversational_pronouns(question):
    corpus = rows('The second account uses a distinct private acceptance reference. Its private marker is SAMPLE-42.')
    found = rank_passages(corpus, question, 'Acceptance Lab').passages
    assert found and found[0].chunk.chunk_index == 0


@pytest.mark.parametrize('question', [
    'What is this Neptune orbital marker?',
    'What is the password for my AWS account?',
    'What is this flarble?',
])
def test_pronoun_filter_keeps_unknown_topic_qualifiers(question):
    corpus = rows('The reference records the acceptance marker SAMPLE-42 for this account.')
    assert rank_passages(corpus, question, 'Acceptance Lab').passages == []


@pytest.mark.parametrize('question', ['What does `this` mean in Java?', 'Explain the this pointer in C++.', 'What is this in Java?'])
def test_named_this_identifier_is_not_conversational_filler(question):
    assert 'this' in query_terms(question, 'All')
    assert 'this' not in query_terms('What marker is in this book?', 'All')


def test_explicit_question_clauses_keep_evidence_for_each_supported_part():
    corpus = rows('Parentheses are optional for a tuple; values are comma-separated.',
        'A list is mutable; a tuple is immutable.',
        'A list has indexed items. Lists can be appended and sorted.')
    ranked = rank_passages(corpus,
        'What is the difference between a list and a tuple? Are parentheses required for a tuple?', 'Python')
    assert {0, 1}.issubset({item.chunk.chunk_index for item in ranked.passages})
    assert (1, 0) in ranked.priority_keys


def test_containment_phrasing_finds_mutable_value_in_tuple_without_dropping_topics():
    corpus = rows('A tuple can contain a list. The list can be modified but the tuple cannot.',
        'Tuples are immutable sequences.', 'A list can be sorted in place.')
    ranked = rank_passages(corpus, 'Can the list stored inside my tuple still be modified?', 'Python')
    assert ranked.passages and ranked.passages[0].chunk.chunk_index == 0


def test_change_paraphrase_finds_parameter_modification_with_caller_variable():
    corpus = rows('Function parameters are passed by value. Modifying them does not affect caller variables.',
        'An argument to a macro can be repeated. A variable can be declared in a macro.')
    ranked = rank_passages(corpus, "If a function changes its argument in C, will the caller's variable change too?", 'C')
    assert ranked.passages and ranked.passages[0].chunk.chunk_index == 0


def test_ranker_diversifies_pages_without_losing_only_available_same_page_evidence():
    corpus = rows('An interface is a contract.', 'An interface is a contract for methods.', 'An interface is a contract for classes.')
    corpus[1][0].page_number = 1
    ranked = rank_passages(corpus, 'Explain an interface.', 'Java', 3)
    assert {item.chunk.page_number for item in ranked.passages[:2]} == {1, 3}
    assert len(ranked.passages) == 3


def test_partial_hybrid_cannot_crowd_out_unembedded_compound_definitions(db_session, monkeypatch):
    doc = Document(title='C++ Reference', filename='ref.pdf', original_filename='ref.pdf', subject='C++', is_default=True, status='partial')
    db_session.add(doc)
    db_session.flush()
    texts = [
        'A constructor is a member function that initializes an object.',
        'A destructor is a member function called when an object is destroyed.',
        'Virtual calls in constructors and destructors behave differently. Constructors and destructors call virtual functions.',
        'Function try blocks in constructors and destructors rethrow exceptions. Constructors and destructors have handlers.',
        'Pure virtual calls in constructors and destructors have undefined behavior.',
        'Constructors and destructors during stack unwinding require special handling.',
    ]
    vector = [1.0] + [0.0] * (settings.EMBEDDING_DIMENSIONS - 1)
    for index, text in enumerate(texts):
        chunk = DocumentChunk(document_id=doc.id, chunk_index=index, page_number=1 if index >= 2 else index + 10, content=text)
        if index >= 2:
            chunk.embedding_json = json.dumps(vector)
            chunk.metadata_json = json.dumps({'embedding': embedding_service.provenance(text)})
        db_session.add(chunk)
    db_session.commit()
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr(embedding_service, 'generate_embedding', Mock(return_value=vector))
    sources = rag_service.retrieve_relevant_chunks(db_session, 'How do constructors and destructors work in C++?', 'C++')
    assert {source.chunk_index for source in sources[:2]} == {0, 1}
    assert len(sources) <= 5


def test_all_search_honors_single_explicit_language_without_mutating_preferences(db_session):
    for language in ['C++', 'Java']:
        doc = Document(title=language, filename=language + '.pdf', original_filename='ref.pdf',
            subject=language, is_default=True, status='partial')
        db_session.add(doc)
        db_session.flush()
        db_session.add(DocumentChunk(document_id=doc.id, chunk_index=0, page_number=1,
            content='A constructor is a member function that initializes an object.'))
    db_session.commit()
    found = rag_service.retrieve_relevant_chunks(db_session, 'What is a constructor in C++?', 'All')
    assert found and {source.document_title for source in found} == {'C++'}
    generic = rag_service.retrieve_relevant_chunks(db_session, 'What is a constructor?', 'All')
    assert {source.document_title for source in generic} == {'C++', 'Java'}


def test_small_semantic_sample_cannot_displace_the_unembedded_majority(db_session, monkeypatch):
    doc = Document(title='C Reference', filename='ref.pdf', original_filename='ref.pdf', subject='C', is_default=True, status='partial')
    db_session.add(doc)
    db_session.flush()
    vector = [1.0] + [0.0] * (settings.EMBEDDING_DIMENSIONS - 1)
    for index in range(6):
        text = ('malloc allocation failures affect pointers. Check allocation failures before using pointers.'
            if index < 4 else 'Pointers refer to memory addresses.')
        chunk = DocumentChunk(document_id=doc.id, chunk_index=index, page_number=index + 1, content=text)
        if index >= 4:
            chunk.embedding_json = json.dumps(vector)
            chunk.metadata_json = json.dumps({'embedding': embedding_service.provenance(text)})
        db_session.add(chunk)
    db_session.commit()
    monkeypatch.setattr(embedding_service, 'is_configured', lambda: True)
    monkeypatch.setattr(embedding_service, 'generate_embedding', lambda query: vector)
    found = rag_service.retrieve_relevant_chunks(db_session, 'How do malloc allocation failures affect pointers?', 'C')
    assert {0, 1, 2, 3}.issubset({source.chunk_index for source in found})
    assert len(found) == 5
