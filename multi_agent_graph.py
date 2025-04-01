import json
from typing import Literal
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.types import MessagesState, Command
from langgraph.prebuilt import create_react_agent

from model import SourceTools
from helpers import make_system_prompt, get_next_node
from common import llms

# === Instantiate the backend ===
st = SourceTools()

# === Tool Definitions ===
@tool
def get_classes(package_name: str):
    """Tool: Return all classes and class-level relationships in a given package"""
    return st.get_classes(package_name)

@tool
def get_packages(package_name: str):
    """Tool: Return a package, its subpackages, classes, and package-level relationships"""
    return st.get_packages(package_name)

@tool
def get_source(file_name: str):
    """Tool: Return raw source code for a given file"""
    return st.get_source(file_name)

# === Source Code Agent ===
source_code_agent = create_react_agent(
    llms["source_code"],
    tools=[get_classes, get_packages, get_source],
    prompt=make_system_prompt("""
You are a software architecture assistant that analyzes source code and UML diagrams.
You have access to the following tools:

- get_classes(package_name): View all classes and relationships in a package.
- get_packages(package_name): Explore package structure and relationships.
- get_source(file_name): View source code of a given file.

Use these tools to reason through software structure, class composition, package dependencies, and provide insights or explanations to the user. Always explain your steps before providing the FINAL ANSWER.
"""),
)

# === Helper: Agent Router ===
def route_after_agent(agent_name: str, state: MessagesState, result_messages: list) -> Command:
    responded = set(state.get("responded_agents", []))
    required = set(state.get("required_agents", []))
    responded.add(agent_name)

    update = {
        "messages": result_messages,
        "responded_agents": list(responded)
    }

    if responded == required:
        return Command(update=update, goto="aggregator")
    else:
        for agent in state["required_agents"]:
            if agent not in responded:
                return Command(update=update, goto=agent)

    return Command(update=update, goto="aggregator")

# === Agent Node: Source Code ===
def source_code_node(state: MessagesState) -> Command[Literal["aggregator"]]:
    if any("FINAL ANSWER" in msg.content for msg in state["messages"]):
        return Command(update=state, goto="aggregator")

    result = source_code_agent.invoke(state)
    result["messages"][-1] = HumanMessage(content=result["messages"][-1].content, name="source_code")
    return route_after_agent("source_code", state, result["messages"])

# === Orchestrator Node ===
def orchestrator_node(state: MessagesState) -> Command[Literal["source_code", "aggregator"]]:
    if state.get("user_query") is None or set(state.get("required_agents", [])) == set(state.get("responded_agents", [])):
        return Command(update=state, goto="aggregator")

    task_analysis = llms["planner"].invoke([
        HumanMessage(content=(
            "You are a query orchestrator and planning assistant in a multi-agent system that helps answer software-related questions.\n"
            "You have access to these agents:\n"
            "- 'source_code': understands code logic, structure, classes, relationships.\n"
            "- 'history': analyzes git history, commit changes, authorship, file evolution.\n\n"
            "Your task is to:\n"
            "1. Rewrite the user's query to make it clearer.\n"
            "2. Create a step-by-step plan using available agents.\n"
            "3. Identify which agents are required.\n\n"
            f"User Query: {state['user_query']}\n\n"
            "Respond in JSON format like this:\n"
            "{\n"
            '  "rewritten_query": "...",\n'
            '  "required_agents": ["source_code"],\n'
            '  "plan": "1. Use get_classes to find method location.\\n2. Use get_source.\\n3. ..."\n'
            "}"
        ))
    ])
    parsed_response = json.loads(task_analysis.content)

    state["rewritten_query"] = parsed_response.get("rewritten_query", state["user_query"])
    state["required_agents"] = parsed_response.get("required_agents", [])
    state["responded_agents"] = []
    state["agent_responses"] = {}

    plan = parsed_response.get("plan")
    if plan:
        plan_message = HumanMessage(content=f"Plan:\n{plan}", name="planner")
        state["messages"] = [plan_message] + state.get("messages", [])

    if not state["required_agents"]:
        return Command(update=state, goto="aggregator")

    return Command(update=state, goto=state["required_agents"][0])

# === Aggregator Node (Final) ===
def aggregator_node(state: MessagesState) -> Command[Literal[END]]:
    return Command(update=state, goto=END)

# === Build LangGraph ===
builder = StateGraph(MessagesState)
builder.add_node("orchestrator", orchestrator_node)
builder.add_node("source_code", source_code_node)
builder.add_node("aggregator", aggregator_node)

builder.set_entry_point("orchestrator")
builder.set_finish_point("aggregator")

graph = builder.compile()
graph_app = graph.app
