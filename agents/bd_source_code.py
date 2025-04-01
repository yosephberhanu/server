from langgraph.prebuilt import create_react_agent
from typing import Literal
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import MessagesState, END
from langgraph.types import Command
from .helpers import make_system_prompt
from .common import llms, LaPSuMState

from sqlalchemy import create_engine, text

# ─────── Setup database engine ─────── #
engine = create_engine("sqlite:///uml.db")  # Or your actual DB

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

# ─────── Agent Schema-Aware Prompt ─────── #
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

You will receive natural language queries and respond using this schema. If applicable, generate SQL and call the tool.
"""

# ─────── Create LangGraph UML Agent ─────── #
uml_agent = create_react_agent(
    llms["source_code"],  # Reuses same LLM
    tools=[query_uml_database],
    prompt=make_system_prompt(SCHEMA_PROMPT),
)

# ─────── Node for LangGraph ─────── #
def source_code_node(state: LaPSuMState) -> Command[Literal["orchestrator"]]:
    if "source_code" in state.get("responded_agents", []):
        return Command(update=state, goto="orchestrator")

    query = state.get("rewritten_query") or state.get("user_query") or ""
    result = uml_agent.invoke({"messages": [HumanMessage(content=query)]})
    final_message = result["messages"][-1]

    state["agent_responses"]["source_code"] = final_message.content
    state["responded_agents"].append("source_code")
    result["messages"][-1] = AIMessage(content=final_message.content, name="source_code")

    return Command(update=state, goto="orchestrator")