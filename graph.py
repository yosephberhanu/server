from typing import Literal, Any
from pydantic import BaseModel, Field

from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit

from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import ToolMessage, AIMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langgraph.prebuilt import ToolNode
from langgraph.graph import END, StateGraph, START

from common import DBState
from dotenv import load_dotenv
load_dotenv()

db = SQLDatabase.from_uri("sqlite:///uml-data.db")
# model="llama-3.3-70b-versatile"
#deepseek-r1-distill-llama-70b
def getLLM():
    return ChatGroq(model="llama-3.3-70b-versatile")
    # return ChatOllama(
    #     model="qwen2.5",
    #     # base_url="http://host.docker.internal:11434",
    # )

def create_tool_node_with_fallback(tools: list) -> RunnableWithFallbacks[Any, dict]:
    """
    Create a ToolNode with a fallback to handle errors and surface them to the agent.
    """
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )


def handle_tool_error(state: DBState) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


toolkit = SQLDatabaseToolkit(db=db, llm=getLLM())
tools = toolkit.get_tools()

list_tables_tool = next(tool for tool in tools if tool.name == "sql_db_list_tables")
get_schema_tool = next(tool for tool in tools if tool.name == "sql_db_schema")


@tool
def db_query_tool(query: str) -> str:
    """
    Execute a SQL query against the database and get back the result.
    If the query is not correct, an error message will be returned.
    If an error is returned, rewrite the query, check the query, and try again.
    """
    result = db.run_no_throw(query)
    if not result:
        return "Error: Query failed. Please rewrite your query and try again."
    return result


query_check_system = """You are a SQL expert with a strong attention to detail.
The SQL you are verifying will be run against a database that models UML components extracted from a software repository.

Check for these common issues:
- Using NOT IN with NULL values
...
"""
query_check_prompt = ChatPromptTemplate.from_messages(
    [("system", query_check_system), ("placeholder", "{messages}")]
)
query_check = query_check_prompt | getLLM().bind_tools(
    [db_query_tool], tool_choice="required"
)


# Add a node for the first tool call
def first_tool_call(state: DBState) -> dict[str, list[AIMessage]]:
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "sql_db_list_tables",
                        "args": {},
                        "id": "tool_abcd123",
                    }
                ],
            )
        ]
    }


def model_check_query(state: DBState) -> dict[str, list[AIMessage]]:
    """
    Use this tool to double-check if your query is correct before executing it.
    """
    return {"messages": [query_check.invoke({"messages": [state["messages"][-1]]})]}

# Add a node for a model to choose the relevant tables based on the question and available tables
model_get_schema = getLLM().bind_tools(
    [get_schema_tool]
)

# Describe a tool to represent the end state
class SubmitFinalAnswer(BaseModel):
    """Submit the final answer to the user based on the query results."""

    final_answer: str = Field(..., description="The final answer to the user")


# Add a node for a model to generate a query based on the question and schema
query_gen_system = """You are a SQL expert helping users explore a database that represents a software code repository as UML elements.
The database schema includes tables such as `uml_class`, `uml_property`, `uml_method`, and `uml_relationship`.

- Each `uml_class` represents a class in the codebase, with metadata like class name, package, and whether it's abstract or an interface.
- `uml_property` stores the fields or attributes of each class.
- `uml_method` stores the methods/functions and their visibility.
- `uml_relationship` describes associations like inheritance, composition, and method-level dependencies between classes.

You are helping users query this repository to answer questions like:
- Which classes were edited recently?
- Which classes have the most methods or properties?
- Which classes are connected via composition?
- What are the components of each package, classs and so on?

You must generate SQLite queries that answer these kinds of questions correctly and concisely.

DO NOT call any tool besides SubmitFinalAnswer to submit the final answer.
DO NOT respond with the sql query in the final answer always the response to the question.
Answer from the database and user input only (i.e., query and context)
...

"""

query_gen_prompt = ChatPromptTemplate.from_messages(
    [("system", query_gen_system), ("placeholder", "{messages}")]
)
query_gen = query_gen_prompt | getLLM().bind_tools(
    [SubmitFinalAnswer]
)


def query_gen_node(state: DBState):
    message = query_gen.invoke(state)

    # Sometimes, the LLM will hallucinate and call the wrong tool. We need to catch this and return an error message.
    tool_messages = []
    if message.tool_calls:
        for tc in message.tool_calls:
            if tc["name"] != "SubmitFinalAnswer":
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: The wrong tool was called: {tc['name']}. Please fix your mistakes. Remember to only call SubmitFinalAnswer to submit the final answer. Generated queries should be outputted WITHOUT a tool call.",
                        tool_call_id=tc["id"],
                    )
                )
    else:
        tool_messages = []
    return {"messages": [message] + tool_messages}

# Define a conditional edge to decide whether to continue or end the workflow
def should_continue(state: DBState) -> Literal[END, "correct_query", "query_gen"]:
    messages = state["messages"]
    last_message = messages[-1]
    # If there is a tool call, then we finish
    if getattr(last_message, "tool_calls", None):
        return END
    if last_message.content.startswith("Error:"):
        return "query_gen"
    else:
        return "correct_query"


def create_db_subgraph(workflow: StateGraph)-> StateGraph:
    
    workflow.add_node("first_tool_call", first_tool_call)

    # Add nodes for the first two tools
    workflow.add_node("list_tables_tool", create_tool_node_with_fallback([list_tables_tool]))
    workflow.add_node("get_schema_tool", create_tool_node_with_fallback([get_schema_tool]))


    workflow.add_node("model_get_schema", lambda state: { "messages": [model_get_schema.invoke(state["messages"])], },)

    workflow.add_node("query_gen", query_gen_node)

    # Add a node for the model to check the query before executing it
    workflow.add_node("correct_query", model_check_query)

    # Add node for executing the query
    workflow.add_node("execute_query", create_tool_node_with_fallback([db_query_tool]))


    # Specify the edges between the nodes
    workflow.add_edge(START, "first_tool_call")
    workflow.add_edge("first_tool_call", "list_tables_tool")
    workflow.add_edge("list_tables_tool", "model_get_schema")
    workflow.add_edge("model_get_schema", "get_schema_tool")
    workflow.add_edge("get_schema_tool", "query_gen")
    workflow.add_conditional_edges(
        "query_gen",
        should_continue,
    )
    workflow.add_edge("correct_query", "execute_query")
    workflow.add_edge("execute_query", "query_gen")
    
    return workflow

# Define a new graph
workflow = StateGraph(DBState)

workflow = create_db_subgraph(workflow)

# Compile the workflow into a runnable
db_app = workflow.compile()
