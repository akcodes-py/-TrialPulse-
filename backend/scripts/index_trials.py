"""Create a fresh dual-vector collection from normalized trial JSONL."""

import argparse
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from backend.app.retrieval import biomedical_encoder, qdrant_client, sparse_encoder, trial_text
from backend.app.schemas import Trial
from backend.app.settings import get_settings


def index(path: Path):
    from qdrant_client import models

    settings = get_settings()
    client = qdrant_client()
    encoder = biomedical_encoder()
    dimension = encoder.get_sentence_embedding_dimension()
    if client.collection_exists(settings.collection):
        raise ValueError(
            "Collection already exists. Choose a new TRIALPULSE_COLLECTION to avoid mixing corpora or embedding versions."
        )
    client.create_collection(
        collection_name=settings.collection,
        vectors_config={"dense": models.VectorParams(size=dimension, distance=models.Distance.COSINE)},
        sparse_vectors_config={"sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )
    total = 0

    def upload(trials):
        texts = [trial_text(t) for t in trials]
        dense_vectors = encoder.encode(texts, normalize_embeddings=True, batch_size=32)
        sparse_vectors = list(sparse_encoder().embed(texts))
        points = [
            models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, trial.id)),
                vector={
                    "dense": dense.tolist(),
                    "sparse": models.SparseVector(
                        indices=sparse.indices.tolist(), values=sparse.values.tolist()
                    ),
                },
                payload={"trial": trial.model_dump(mode="json"), "embedding_model": settings.model_name},
            )
            for trial, dense, sparse in zip(trials, dense_vectors, sparse_vectors)
        ]
        client.upsert(collection_name=settings.collection, points=points, wait=True)

    with path.open(encoding="utf-8") as handle:
        batch = []
        for line in handle:
            if not line.strip():
                continue
            trial = Trial.model_validate_json(line)
            if trial.status != "RECRUITING":
                continue
            batch.append(trial)
            if len(batch) == 32:
                upload(batch)
                total += len(batch)
                batch.clear()
        if batch:
            upload(batch)
            total += len(batch)
    print(f"Indexed {total} recruiting trials into {settings.collection}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/local/trials.jsonl"))
    index(parser.parse_args().input)
