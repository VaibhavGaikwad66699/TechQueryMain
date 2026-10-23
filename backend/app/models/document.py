from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database.session import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)  # stored file name in local storage
    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, default=0)
    subject = Column(String(100), default="All", index=True)  # API requires a specific language on upload
    total_pages = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    status = Column(String(50), default="pending", index=True)  # pending, processing, ready, error
    error_message = Column(Text, nullable=True)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_default = Column(Boolean, nullable=False, default=False, server_default='0', index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    uploader = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    extraction_checkpoint = relationship('ExtractionCheckpoint', back_populates='document', uselist=False, cascade='all, delete-orphan')

    @property
    def indexing(self):
        from app.services.index_service import index_coverage
        return index_coverage(self)

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=False, index=True)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, default=0)
    embedding_json = Column(Text, nullable=True)  # JSON-serialized float array
    metadata_json = Column(Text, nullable=True)   # Additional chunk metadata (e.g. section, headings)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("Document", back_populates="chunks")


class ExtractionCheckpoint(Base):
    __tablename__ = 'extraction_checkpoints'
    document_id = Column(Integer, ForeignKey('documents.id'), primary_key=True)
    source_sha256 = Column(String(64), nullable=False)
    total_pages = Column(Integer, nullable=False)
    last_page = Column(Integer, nullable=False, default=0)
    extractor = Column(String(30), nullable=False)
    complete = Column(Boolean, nullable=False, default=False)
    text_bytes = Column(Integer, nullable=False, default=0)
    document = relationship('Document', back_populates='extraction_checkpoint')
    pages = relationship('ExtractionPage', cascade='all, delete-orphan')


class ExtractionPage(Base):
    __tablename__ = 'extraction_pages'
    document_id = Column(Integer, ForeignKey('extraction_checkpoints.document_id'), primary_key=True)
    page_number = Column(Integer, primary_key=True)
    chunks_json = Column(Text, nullable=False)
