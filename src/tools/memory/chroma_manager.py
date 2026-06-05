import os
import chromadb
from pathlib import Path

CHROMA_DIR = os.path.join(str(Path.home()), ".sebastian", "chroma_db")

_client = None


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
    return _client


def get_collection(name: str = "documents"):
    client = get_client()
    return client.get_or_create_collection(name=name)


def list_collections():
    client = get_client()
    return client.list_collections()
