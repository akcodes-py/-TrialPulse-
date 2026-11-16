import hashlib
import math
import re
from collections import Counter
from functools import lru_cache

from backend.app.fixtures import demo_trials
from backend.app.schemas import Match, PatientProfile, Trial
from backend.app.settings import get_settings


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())


def trial_text(trial: Trial) -> str:
    return " ".join([trial.title, *trial.conditions, trial.summary, trial.eligibility_text])


def patient_query(patient: PatientProfile) -> str:
    return " ".join(f"{f.label} {f.value or ''}" for f in patient.facts if not f.negative)


def hashed_vector(text: str, size: int = 128) -> list[float]:
    """Deterministic lexical demo vector; intentionally not a biomedical embedding."""
    result = [0.0] * size
    for token in tokens(text):
        raw = hashlib.blake2b(token.encode(), digest_size=8).digest()
        result[int.from_bytes(raw[:4], "big") % size] += 1 if raw[4] % 2 else -1
    norm = math.sqrt(sum(x * x for x in result)) or 1
    return [x / norm for x in result]


def demo_search(patient: PatientProfile, top_k: int) -> list[Match]:
    trials = demo_trials()
    documents = [tokens(trial_text(trial)) for trial in trials]
    query = tokens(patient_query(patient))
    average_length = sum(map(len, documents)) / len(documents)
    lexical, dense = {}, {}
    query_vector = hashed_vector(" ".join(query))
    for trial, document in zip(trials, documents):
        counts = Counter(document)
        score = 0.0
        for token in set(query):
            df = sum(token in doc for doc in documents)
            idf = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
            tf = counts[token]
            score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * len(document) / average_length))
        lexical[trial.id] = score
        dense[trial.id] = sum(x * y for x, y in zip(query_vector, hashed_vector(trial_text(trial))))
    ranks = [
        {key: i + 1 for i, key in enumerate(sorted(scores, key=scores.get, reverse=True))}
        for scores in (lexical, dense)
    ]
    matches = [
        Match(
            trial=trial,
            retrieval_score=sum(1 / (60 + r[trial.id]) for r in ranks),
            dense_score=dense[trial.id],
            lexical_score=lexical[trial.id],
        )
        for trial in trials
    ]
    return sorted(matches, key=lambda m: m.retrieval_score, reverse=True)[:top_k]


@lru_cache
def biomedical_encoder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().model_name)


@lru_cache
def sparse_encoder():
    from fastembed import SparseTextEmbedding

    return SparseTextEmbedding(model_name="Qdrant/bm25")


@lru_cache
def qdrant_client():
    from qdrant_client import QdrantClient

    return QdrantClient(url=get_settings().qdrant_url, timeout=30)


def qdrant_search(patient: PatientProfile, top_k: int) -> list[Match]:
    from qdrant_client import models

    query = patient_query(patient)
    dense = biomedical_encoder().encode(query, normalize_embeddings=True).tolist()
    sparse = next(iter(sparse_encoder().query_embed(query)))
    result = qdrant_client().query_points(
        collection_name=get_settings().collection,
        prefetch=[
            models.Prefetch(query=dense, using="dense", limit=max(100, top_k)),
            models.Prefetch(
                query=models.SparseVector(indices=sparse.indices.tolist(), values=sparse.values.tolist()),
                using="sparse",
                limit=max(100, top_k),
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )
    return [
        Match(trial=Trial.model_validate(point.payload["trial"]), retrieval_score=point.score)
        for point in result.points
    ]


def retrieve(patient: PatientProfile, top_k: int) -> list[Match]:
    if get_settings().retrieval == "qdrant":
        return qdrant_search(patient, top_k)
    return demo_search(patient, top_k)
