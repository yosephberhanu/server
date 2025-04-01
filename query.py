#!/usr/bin/env python
# coding: utf-8

import os
import json
import subprocess
import logging

from dotenv import load_dotenv
from typing import List, Optional, Dict, Literal
from sqlalchemy import create_engine, text
from typing_extensions import Annotated, TypedDict

from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from langgraph.types import Command
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage

# ## Shared and Utilities
load_dotenv()
# ### Updated State Model with Iteration Fields and Full Diagram Context

class LaPSuMState(TypedDict):
    # User query and orchestration context
    user_query: Annotated[Optional[str], "Original user query"]
    rewritten_query: Annotated[Optional[str], "Rewritten version of the query by the orchestrator"]

    # Source-related metadata
    repo_path: Annotated[Optional[str], "Path to the local git repository"]
    diagram: Annotated[Optional[str], "Current UML diagram in JSON format"]

    # Agent coordination
    required_agents: Annotated[List[Literal["history", "source_code"]], "List of agents needed to process the query"]
    responded_agents: Annotated[List[Literal["history", "source_code"]], "List of agents that have already responded"]

    # Optional: store intermediate responses for aggregation
    agent_responses: Annotated[Dict[str, str], "Responses from each agent keyed by agent name"]

    # Iteration control
    iteration_count: Annotated[int, "Current iteration count"]
    max_iterations: Annotated[int, "Max iterations allowed"]

# ### LLM Initialization

qwen = ChatOllama(model="qwen2.5")
deepseek = ChatGroq(model="deepseek-r1-distill-llama-70b")
llama = ChatGroq(model="llama-3.3-70b-versatile")

llms = {
    "orchestrator": qwen,  # using qwen for orchestration in this example
    "source_code": llama,
    "history": qwen,
    "docs": qwen,
    "issues": qwen,
    "aggregator": qwen,
    "discussion": qwen
}

# ## Agents and Tools

# ### History Agent

