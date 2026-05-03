from typing import List
from core.config import settings


def chunk_document(file_path: str,
                   strategy: str = "recursive",
                   chunk_size: int = None,
                   chunk_overlap: int = None) -> List[str]:
    size    = chunk_size    or settings.default_chunk_size
    overlap = chunk_overlap or settings.default_chunk_overlap

    text = _load_file(file_path)
    if not text or not text.strip():
        return []

    if strategy == "recursive":
        return _recursive_split(text, size, overlap)
    elif strategy == "sentence":
        return _sentence_split(text, size)
    elif strategy == "paragraph":
        return _paragraph_split(text, size, overlap)
    else:
        return _fixed_split(text, size, overlap)


def _load_file(file_path: str) -> str:
    ext = file_path.lower().rsplit(".", 1)[-1] if "." in file_path else ""

    if ext == "pdf":
        return _load_pdf(file_path)
    elif ext in ("docx", "doc"):
        return _load_docx(file_path)
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()


def _load_pdf(file_path: str) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        raise ImportError("需要安装 pypdf: pip install pypdf")


def _load_docx(file_path: str) -> str:
    try:
        import docx
        doc = docx.Document(file_path)
        return "\n\n".join(para.text for para in doc.paragraphs if para.text.strip())
    except ImportError:
        raise ImportError("需要安装 python-docx: pip install python-docx")


def _recursive_split(text: str, size: int, overlap: int) -> List[str]:
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "]
    )
    return splitter.split_text(text)


def _fixed_split(text: str, size: int, overlap: int) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def _sentence_split(text: str, max_size: int = 1000) -> List[str]:
    import re
    sentences = re.split(r'(?<=[。！？.!?])\s*', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) > max_size and current:
            chunks.append(current.strip())
            current = sent
        else:
            current += " " + sent if current else sent
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _paragraph_split(text: str, size: int, overlap: int) -> List[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) > size and current:
            chunks.append(current.strip())
            if overlap > 0:
                current = current[-overlap:] + "\n\n" + para
            else:
                current = para
        else:
            current += "\n\n" + para if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks
