"""Production conversation graph for the real-estate chatbot."""

from langgraph.graph import END, START, StateGraph
from app.agents.free_chat.nodes.load_memory import load_memory_node
from app.agents.free_chat.nodes.level1_extraction import level1_extraction_node
from app.agents.free_chat.nodes.classify_action import classify_action_node
from app.agents.free_chat.nodes.extract_constraints import extract_constraints_node
from app.agents.free_chat.nodes.modify_search_context import modify_search_context_node
from app.agents.free_chat.nodes.reset_search_context import reset_search_context_node
from app.agents.free_chat.nodes.needs_clarification import needs_clarification_node
from app.agents.free_chat.nodes.level3_query_planner import level3_query_planner_node
from app.agents.free_chat.nodes.execute_query import execute_query_node
from app.agents.free_chat.nodes.level4_response import level4_response_node
from app.agents.free_chat.nodes.update_memory import update_memory_node
from app.agents.free_chat.state import AgentState


def _route_action(state: AgentState) -> str:
    action = state.get("conversation_action")
    if action == "new_search":
        return "reset_search_context"
    if action == "modify_search":
        return "modify_search_context"
    if action == "general_chat":
        # General real-estate chat needs no extraction, clarification, planning,
        # or DB query — answer directly in the response node.
        return "general_chat"
    return "extract_constraints"


def _route_clarification(state: AgentState) -> str:
    return "level4_response" if state.get("clarification_needed") else "level3_query_planner"


def build_graph():
    workflow = StateGraph(AgentState)
    nodes = {
        "load_memory": load_memory_node,
        "level1_extraction": level1_extraction_node,
        "classify_action": classify_action_node,
        "extract_constraints": extract_constraints_node,
        "modify_search_context": modify_search_context_node,
        "reset_search_context": reset_search_context_node,
        "needs_clarification": needs_clarification_node,
        "level3_query_planner": level3_query_planner_node,
        "execute_query": execute_query_node,
        "level4_response": level4_response_node,
        "update_memory": update_memory_node,
    }
    for name, node in nodes.items():
        workflow.add_node(name, node)

    workflow.add_edge(START, "load_memory")
    workflow.add_edge("load_memory", "level1_extraction")
    workflow.add_edge("level1_extraction", "classify_action")
    workflow.add_conditional_edges("classify_action", _route_action, {
        "reset_search_context": "reset_search_context",
        "modify_search_context": "modify_search_context",
        "extract_constraints": "extract_constraints",
        "general_chat": "level4_response",
    })
    workflow.add_edge("reset_search_context", "needs_clarification")
    workflow.add_edge("modify_search_context", "needs_clarification")
    workflow.add_edge("extract_constraints", "needs_clarification")
    workflow.add_conditional_edges("needs_clarification", _route_clarification, {
        "level4_response": "level4_response",
        "level3_query_planner": "level3_query_planner",
    })
    workflow.add_edge("level3_query_planner", "execute_query")
    workflow.add_edge("execute_query", "level4_response")
    workflow.add_edge("level4_response", "update_memory")
    workflow.add_edge("update_memory", END)
    return workflow.compile()


free_chat_graph = build_graph()
