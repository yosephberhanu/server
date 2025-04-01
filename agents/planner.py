import json
from typing import Literal
from langchain_core.messages import  HumanMessage
from langgraph.types import Command
from .common import llms, LaPSuMState

def orchestrator_node(state: LaPSuMState) -> Command[Literal["history", "source_code", "aggregator"]]:
    # Skip orchestration if aggregation is already triggered or all agents have responded
    if state.get("user_query") is None or set(state.get("required_agents", [])) == set(state.get("responded_agents", [])):
        return Command(update=state, goto="aggregator")

    # Run LLM-based query rewriting and planning
    task_analysis = llms['orchestrator'].invoke([
        HumanMessage(
            content=(
                "You are a query orchestrator and planning assistant in a multi-agent system that helps answer software-related questions.\n"
                "You have access to these agents:\n"
                "- 'source_code': understands code logic, structure, classes, relationships.\n"
                "- 'history': analyzes git history, commit changes, authorship, file evolution.\n\n"
                "Your task is to:\n"
                "1. Rewrite the user's query to make it clearer and better suited for agents.\n"
                "2. Create a step-by-step plan using available tools/agents.\n"
                "3. Identify which agents are required to complete the plan.\n\n"
                f"User Query: {state['user_query']}\n\n"
                "Respond in JSON format like this:\n"
                "{\n"
                '  "rewritten_query": "....",\n'
                '  "required_agents": ["source_code", "history"],\n'
                '  "plan": "1. Use get_classes to find method location.\\n2. Use get_source to extract code.\\n3. Use history agent to trace the commit."\n'
                "}"
            )
        )
    ])

    parsed_response = json.loads(task_analysis.content)

    # Extract orchestration fields
    state["rewritten_query"] = parsed_response.get("rewritten_query", state["user_query"])
    state["required_agents"] = parsed_response.get("required_agents", [])
    state["responded_agents"] = []
    state["agent_responses"] = {}

    # Optional: add the plan to message history so agents can reason over it
    plan = parsed_response.get("plan")
    if plan:
        plan_message = HumanMessage(content=f"Plan:\n{plan}", name="planner")
        state["messages"] = [plan_message] + state.get("messages", [])

    # If no agents are required, go to aggregator
    if not state["required_agents"]:
        return Command(update=state, goto="aggregator")

    # Route to first required agent
    next_agent = state["required_agents"][0]
    return Command(update=state, goto=next_agent)

# def orchestrator_node(state: MessagesState) -> Command[Literal["history", END]]:
#     for msg in state["messages"]:
#         if "FINAL ANSWER" in msg.content:
#             return Command(update=state, goto=END)

#     last_message = state["messages"][-1].content
#     task_analysis = llm.invoke([
#         HumanMessage(
#             content=(
#                 "You are working with a source code and history agents which you can ask for help."
#                 "Update the question in to a form best answerable by a combination of these tools."
#                 "Classify the following user request into one of three categories:\n"
#                 "1. 'history' -> If the request is involves the code's history (e.g., git).\n"
#                 "2. 'source_code' -> If the request is involves the source code it self.\n"
#                 "3. 'final' -> If the request does not need further action.\n\n"
#                 f"User Request: {last_message}\n\n"
#                 "Respond with only the agent name that could help with the task:  e.g., 'source_code', 'history', or 'final'."
#             )
#         )
#     ])
    
#     response_text = task_analysis.content.strip().lower()
#     if response_text == "history":
#         return Command(update=state, goto="history")
#     else:
#         return Command(update=state, goto=END)

