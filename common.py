from typing import Any
from typing import Annotated, Literal, List, Optional, Dict, Literal

from typing_extensions import TypedDict
from langgraph.graph.message import AnyMessage, add_messages

# Define the state for the agent
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_query: Annotated[Optional[str], "User query"]
    context: Annotated[Optional[str], "Context infomration about user query"]
    repo_path: Annotated[Optional[str], "Path to the local git repository"]
    code_response: Annotated[list[AnyMessage], add_messages]
    iteration_count: Annotated[Optional[int], "Current iteration count"]
    max_iterations: Annotated[Optional[int], "Max iterations allowed"]

class DBState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    # user_query: Annotated[Optional[str], "User query"]

class UMLState(TypedDict):
    user_query: Annotated[list[AnyMessage], add_messages]