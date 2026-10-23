import json
from app.models.document import Document, DocumentChunk
from app.services.pdf_service import pdf_service
from app.services.embedding_service import embedding_service
from app.services.rag_service import rag_service

def test_pdf_chunking_logic():
    text = (
        "Java interfaces specify what a class must do and not how. "
        "It is the blueprint of the class. It has static constants and abstract methods. "
        "The interface in Java is a mechanism to achieve abstraction. "
        "There can be only abstract methods in the Java interface, not method body. "
        "It is used to achieve abstraction and multiple inheritance in Java."
    )
    chunks = pdf_service._split_text(text, chunk_size=100, chunk_overlap=30)
    assert len(chunks) >= 2
    assert any("interface" in c.lower() for c in chunks)

def test_cosine_similarity():
    # Identical vectors
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    sim = embedding_service.cosine_similarity(v1, v2)
    assert abs(sim - 1.0) < 1e-5

    # Orthogonal vectors
    v3 = [0.0, 1.0, 0.0]
    sim_ortho = embedding_service.cosine_similarity(v1, v3)
    assert abs(sim_ortho) < 1e-5

def test_rag_retrieval_and_preferences(db_session):
    # Create document
    doc = Document(is_default=True,
        title="C Memory Programming",
        filename="os_test.pdf",
        original_filename="Operating_Systems.pdf",
        file_size=1024,
        subject="C",
        status="ready"
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    # Create chunks
    chunk1 = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        page_number=42,
        content="Virtual memory allows the execution of processes that are not completely in memory. One major advantage is that an application program can be larger than physical memory.",
        token_count=35,
        embedding_json=None
    )
    chunk2 = DocumentChunk(
        document_id=doc.id,
        chunk_index=1,
        page_number=43,
        content="Paging is a memory management scheme that eliminates the need for contiguous allocation of physical memory.",
        token_count=20,
        embedding_json=None
    )
    db_session.add_all([chunk1, chunk2])
    db_session.commit()

    # Keyword search test
    sources = rag_service._fallback_keyword_search(
        db=db_session,
        query="What is virtual memory and paging?",
        subject="C",
        top_k=5
    )
    assert len(sources) > 0
    assert sources[0].document_title == "C Memory Programming"
    assert sources[0].page_number in [42, 43]

def test_direct_query_endpoint_guest(client):
    payload = {
        "question": "What is polymorphism?",
        "subject": "Java",
        "explanation_level": "Beginner",
        "answer_style": "Concise",
        "include_examples": True
    }
    # Unauthenticated guest call
    res = client.post("/api/v1/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert "sources" in data
    assert data["preferences_applied"]["explanation_level"] == "Beginner"
