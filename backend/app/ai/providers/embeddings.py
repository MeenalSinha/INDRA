import logging
from ..interfaces import EmbeddingProvider

log = logging.getLogger("indra.ai.providers.embeddings")

class TfIdfEmbeddingProvider(EmbeddingProvider):
    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        # Not heavily used, pairwise_similarity is the main entrypoint
        return []
        
    async def pairwise_similarity(self, texts: list[str]) -> list[list[float]]:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        
        cleaned = [t if t and t.strip() else "empty report" for t in texts]
        if len(cleaned) < 2:
            return [[1.0]]
            
        vectorizer = TfidfVectorizer(stop_words="english", min_df=1)
        try:
            matrix = vectorizer.fit_transform(cleaned)
            return cosine_similarity(matrix).tolist()
        except ValueError:
            n = len(cleaned)
            return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


class TransformersEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._st_model = None
        self._load_model()
        
    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            self._st_model = SentenceTransformer(self.model_name)
            log.info(f"Sentence-Transformers {self.model_name} loaded successfully.")
        except Exception as exc:
            log.warning(f"Failed to load Transformers model {self.model_name}: {exc}")
            self._st_model = None

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not self._st_model:
            raise RuntimeError("Transformers model not loaded")
        cleaned = [t if t and t.strip() else "empty report" for t in texts]
        embeddings = self._st_model.encode(cleaned, convert_to_numpy=True, show_progress_bar=False)
        return embeddings.tolist()

    async def pairwise_similarity(self, texts: list[str]) -> list[list[float]]:
        if not self._st_model:
            raise RuntimeError("Transformers model not loaded")
            
        import numpy as np
        cleaned = [t if t and t.strip() else "empty report" for t in texts]
        if len(cleaned) < 2:
            return [[1.0]]
            
        embeddings = self._st_model.encode(cleaned, convert_to_numpy=True, show_progress_bar=False)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1e-9, norms)
        normed = embeddings / norms
        matrix = normed @ normed.T
        return matrix.tolist()
