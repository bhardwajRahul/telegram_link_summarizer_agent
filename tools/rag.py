# tools/rag.py

from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
import faiss  # type: ignore
import numpy as np
import logging

from config import EMBEDDING_MODEL_NAME

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Handles text chunking, embedding, indexing, and retrieval for RAG."""

    def __init__(self, embedding_model_name: str = EMBEDDING_MODEL_NAME):
        try:
            self.embedding_model = SentenceTransformer(embedding_model_name)
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                is_separator_regex=False,
            )
            self.vector_store = None
            self.chunks = []
            logger.info(
                f"RAGPipeline initialized with embedding model: {embedding_model_name}"
            )
        except Exception as e:
            logger.error(
                f"Failed to initialize SentenceTransformer model '{embedding_model_name}': {e}"
            )
            # Propagate the error to prevent the RAG tool from being used incorrectly
            raise RuntimeError(
                f"Could not load embedding model: {embedding_model_name}"
            ) from e

    def build_index(self, text: str) -> tuple[bool, str | None]:
        """Chunks text, generates embeddings, and builds a FAISS index."""
        try:
            logger.info("Starting RAG index build...")
            self.chunks = self.text_splitter.split_text(text)
            if not self.chunks:
                logger.warning("Text splitting resulted in no chunks.")
                return False, "Text could not be split into chunks."

            logger.info(f"Split text into {len(self.chunks)} chunks.")
            embeddings = self.embedding_model.encode(
                self.chunks, show_progress_bar=False
            )

            if embeddings is None or len(embeddings) == 0:
                logger.error("Embedding model failed to produce embeddings.")
                return False, "Failed to generate text embeddings."

            dimension = embeddings.shape
            self.vector_store = faiss.IndexFlatL2(
                dimension
            )  # Using L2 distance for similarity
            self.vector_store.add(np.array(embeddings, dtype=np.float32))
            logger.info(
                f"Successfully built FAISS index with {self.vector_store.ntotal} vectors."
            )
            return True, None
        except Exception as e:
            logger.error(f"Error building RAG index: {e}", exc_info=True)
            self.vector_store = None  # Ensure index is cleared on error
            self.chunks = []
            return False, f"An error occurred during RAG index building: {e}"

    def retrieve_context(self, query: str, k: int = 3) -> tuple[str | None, str | None]:
        """Retrieves the top-k relevant chunks for a given query."""
        if not self.vector_store or self.vector_store.ntotal == 0:
            logger.error("Cannot retrieve context: RAG index not built or is empty.")
            return None, "RAG index is not available for context retrieval."
        if not self.chunks:
            logger.error("Cannot retrieve context: No text chunks available.")
            return None, "No text chunks available for context retrieval."

        try:
            logger.info(f"Retrieving top {k} relevant chunks for query...")
            query_embedding = self.embedding_model.encode(
                [query], show_progress_bar=False
            )
            if query_embedding is None or len(query_embedding) == 0:
                logger.error("Failed to generate query embedding.")
                return None, "Failed to generate query embedding."

            distances, indices = self.vector_store.search(
                np.array(query_embedding, dtype=np.float32), k
            )

            # Filter out invalid indices (e.g., -1 if k > ntotal)
            valid_indices = [idx for idx in indices if 0 <= idx < len(self.chunks)]

            if not valid_indices:
                logger.warning("No relevant chunks found for the query.")
                return "", None  # Return empty string, not an error

            retrieved_chunks = [self.chunks[i] for i in valid_indices]
            context = "\n\n---\n\n".join(retrieved_chunks)
            logger.info(f"Successfully retrieved {len(retrieved_chunks)} chunks.")
            return context, None
        except Exception as e:
            logger.error(f"Error retrieving context from RAG index: {e}", exc_info=True)
            return None, f"An error occurred during context retrieval: {e}"
