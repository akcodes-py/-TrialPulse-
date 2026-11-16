import math

import pytest

from evaluation.eval_trec import evaluate_files, read_run, topic_metrics


def test_precision_denominator_and_linear_ndcg():
    metrics = topic_metrics({"A": 2, "B": 1}, ["B", "A"])
    assert metrics["precision_5"] == 0.2
    assert metrics["precision_10"] == 0.1
    expected = (1 + 2 / math.log2(3)) / (2 + 1 / math.log2(3))
    assert metrics["ndcg_10"] == pytest.approx(expected)


def test_missing_topic_scores_zero_and_run_order_uses_score(tmp_path):
    qrels = tmp_path / "qrels"
    run = tmp_path / "run"
    qrels.write_text("1 0 A 2\n2 0 B 2\n")
    run.write_text("1 Q0 C 1 1 demo\n1 Q0 A 2 9 demo\n")
    assert read_run(run)["1"] == ["A", "C"]
    report = evaluate_files(qrels, {"test": run}, "test")
    assert report["results"][0]["ndcg_10"] == 0.5
    assert report["results"][0]["missing_topics"] == ["2"]


def test_duplicate_documents_are_not_double_counted(tmp_path):
    path = tmp_path / "run"
    path.write_text("1 Q0 A 1 10 run\n1 Q0 A 2 9 run")
    with pytest.raises(ValueError, match="Duplicate"):
        read_run(path)
