import json
from pathlib import Path
from sentence_transformers import SentenceTransformer
from huggingface_hub import snapshot_download
from src.tools.memory.chroma_manager import get_collection, list_collections, get_client

HOME = Path.home()
MODEL_DIR = HOME / ".embedding_models" / "sentence-transformers"
MODEL_NAME = "all-MiniLM-L6-v2"
MODEL_PATH = MODEL_DIR / MODEL_NAME

_embedder = None


def _ensure_model():
    if not MODEL_DIR.exists():
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if not MODEL_PATH.exists():
        try:
            snapshot_download(
                repo_id='sentence-transformers/all-MiniLM-L6-v2',
                local_dir=str(MODEL_PATH)
            )
        except Exception:
            try:
                snapshot_download(
                    repo_id='sentence-transformers/all-MiniLM-L6-v2',
                    local_dir=str(MODEL_PATH),
                    local_files_only=True
                )
            except Exception as e:
                raise RuntimeError(f"无法加载嵌入模型: {e}")


def _get_embedder():
    global _embedder
    if _embedder is None:
        _ensure_model()
        _embedder = SentenceTransformer(str(MODEL_PATH))
    return _embedder


def memory_store(collection_name: str, texts: list, ids: list, metadatas: list = None) -> str:
    if not texts or not ids:
        return json.dumps(
            {
                "success": False,
                "summary": "texts和ids不能为空",
                "count": 0
            },
            ensure_ascii=False
        )
    if len(texts) != len(ids):
        return json.dumps(
            {
                "success": False,
                "summary": f"texts({len(texts)})与ids({len(ids)})数量不匹配",
                "count": 0
            },
            ensure_ascii=False
        )
    try:
        embedder = _get_embedder()
        embeddings = embedder.encode(texts, show_progress_bar=False).tolist()
        collection = get_collection(collection_name)
        collection.add(embeddings=embeddings, documents=texts, ids=ids, metadatas=metadatas)
        return json.dumps(
            {
                "success": True,
                "summary": f"存入{len(texts)}条到集合'{collection_name}'",
                "count": len(texts)
            },
            ensure_ascii=False
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e),
                "count": 0
            },
            ensure_ascii=False
        )


def memory_query(collection_name: str, query_text: str, n_results: int = 5) -> str:
    if not query_text.strip():
        return json.dumps(
            {
                "success": False,
                "summary": "查询文本不能为空",
                "results": []
            },
            ensure_ascii=False
        )
    try:
        embedder = _get_embedder()
        collection = get_collection(collection_name)
        qe = embedder.encode([query_text], show_progress_bar=False).tolist()
        raw = collection.query(query_embeddings=qe, n_results=n_results)
        results = []
        if raw and raw.get("ids") and raw["ids"][0]:
            for i in range(len(raw["ids"][0])):
                results.append({
                    "id": raw["ids"][0][i],
                    "text": raw["documents"][0][i] if raw.get("documents") else "",
                    "score": raw["distances"][0][i] if raw.get("distances") else None,
                    "metadata": raw["metadatas"][0][i] if raw.get("metadatas") else {},
                })
        return json.dumps(
            {
                "success": True,
                "summary": f"找到{len(results)}条",
                "results": results
            },
            ensure_ascii=False
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e),
                "results": []
            },
            ensure_ascii=False
        )


def memory_list_collections() -> str:
    try:
        names = [c.name for c in list_collections()]
        return json.dumps(
            {
                "success": True,
                "collections": names,
                "summary": f"共{len(names)}个集合"
            },
            ensure_ascii=False
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "collections": [],
                "summary": str(e)
            },
            ensure_ascii=False
        )


def memory_delete_collection(collection_name: str) -> str:
    try:
        get_client().delete_collection(collection_name)
        return json.dumps(
            {
                "success": True,
                "summary": f"集合'{collection_name}'已删除"
            },
            ensure_ascii=False
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "summary": str(e)
            },
            ensure_ascii=False
        )


# ── Schemas ──
MEMORY_STORE_SCHEMA = {
    "type": "function", "function": {
        "name": "memory_store",
        "description": "将文本存入ChromaDB知识库",
        "parameters": {"type": "object", "properties": {
            "collection_name": {"type": "string", "description": "集合名称"},
            "texts": {"type": "array", "items": {"type": "string"}, "description": "待存储的文本列表"},
            "ids": {"type": "array", "items": {"type": "string"}, "description": "唯一ID列表，与texts一一对应"},
            "metadatas": {"type": "array", "items": {"type": "object"}, "description": "可选，元数据字典列表，与texts一一对应"},
        }, "required": ["collection_name", "texts", "ids"]},
    },
}

MEMORY_QUERY_SCHEMA = {
    "type": "function", "function": {
        "name": "memory_query",
        "description": "在知识库中语义检索相关内容",
        "parameters": {"type": "object", "properties": {
            "collection_name": {"type": "string", "description": "集合名称"},
            "query_text": {"type": "string", "description": "查询文本"},
            "n_results": {"type": "integer", "description": "返回结果数，默认5"},
        }, "required": ["collection_name", "query_text"]},
    },
}

MEMORY_LIST_SCHEMA = {
    "type": "function", "function": {
        "name": "memory_list_collections",
        "description": "列出所有ChromaDB集合",
        "parameters": {"type": "object", "properties": {
        }, "required": []},
    },
}

MEMORY_DELETE_SCHEMA = {
    "type": "function", "function": {
        "name": "memory_delete_collection",
        "description": "删除整个ChromaDB集合（不可逆，须先确认）",
        "parameters": {"type": "object", "properties": {
            "collection_name": {"type": "string", "description": "要删除的集合名称"},
        }, "required": ["collection_name"]},
    },
}
