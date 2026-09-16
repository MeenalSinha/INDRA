"""
Semantic similarity for report text.

TWO BACKENDS, selected via ML_BACKEND env var:

  ML_BACKEND=tfidf (default, Demo Mode):
    TF-IDF + cosine similarity (scikit-learn). No model download, no GPU,
    runs entirely locally. Used when the env var is unset or set to "tfidf".

  ML_BACKEND=transformers (Live/Production Mode):
    Sentence-Transformers all-MiniLM-L6-v2 (22 MB, CPU-friendly) + cosine
    similarity. Auto-downloads to ~/.cache/huggingface on first use.
    Falls back to TF-IDF with a logged warning if the model can't be loaded.

Both backends expose the same pairwise_similarity(texts) -> NxN matrix
signature. Callers (duplicate.py, fusion/engine.py) do not change.

§4 upgrade: Sentence-Transformers backend wired behind ML_BACKEND env var.
"""
import os
import logging

log = logging.getLogger("indra.ml.embeddings")

_ML_BACKEND = os.getenv("ML_BACKEND", "tfidf").lower()

# --- Attempt to load the Sentence-Transformers model at import time if
#     the backend is configured. Graceful fallback to TF-IDF on failure.
_st_model = None
if _ML_BACKEND == "transformers":
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        _st_model = SentenceTransformer("all-MiniLM-L6-v2")
        log.info("Sentence-Transformers all-MiniLM-L6-v2 loaded (ML_BACKEND=transformers).")
    except Exception as exc:
        log.warning(
            "ML_BACKEND=transformers requested but model failed to load (%s). "
            "Falling back to TF-IDF.", exc
        )
        _st_model = None


def _tfidf_similarity(texts: list[str]):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    cleaned = [t if t and t.strip() else "empty report" for t in texts]
    if len(cleaned) < 2:
        return [[1.0]]
    vectorizer = TfidfVectorizer(stop_words="english", min_df=1)
    try:
        matrix = vectorizer.fit_transform(cleaned)
        return cosine_similarity(matrix)
    except ValueError:
        n = len(cleaned)
        return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def _transformers_similarity(texts: list[str]):
    import numpy as np
    cleaned = [t if t and t.strip() else "empty report" for t in texts]
    if len(cleaned) < 2:
        return [[1.0]]
    embeddings = _st_model.encode(cleaned, convert_to_numpy=True, show_progress_bar=False)
    # Normalise then dot-product = cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-9, norms)
    normed = embeddings / norms
    return normed @ normed.T


def pairwise_similarity(texts: list[str]):
    """Return an NxN cosine similarity matrix for the given texts.

    Uses Sentence-Transformers when ML_BACKEND=transformers AND the model
    loaded successfully at startup; otherwise uses TF-IDF.
    """
    if _st_model is not None:
        try:
            return _transformers_similarity(texts)
        except Exception as exc:
            log.warning("Transformers similarity failed (%s), falling back to TF-IDF.", exc)
    return _tfidf_similarity(texts)


def active_backend() -> str:
    """For introspection — returns which backend is actually active."""
    return "transformers" if _st_model is not None else "tfidf"