@tool
def run_git_command(repo_path: str, command: str) -> str:
    """
    Run an arbitrary git command in the given repository path.
    """
    if not os.path.exists(os.path.join(repo_path, ".git")):
        return f"Error: {repo_path} is not a valid Git repository."
    try:
        result = subprocess.run(
            ["git"] + command.strip().split(),
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error running git command: {e.stderr}"

history_agent = create_react_agent(
    llms['history'],
    tools=[run_git_command],
    prompt="""
        You are a version control analysis assistant collaborating with a software researcher.
        Your role is to analyze the Git history of a local project using only the tools provided.
        Constraints:
        - Do not rely on prior knowledge or assumptions.
        - All information must be derived from Git history via the provided tools.
        - Begin your final answer with 'FINAL ANSWER'.
        Available Tool:
        - run_git_command(command): Run any git command against the local repo.
        Always refer to the repo using the path provided in 'repo_path'.
    """
)

def history_node(state: LaPSuMState) -> Command[Literal["orchestrator"]]:
    if "history" in state.get("responded_agents", []):
        return Command(update=state, goto="orchestrator")
    
    # Build the query and append the full diagram data
    base_query = state.get("rewritten_query") or state.get("user_query") or ""
    diagram_context = "\n\nDiagram Data:\n" + state["diagram"] if state.get("diagram") else ""
    full_query = base_query + diagram_context

    repo_path = state.get("repo_path")
    result = history_agent.invoke({
        "messages": [HumanMessage(content=full_query)],
        "repo_path": repo_path,
    })

    final_message = result["messages"][-1]
    state["agent_responses"]["history"] = final_message.content
    state["responded_agents"].append("history")
    result["messages"][-1] = AIMessage(content=final_message.content, name="history")
    return Command(update=state, goto="orchestrator")

# ### Source Code Agent

engine = create_engine("sqlite:///uml-data.db")

@tool
def query_uml_database(sql: str) -> str:
    """Run a SQL query against the UML database. Return results as string."""
    with engine.connect() as conn:
        try:
            result = conn.execute(text(sql))
            rows = [dict(row) for row in result]
            return str(rows)
        except Exception as e:
            return f"SQL Error: {e}"

SCHEMA_PROMPT = """
You are a software architecture assistant specialized in analyzing Java projects via UML databases.
You can use the following tool:
- query_uml_database(sql): Run SQL queries on the UML database.
The UML schema consists of:
- uml_class(id, name, package_name, is_abstract, is_interface, annotations, files, dom_id, display_name, summary, comments)
- uml_property(id, class_id, name, data_type, visibility, is_static, is_final, source_line, dom_id, annotations, comments, summary)
- uml_method(id, class_id, name, dom_id, return_type, visibility, is_static, is_abstract, starting_line, ending_line, source, annotations, display_name, comments, summary)
- uml_parameter(id, method_id, name, dom_id, data_type, display_name, annotations, comments, summary)
- uml_relationship(id, name, dom_id, source, target, type)
- uml_package(id, name, parent)
When generating SQL queries, consider the full diagram data provided.
"""

uml_agent = create_react_agent(
    llms["source_code"],
    tools=[query_uml_database],
    prompt=SCHEMA_PROMPT,
)

def source_code_node(state: LaPSuMState) -> Command[Literal["orchestrator"]]:
    if "source_code" in state.get("responded_agents", []):
        return Command(update=state, goto="orchestrator")
    
    # Build query with full diagram data included
    base_query = state.get("rewritten_query") or state.get("user_query") or ""
    diagram_context = "\n\nDiagram Data:\n" + state["diagram"] if state.get("diagram") else ""
    full_query = base_query + diagram_context

    result = uml_agent.invoke({"messages": [HumanMessage(content=full_query)]})
    final_message = result["messages"][-1]
    state["agent_responses"]["source_code"] = final_message.content
    state["responded_agents"].append("source_code")
    result["messages"][-1] = AIMessage(content=final_message.content, name="source_code")
    return Command(update=state, goto="orchestrator")

# ### Aggregator Agent

aggregator_agent = create_react_agent(
    llms['aggregator'],
    tools=[],
    prompt="""
        You are an aggregation assistant.
        Your role is to combine and summarize responses provided by your colleague agents.
        Only use the content already provided in the current conversation state.
        Rules:
        - DO NOT infer or invent any information.
        - DO NOT ask the user follow-up questions.
        - DO NOT make assumptions or guesses.
        - If the information is incomplete or missing, say so directly.
        - If the answer is complete, prefix your final output with: 'FINAL ANSWER'.
        Be sure to consider the full diagram data provided.
    """
)

def aggregator_node(state: LaPSuMState) -> Command[Literal["orchestrator", END]]:
    # If any previous response already has a final answer, end the workflow.
    for response in state.get("agent_responses", {}).values():
        if "FINAL ANSWER" in response:
            return Command(update=state, goto=END)
    
    # Build conversation context including the full diagram data.
    messages = [HumanMessage(content=state["rewritten_query"] or state["user_query"])]
    if state.get("diagram"):
        messages.insert(0, HumanMessage(content="Full Diagram Data:\n" + state["diagram"], name="diagram"))
    for agent_name in state.get("required_agents", []):
        if agent_name in state.get("agent_responses", {}):
            messages.append(AIMessage(
                content=state["agent_responses"][agent_name],
                name=agent_name
            ))
    
    result = aggregator_agent.invoke({"messages": messages})
    final_message = result["messages"][-1]
    goto = END if "FINAL ANSWER" in final_message.content else "orchestrator"
    state["agent_responses"]["aggregator"] = final_message.content
    return Command(update=state, goto=goto)

# ### Orchestrator Node

def orchestrator_node(state: LaPSuMState) -> Command[Literal["history", "source_code", "aggregator"]]:
    # Check if maximum iterations have been reached.
    if state.get("iteration_count", 0) >= state.get("max_iterations", 10):
        return Command(update=state, goto="aggregator")
    
    # Increment iteration counter.
    state["iteration_count"] = state.get("iteration_count", 0) + 1
    
    # Retrieve any previous aggregator attempt.
    previous_attempt = state.get("agent_responses", {}).get("aggregator")
    additional_context = f"Previous attempt: {previous_attempt}\n" if previous_attempt else ""
    
    # Include the full diagram data in the orchestrator prompt.
    diagram_context = "Full Diagram Data:\n" + state["diagram"] + "\n" if state.get("diagram") else ""
    
    # If all required agents have responded, trigger aggregation.
    if state.get("user_query") is None or set(state.get("required_agents", [])) == set(state.get("responded_agents", [])):
        return Command(update=state, goto="aggregator")
    
    # Use the orchestrator LLM to rewrite the query and plan next steps.
    task_analysis = llms['orchestrator'].invoke([
        HumanMessage(
            content=(
                "You are a query orchestrator and planning assistant in a multi-agent system that helps answer software-related questions.\n"
                "Agents available:\n"
                "- 'source_code': understands code logic, structure, classes, relationships.\n"
                "- 'history': analyzes git history, commit changes, authorship, file evolution.\n\n"
                f"User Query: {state['user_query']}\n"
                f"{additional_context}"
                f"{diagram_context}\n"
                "Respond in JSON format like this:\n"
                "{\n"
                '  "rewritten_query": "....",\n'
                '  "required_agents": ["source_code", "history"],\n'
                '  "plan": "Step 1: ..." \n'
                "}"
            )
        )
    ])
    
    try:
        parsed_response = json.loads(task_analysis.content)
    except json.JSONDecodeError as e:
        logging.error("JSON decode error in orchestrator: %s", e)
        return Command(update=state, goto="aggregator")
    
    state["rewritten_query"] = parsed_response.get("rewritten_query", state["user_query"])
    state["required_agents"] = parsed_response.get("required_agents", [])
    # Reset responses for the new iteration while preserving iteration_count and diagram data.
    state["responded_agents"] = []
    state["agent_responses"] = {}
    
    plan = parsed_response.get("plan")
    if plan:
        plan_message = HumanMessage(content=f"Plan:\n{plan}", name="planner")
        state["messages"] = [plan_message] + state.get("messages", [])
    
    if not state["required_agents"]:
        return Command(update=state, goto="aggregator")
    
    next_agent = state["required_agents"][0]
    return Command(update=state, goto=next_agent)

# ## Graph Setup

workflow = StateGraph(LaPSuMState)
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("aggregator", aggregator_node)
workflow.add_node("history", history_node)
workflow.add_node("source_code", source_code_node)

workflow.set_entry_point("orchestrator")
workflow.add_edge("source_code", "orchestrator")
workflow.add_edge("history", "orchestrator")
workflow.add_edge("aggregator", "orchestrator")
workflow.add_edge("aggregator", END)

graph = workflow.compile()

# ### Visualize (Optional)

from IPython.display import Image, display
try:
    display(Image(graph.get_graph().draw_mermaid_png()))
except Exception:
    pass

# ## Run Queries with Iteration and Full Diagram Data

initial_state = {
    "user_query": "Filter out classes with less than 5 methods",
    "rewritten_query": None,
    "repo_path": "/Users/yoseph/Work/Personal/keycloak",
    "diagram": '{"classes": [{"name": "User", "methods": ["login", "logout", "register", "update", "delete"]}, {"name": "Session", "methods": ["start", "end"]}]}',
    "required_agents": [],
    "responded_agents": [],
    "agent_responses": {},
    "iteration_count": 0,
    "max_iterations": 3,
}

events = graph.stream(initial_state, {"recursion_limit": 100})

for event in events:
    first_key = next(iter(event))
    response = event[first_key]
    if "agent_responses" in response and response["agent_responses"].get("aggregator"):
        print(f"{first_key}: {response['agent_responses']['aggregator']}")
    else:
        print(f"{first_key}: (intermediate state, iteration {response.get('iteration_count', '?')})")
    print('----')