"""Seeds the pattern knowledge base from knowledge_base/*.md using Ollama embeddings."""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from vector_store import get_collection
from config import CHROMA_PATH, COLLECTIONS


KB_DIR = Path(__file__).resolve().parent / 'knowledge_base'


def chunk_text(text: str, words_per_chunk: int = 180) -> list:
    words = text.split()
    chunks = []
    for i in range(0, len(words), words_per_chunk):
        chunk = ' '.join(words[i:i + words_per_chunk]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def ingest():
    if not KB_DIR.exists():
        print(f'[ERROR] Knowledge base directory missing: {KB_DIR}')
        sys.exit(1)

    md_files = sorted(KB_DIR.glob('*.md'))
    if not md_files:
        print(f'[ERROR] No .md files in {KB_DIR}')
        sys.exit(1)

    print(f'[INGEST] ChromaDB path: {CHROMA_PATH}')
    print(f'[INGEST] Collection:    {COLLECTIONS["patterns"]}')
    print(f'[INGEST] Found {len(md_files)} markdown files.\n')

    col = get_collection('patterns')
    total = 0
    for path in md_files:
        content = path.read_text(encoding='utf-8')
        chunks = chunk_text(content)
        ids, docs, metas = [], [], []
        for i, chunk in enumerate(chunks):
            ids.append(f'{path.stem}_{i}')
            docs.append(chunk)
            metas.append({'source': path.name, 'chunk_index': i})
        if ids:
            col.upsert(ids=ids, documents=docs, metadatas=metas)
        total += len(chunks)
        print(f'  {path.name}: {len(chunks)} chunks')

    print(f'\n[INGEST] Done. {total} chunks stored. Collection size: {col.count()}')


if __name__ == '__main__':
    ingest()
