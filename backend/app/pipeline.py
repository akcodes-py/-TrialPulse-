import asyncio
from datetime import date
from time import perf_counter
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.eligibility import critique, eligibility_status, evaluate_rule
from backend.app.fhir import parse_fhir
from backend.app.retention import score_retention
from backend.app.retrieval import retrieve
from backend.app.schemas import Match, PatientProfile, PipelineRequest, PipelineResponse, TraceStep
from backend.app.settings import get_settings


class State(TypedDict, total=False):
    bundle: dict
    request: PipelineRequest
    as_of: date
    patient: PatientProfile
    candidates: list[Match]
    trace: list[TraceStep]


def traced(state: State, start: float, node: str, detail: str) -> list[TraceStep]:
    return [
        *state.get("trace", []),
        TraceStep(node=node, duration_ms=round((perf_counter() - start) * 1000, 2), detail=detail),
    ]


async def extract(state: State):
    start = perf_counter()
    patient = parse_fhir(state["bundle"], state["as_of"])
    return {
        "patient": patient,
        "trace": traced(state, start, "FHIR Parser", f"{len(patient.facts)} coded facts extracted"),
    }


async def search(state: State):
    start = perf_counter()
    candidates = await asyncio.to_thread(retrieve, state["patient"], state["request"].top_k)
    return {
        "candidates": candidates,
        "trace": traced(
            state, start, "Hybrid Search", f"{len(candidates)} candidates · {get_settings().retrieval}"
        ),
    }


async def evaluate(state: State):
    start = perf_counter()

    def audit(match):
        result = match.model_copy(deep=True)
        result.verdicts = [evaluate_rule(rule, state["patient"]) for rule in match.trial.criteria]
        return result

    audited = await asyncio.gather(
        *[asyncio.to_thread(audit, match) for match in state["candidates"][: state["request"].audit_k]]
    )
    return {
        "candidates": [*audited, *state["candidates"][len(audited) :]],
        "trace": traced(state, start, "Evaluator", f"{len(audited)} protocols evaluated concurrently"),
    }


async def critic(state: State):
    start = perf_counter()
    candidates = [match.model_copy(deep=True) for match in state["candidates"]]
    for match in candidates:
        by_id = {rule.rule_id: rule for rule in match.trial.criteria}
        match.verdicts = [
            critique(by_id[v.rule_id], v, state["patient"], state["as_of"]) for v in match.verdicts
        ]
        match.eligibility = eligibility_status(match.verdicts)
    return {
        "candidates": candidates,
        "trace": traced(
            state, start, "Protocol Critic", "Citation integrity, exclusion logic & lab freshness checked"
        ),
    }


async def rank(state: State):
    start = perf_counter()
    candidates = [match.model_copy(deep=True) for match in state["candidates"]]

    async def predict(match):
        if match.verdicts:
            match.retention = await asyncio.to_thread(score_retention, state["patient"], match.trial)

    await asyncio.gather(*[predict(match) for match in candidates])
    # Eligibility dominates retention; retrieval resolves remaining ties.
    order = {"ELIGIBLE": 0, "NEEDS_REVIEW": 1, "INELIGIBLE": 2}

    def ranking_key(match):
        probability = match.retention.completion_probability if match.retention else None
        return (
            order[match.eligibility],
            -(probability if probability is not None else -1),
            -match.retrieval_score,
        )

    candidates.sort(key=ranking_key)
    return {
        "candidates": candidates,
        "trace": traced(
            state,
            start,
            "Retention Scorer",
            "Eligibility first, then available retention scores; retrieval breaks ties",
        ),
    }


builder = StateGraph(State)
for name, function in [
    ("extract", extract),
    ("search", search),
    ("evaluate", evaluate),
    ("critic", critic),
    ("rank", rank),
]:
    builder.add_node(name, function)
builder.add_edge(START, "extract")
for left, right in [
    ("extract", "search"),
    ("search", "evaluate"),
    ("evaluate", "critic"),
    ("critic", "rank"),
]:
    builder.add_edge(left, right)
builder.add_edge("rank", END)
graph = builder.compile()


def response_from_state(state: State) -> PipelineResponse:
    return PipelineResponse(
        patient=state["patient"],
        matches=state["candidates"],
        trace=state["trace"],
        retrieval_mode=get_settings().retrieval,
        total_candidates=len(state["candidates"]),
        as_of=state["as_of"],
    )


async def run_pipeline(bundle: dict, request: PipelineRequest, as_of: date) -> PipelineResponse:
    result = await graph.ainvoke({"bundle": bundle, "request": request, "as_of": as_of, "trace": []})
    return response_from_state(result)
