import os
import subprocess
from typing import Literal
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage

from langgraph.prebuilt import create_react_agent
from langgraph.graph import MessagesState, END
from langgraph.types import Command
from .helpers import  make_system_prompt
from .common import llms, LaPSuMState

@tool
def run_git_command(repo_path: str, command: str) -> str:
    """
    Run an arbitrary git command in the given repository path.
    
    Args:
        repo_path: Path to the Git repository.
        command: The git command to run (without the leading 'git'), e.g., 'log -10 --pretty=format:%h'
    
    Returns:
        The output of the command or an error message.
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
    prompt=make_system_prompt("""
        You are a version control analysis assistant collaborating with a software researcher.
        
        Your role is to analyze the Git history of a local project using only the tools provided.

        Constraints:
        - Do not rely on prior knowledge or assumptions.
        - All information must be derived from Git history via the provided tools.
        - Begin your final answer with 'FINAL ANSWER'.

        Available Tool:
        - run_git_command(command): Run any git command against the local repo.

        Always refer to the repo using the path provided in 'repo_path'.
    """)
)
def history_node(state: LaPSuMState) -> Command[Literal["orchestrator"]]:
    if "history" in state.get("responded_agents", []):
        return Command(update=state, goto="orchestrator")

    query = state.get("rewritten_query") or state.get("user_query") or ""
    repo_path = state.get("repo_path")

    # Pass the rewritten query and repo_path to the agent
    result = history_agent.invoke({
        "messages": [HumanMessage(content=query)],
        "repo_path": repo_path,
    })

    final_message = result["messages"][-1]
    state["agent_responses"]["history"] = final_message.content
    state["responded_agents"].append("history")

    # Tag the message so it's traceable in logs or UI
    result["messages"][-1] = AIMessage(content=final_message.content, name="history")

    return Command(update=state, goto="orchestrator")