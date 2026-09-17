from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph


class WorkflowState(TypedDict, total=False):
    user_id: str
    query: dict[str, object]
    jobs: list[dict[str, object]]
    scored_jobs: list[dict[str, object]]
    documents: list[dict[str, str]]
    approval_required: bool
    error: str


class JobDiscoveryAgent:
    async def run(self, state: WorkflowState) -> WorkflowState:
        return {**state, "jobs": state.get("jobs", [])}


class JobScoringAgent:
    async def run(self, state: WorkflowState) -> WorkflowState:
        return {**state, "scored_jobs": state.get("jobs", [])}


class ResumeTailorAgent:
    async def run(self, state: WorkflowState) -> WorkflowState:
        return {**state, "documents": state.get("documents", [])}


class CoverLetterAgent(ResumeTailorAgent):
    pass


class QuestionAnswerAgent(ResumeTailorAgent):
    pass


class ApplicationAgent:
    async def run(self, state: WorkflowState) -> WorkflowState:
        return {**state, "approval_required": True}


class ReportingAgent:
    async def run(self, state: WorkflowState) -> WorkflowState:
        return state


def build_application_graph() -> object:
    discovery = JobDiscoveryAgent()
    scoring = JobScoringAgent()
    tailoring = ResumeTailorAgent()
    application = ApplicationAgent()
    reporting = ReportingAgent()
    graph = StateGraph(WorkflowState)
    graph.add_node("discover", discovery.run)
    graph.add_node("score", scoring.run)
    graph.add_node("tailor", tailoring.run)
    graph.add_node("apply", application.run)
    graph.add_node("report", reporting.run)
    graph.set_entry_point("discover")
    graph.add_edge("discover", "score")
    graph.add_edge("score", "tailor")
    graph.add_edge("tailor", "apply")
    graph.add_edge("apply", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=MemorySaver())
