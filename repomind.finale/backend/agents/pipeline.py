"""
LangGraph pipeline v2 - with event emitter for live progress streaming.
"""
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Callable
from agents.indexer import load_vectorstore
from agents.contextualizer import contextualize_diff
from agents.reviewer import run_reviewer, run_critic, run_reporter
from agents.diff_parser import parse_diff
import time


EventEmitter = Callable[[str, dict], None]


class ReviewState(TypedDict):
    # Input
    diff: str
    collection_name: str
    project_profile: dict
    lang: str

    # Intermediate
    parsed_diff: Optional[dict]
    context: Optional[dict]
    raw_issues: Optional[list]
    critic_result: Optional[dict]

    # Output
    report: Optional[dict]
    error: Optional[str]
    timings: dict


def _make_node(name: str, fn, emitter: Optional[EventEmitter] = None):
    """Wrapper que adiciona timing e eventos."""
    def node_fn(state: ReviewState) -> ReviewState:
        if state.get("error"):
            return state

        if emitter:
            emitter(f"{name}:start", {"agent": name})

        start = time.time()
        try:
            new_state = fn(state)
            elapsed = time.time() - start
            new_state["timings"] = {**state.get("timings", {}), name: elapsed}

            if emitter:
                event_data = {"agent": name, "elapsed": round(elapsed, 2)}
                if name == "contextualize" and new_state.get("context"):
                    event_data["context_files"] = new_state["context"].get("context_files", [])[:5]
                    event_data["queries"] = new_state["context"].get("queries_used", [])[:3]
                elif name == "review" and new_state.get("raw_issues") is not None:
                    event_data["raw_issues_count"] = len(new_state["raw_issues"])
                elif name == "critic" and new_state.get("critic_result"):
                    cr = new_state["critic_result"]
                    event_data["validated"] = len(cr.get("validated", []))
                    event_data["rejected"] = len(cr.get("rejected", []))
                elif name == "report" and new_state.get("report"):
                    event_data["approved"] = new_state["report"].get("approved")
                    event_data["stats"] = new_state["report"].get("stats", {})
                emitter(f"{name}:done", event_data)

            return new_state
        except Exception as e:
            err_msg = f"{name} falhou: {type(e).__name__}: {str(e)}"
            if emitter:
                emitter(f"{name}:error", {"agent": name, "error": err_msg})
            return {**state, "error": err_msg}

    return node_fn


def _node_parse(state: ReviewState) -> ReviewState:
    parsed = parse_diff(state["diff"])
    return {
        **state,
        "parsed_diff": {
            "files": parsed.files_changed(),
            "additions": parsed.additions,
            "deletions": parsed.deletions,
            "hunks": len(parsed.hunks),
        }
    }


def _node_contextualize(state: ReviewState) -> ReviewState:
    vectorstore = load_vectorstore(state["collection_name"])
    context = contextualize_diff(
        diff=state["diff"],
        vectorstore=vectorstore,
        project_profile=state["project_profile"],
    )
    return {**state, "context": context}


def _node_review(state: ReviewState) -> ReviewState:
    issues = run_reviewer(
        diff=state["diff"],
        context_synthesis=state["context"]["synthesis"],
        project_profile=state["project_profile"],
        affected_symbols=state["context"].get("affected_symbols"),
        lang=state.get("lang", "en"),
    )
    return {**state, "raw_issues": issues}


def _node_critic(state: ReviewState) -> ReviewState:
    result = run_critic(
        issues=state["raw_issues"],
        diff=state["diff"],
        context_synthesis=state["context"]["synthesis"],
        project_profile=state["project_profile"],
        lang=state.get("lang", "en"),
    )
    return {**state, "critic_result": result}


def _node_report(state: ReviewState) -> ReviewState:
    report = run_reporter(
        validated_issues=state["critic_result"]["validated"],
        rejected_issues=state["critic_result"]["rejected"],
        diff_stats=state["parsed_diff"],
        project_profile=state["project_profile"],
        lang=state.get("lang", "en"),
    )
    return {**state, "report": report}


# ── Pipeline build ──────────────────────────────────────────────────────

def build_pipeline(emitter: Optional[EventEmitter] = None):
    graph = StateGraph(ReviewState)

    graph.add_node("parse", _make_node("parse", _node_parse, emitter))
    graph.add_node("contextualize", _make_node("contextualize", _node_contextualize, emitter))
    graph.add_node("review", _make_node("review", _node_review, emitter))
    graph.add_node("critic", _make_node("critic", _node_critic, emitter))
    graph.add_node("report", _make_node("report", _node_report, emitter))

    graph.set_entry_point("parse")
    graph.add_edge("parse", "contextualize")
    graph.add_edge("contextualize", "review")
    graph.add_edge("review", "critic")
    graph.add_edge("critic", "report")
    graph.add_edge("report", END)

    return graph.compile()


def run_review_pipeline(
    diff: str,
    collection_name: str,
    project_profile: dict,
    emitter: Optional[EventEmitter] = None,
    lang: str = "en",
) -> dict:
    """Roda o pipeline completo. emitter recebe eventos por agente."""
    pipeline = build_pipeline(emitter)

    initial_state: ReviewState = {
        "diff": diff,
        "collection_name": collection_name,
        "project_profile": project_profile,
        "lang": lang,
        "parsed_diff": None,
        "context": None,
        "raw_issues": None,
        "critic_result": None,
        "report": None,
        "error": None,
        "timings": {},
    }

    if emitter:
        emitter("pipeline:start", {})

    final = pipeline.invoke(initial_state)

    if emitter:
        emitter("pipeline:done", {"error": final.get("error")})

    if final.get("error"):
        return {"error": final["error"]}

    return {
        "report": final["report"],
        "context": {
            "files": final["context"]["context_files"],
            "queries": final["context"]["queries_used"],
            "affected_symbols": final["context"]["affected_symbols"],
            "synthesis": final["context"]["synthesis"],
        },
        "diff_stats": final["parsed_diff"],
        "timings": final["timings"],
        "raw_issues_count": len(final["raw_issues"] or []),
    }
