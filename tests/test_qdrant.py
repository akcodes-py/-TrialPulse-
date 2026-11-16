"""Exercise the actual Qdrant query contract with a local in-memory collection.

Only the heavyweight encoders are replaced with known deterministic test vectors.
"""

from types import SimpleNamespace

import pytest

from backend.app.fixtures import demo_trials
from backend.app.settings import get_settings


def test_named_vectors_rrf_and_payload_roundtrip(monkeypatch, patient):
    np = pytest.importorskip("numpy")
    qdrant = pytest.importorskip("qdrant_client")
    from qdrant_client import models

    from backend.app import retrieval

    client = qdrant.QdrantClient(":memory:")
    collection = get_settings().collection
    client.create_collection(
        collection,
        vectors_config={"dense": models.VectorParams(size=3, distance=models.Distance.COSINE)},
        sparse_vectors_config={"sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )
    trial = demo_trials()[0]
    client.upsert(
        collection,
        points=[
            models.PointStruct(
                id=1,
                vector={"dense": [1.0, 0.0, 0.0], "sparse": models.SparseVector(indices=[5], values=[1.0])},
                payload={
                    "trial": trial.model_dump(mode="json"),
                    "embedding_model": get_settings().model_name,
                },
            )
        ],
    )
    monkeypatch.setattr(retrieval, "qdrant_client", lambda: client)
    monkeypatch.setattr(
        retrieval,
        "biomedical_encoder",
        lambda: SimpleNamespace(encode=lambda *a, **kw: np.array([1.0, 0.0, 0.0])),
    )
    sparse = SimpleNamespace(indices=np.array([5]), values=np.array([1.0]))
    monkeypatch.setattr(
        retrieval, "sparse_encoder", lambda: SimpleNamespace(query_embed=lambda _: iter([sparse]))
    )
    result = retrieval.qdrant_search(patient, 25)
    assert len(result) == 1
    assert result[0].trial.id == trial.id
    assert result[0].trial.criteria == trial.criteria
    assert result[0].retrieval_score > 0
    client.close()
