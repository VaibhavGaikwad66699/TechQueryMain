import io
import pypdf

def get_auth_token(client):
    register_payload = {
        "email": "docuser@college.edu",
        "username": "DocUser",
        "password": "Password123!"
    }
    res = client.post("/api/v1/auth/register", json=register_payload)
    return res.json()["access_token"]

def create_sample_pdf_bytes():
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    stream = io.BytesIO()
    writer.write(stream)
    stream.seek(0)
    return stream.getvalue()

def test_document_lifecycle(client):
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Reject non-PDF file
    files = {"file": ("notes.txt", b"plain text", "text/plain")}
    res_bad = client.post("/api/v1/documents/upload", files=files, data={"subject": "Java"}, headers=headers)
    assert res_bad.status_code == 400

    # 2. Upload valid PDF
    pdf_bytes = create_sample_pdf_bytes()
    files = {"file": ("Java_Basics.pdf", pdf_bytes, "application/pdf")}
    data = {"title": "Java Basics Guide", "subject": "Java", "auto_process": "false"}
    res_upload = client.post("/api/v1/documents/upload", files=files, data=data, headers=headers)
    assert res_upload.status_code == 201
    doc = res_upload.json()["document"]
    doc_id = doc["id"]
    assert doc["title"] == "Java Basics Guide"
    assert doc["subject"] == "Java"

    # 3. List documents
    res_list = client.get("/api/v1/documents", headers=headers)
    assert res_list.status_code == 200
    docs = res_list.json()
    assert any(d["id"] == doc_id for d in docs)

    # 4. Get document detail
    res_get = client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["id"] == doc_id

    # 5. Delete document
    res_del = client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert res_del.status_code == 200

    # 6. Verify deleted
    assert client.get(f"/api/v1/documents/{doc_id}", headers=headers).status_code == 404
