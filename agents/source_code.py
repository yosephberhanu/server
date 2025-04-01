from .tools.model import SourceTools
from langgraph.prebuilt import create_react_agent
from typing import Literal
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage

from langgraph.prebuilt import create_react_agent
from langgraph.graph import MessagesState, END
from langgraph.types import Command
from .helpers import  make_system_prompt
from .common import llms, LaPSuMState

st = SourceTools()

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
    """Tool: (Unimplemented) Return raw source for a given file"""
    return st.get_source(file_name)


source_code_agent = create_react_agent(
    llms['source_code'],
    tools=[get_classes, get_packages, get_source],
    prompt=make_system_prompt(""" 
        You are a software architecture assistant that analyzes Java source code and UML diagrams.

        You can use the following tools:
        - get_classes(package_name): View all classes and relationships in a package.
        - get_packages(package_name): Explore package structure and relationships.
        - get_source(file_name): View the full source code of a given file.

        Your job is to interpret software design, uncover architectural patterns, and help explain class and package relationships
        based on the query you receive.
    """),
)

def source_code_node(state: LaPSuMState) -> Command[Literal["orchestrator"]]:
    # Skip processing if already responded
    if "source_code" in state.get("responded_agents", []):
        return Command(update=state, goto="orchestrator")

    query = state.get("rewritten_query") or state.get("user_query") or ""

    result = source_code_agent.invoke({"messages": [HumanMessage(content=query)]})

    # Extract the latest message
    final_message = result["messages"][-1]
    state["agent_responses"]["source_code"] = final_message.content
    state["responded_agents"].append("source_code")

    # Optionally tag the message
    result["messages"][-1] = AIMessage(content=final_message.content, name="source_code")

    return Command(update=state, goto="orchestrator")