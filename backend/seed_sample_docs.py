"""
TechQuery Sample Document Seeder
Generates genuine multi-page technical PDF textbooks and indexes them in TechQuery.
This allows immediate testing of RAG search, citations, and Gemini Q&A.
"""

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database.session import SessionLocal, Base, engine
from app.models.document import Document
from app.models.user import User
from app.services.rag_service import rag_service
from app.services.storage_service import storage_service

def make_simple_pdf(pages_text, output_path):
    """Generate a clean, standard PDF 1.4 file with pure Python."""
    num_pages = len(pages_text)
    page_obj_ids = []
    content_obj_ids = []

    curr_id = 3
    for _ in range(num_pages):
        page_obj_ids.append(curr_id)
        content_obj_ids.append(curr_id + 1)
        curr_id += 2

    font_id = curr_id

    obj_defs = {}
    obj_defs[1] = '<< /Type /Catalog /Pages 2 0 R >>'
    kids_str = ' '.join(f'{pid} 0 R' for pid in page_obj_ids)
    obj_defs[2] = f'<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>'

    for i, (page_id, content_id) in enumerate(zip(page_obj_ids, content_obj_ids)):
        obj_defs[page_id] = f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>'

        lines = pages_text[i]
        stream_lines = ['BT', '/F1 12 Tf', '50 720 Td']
        for line_idx, line in enumerate(lines):
            safe_line = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            if line_idx > 0:
                stream_lines.append('0 -22 Td')
            stream_lines.append(f'({safe_line}) Tj')
        stream_lines.append('ET')
        stream_data = '\n'.join(stream_lines).encode('latin1')
        obj_defs[content_id] = f'<< /Length {len(stream_data)} >> stream\n' + stream_data.decode('latin1') + '\nendstream'

    obj_defs[font_id] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'

    out = ['%PDF-1.4\n']
    offsets = {}

    for oid in sorted(obj_defs.keys()):
        offset = sum(len(chunk.encode('latin1')) for chunk in out)
        offsets[oid] = offset
        body = obj_defs[oid]
        out.append(f'{oid} 0 obj\n{body}\nendobj\n')

    xref_offset = sum(len(chunk.encode('latin1')) for chunk in out)
    total_objs = max(obj_defs.keys()) + 1
    out.append(f'xref\n0 {total_objs}\n0000000000 65535 f \n')
    for oid in range(1, total_objs):
        off = offsets.get(oid, 0)
        out.append(f'{off:010d} 00000 n \n')
    out.append(f'trailer\n<< /Size {total_objs} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n')

    full_pdf = ''.join(out).encode('latin1')
    with open(output_path, 'wb') as f:
        f.write(full_pdf)

SAMPLE_DOCS = [
    {
        "filename": "java_core_handbook.pdf",
        "title": "Java Core Programming Handbook",
        "subject": "Java",
        "pages": [
            [
                "Java Architecture and Platform Overview",
                "Java is a high-level, class-based, object-oriented programming language designed to have as few implementation dependencies as possible.",
                "Write Once, Run Anywhere (WORA): Java source code (.java) is compiled into platform-independent bytecode (.class).",
                "The Java Virtual Machine (JVM) executes bytecode on the host operating system.",
                "The Java Development Kit (JDK) contains compilers and tools, while Java Runtime Environment (JRE) provides libraries and the JVM.",
                "Garbage Collection in Java automatically reclaims memory by identifying objects that are no longer reachable by active references."
            ],
            [
                "Object-Oriented Programming Principles in Java",
                "Encapsulation: Bundling data and methods into a single unit, using private fields with public getters and setters.",
                "Inheritance: Creating new classes using existing classes with the extends keyword, promoting code reuse.",
                "Polymorphism: Allowing entities to take on multiple forms through method overloading (compile-time) and method overriding (runtime).",
                "Abstraction: Hiding complex internal implementation details and exposing only the essential interface through abstract classes and interfaces."
            ],
            [
                "Java Interfaces and Multiple Inheritance",
                "An interface in Java is a reference type, similar to a class, that can contain only constants, method signatures, default methods, and static methods.",
                "Interfaces cannot be instantiated directly; they must be implemented by classes using the implements keyword.",
                "A class can implement multiple interfaces, allowing Java to support multiple inheritance of type without the diamond problem.",
                "All methods declared without a body in an interface are implicitly public and abstract.",
                "Example: interface Printable { void print(); } class Document implements Printable { public void print() { System.out.println(); } }"
            ],
            [
                "Exception Handling and Concurrency in Java",
                "Java organizes exceptions under the Throwable hierarchy: Checked Exceptions (IOException, SQLException) and Unchecked RuntimeExceptions.",
                "The try-catch-finally block ensures robust execution and guaranteed resource cleanup.",
                "Java provides built-in multithreading support through the Thread class and the Runnable interface.",
                "The synchronized keyword prevents race conditions by acquiring intrinsic locks on shared objects."
            ]
        ]
    },
    {
        "filename": "c_programming_handbook.pdf",
        "title": "C Programming Sample Handbook",
        "subject": "C",
        "pages": [
            [
                "C Pointers and Arrays",
                "A pointer stores an address. Use the address-of operator & to obtain the address of an object and the indirection operator * to access the pointed-to object."
            ],
            [
                "C Memory Allocation",
                "malloc allocates a block of uninitialized storage and returns a pointer. Check for a null result before use. Release allocated storage with free when it is no longer needed."
            ]
        ]
    },
    {
        "filename": "cpp_programming_handbook.pdf",
        "title": "C++ Programming Sample Handbook",
        "subject": "C++",
        "pages": [
            [
                "C++ Constructors and Destructors",
                "A constructor initializes an object. A destructor runs when the object lifetime ends. Resource Acquisition Is Initialization associates resource ownership with object lifetime."
            ],
            [
                "C++ Containers",
                "std::vector provides a sequence of contiguous elements. std::vector manages its storage and can grow as elements are inserted."
            ]
        ]
    },
    {
        "filename": "python_programming_handbook.pdf",
        "title": "Python Programming Sample Handbook",
        "subject": "Python",
        "pages": [
            [
                "Python Lists and Tuples",
                "A list is a mutable sequence. A tuple is an immutable sequence, although an object stored inside a tuple can itself be mutable. Both support indexing and iteration."
            ],
            [
                "Python Exceptions",
                "Use try and except to handle exceptions. A finally block runs as control leaves the try statement. Use a with statement to manage resources such as open files."
            ]
        ]
    }
]

def seed_sample_documents():
    """Build and register sample technical documents."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    print("[*] Generating sample technical PDF textbooks...")

    docs_dir = Path(storage_service.base_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)

    for doc_meta in SAMPLE_DOCS:
        filename = doc_meta["filename"]
        target_path = docs_dir / filename

        # Check if already in DB
        existing = db.query(Document).filter(Document.filename == filename).first()
        if existing:
            print(f"[-] Document '{doc_meta['title']}' already exists. Preserving its PDF and index; use manage_index.py to resume.")
            continue

        if target_path.exists():
            print(f"[-] Preserving existing unregistered PDF: {filename}")
            continue

        # Generate PDF
        make_simple_pdf(doc_meta["pages"], str(target_path))
        file_size = os.path.getsize(target_path)
        print(f"[+] Created PDF '{filename}' ({file_size} bytes, {len(doc_meta['pages'])} pages)")

        if not existing:
            doc = Document(
                title=doc_meta["title"],
                filename=filename,
                original_filename=filename,
                file_size=file_size,
                subject=doc_meta["subject"],
                total_pages=len(doc_meta["pages"]),
                status="pending"
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
        else:
            doc = existing

        # Process and chunk document
        print(f"[*] Chunking and indexing '{doc.title}'...")
        try:
            pages, chunks = rag_service.process_document(db, doc.id)
            print(f"[+] Successfully indexed '{doc.title}': {pages} pages, {chunks} chunks.")
        except Exception as e:
            print(f"[!] Processing notice: {e}")

    db.close()
    print("\n[V] TechQuery sample documents seeded successfully!")

if __name__ == "__main__":
    seed_sample_documents()
