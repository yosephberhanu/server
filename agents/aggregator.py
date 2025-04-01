from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage

from langgraph.prebuilt import create_react_agent
from langgraph.graph import MessagesState, END
from langgraph.types import Command
from langchain_core.tools import tool
from .helpers import  make_system_prompt

from .common import llms, LaPSuMState

aggregator_agent = create_react_agent(
    llms['aggregator'],
    tools=[],
    prompt=make_system_prompt(
        """
        You are an aggregation assistant.

        Your role is to combine and summarize responses provided by your colleague agents.
        Only use the content already provided in the current conversation state.

        Rules:
        - DO NOT infer or invent any information.
        - DO NOT ask the user follow-up questions.
        - DO NOT make assumptions or guesses.
        - If the information is incomplete or missing, say so directly.
        - If the answer is complete, prefix your final output with: 'FINAL ANSWER'.

        You are expected to clearly and accurately synthesize the responses to help the user.
        """
    ),
)
def aggregator_node(state: LaPSuMState) -> Command[Literal[END]]:
    # Skip if already finalized
    for response in state.get("agent_responses", {}).values():
        if "FINAL ANSWER" in response:
            return Command(update=state, goto=END)

    # Build conversation context from agent responses
    messages = [
        HumanMessage(content=state["rewritten_query"] or state["user_query"]),
    ]
    for agent_name in state.get("required_agents", []):
        if agent_name in state.get("agent_responses", {}):
            messages.append(AIMessage(
                content=state["agent_responses"][agent_name],
                name=agent_name
            ))

    # Invoke the aggregator agent
    result = aggregator_agent.invoke({"messages": messages})

    final_message = result["messages"][-1]

    # If it contains 'FINAL ANSWER', the workflow should end
    goto = END if "FINAL ANSWER" in final_message.content else END  # optionally re-orchestrate if not final

    # Save the aggregated message
    return Command(update={
        "agent_responses": {
            **state.get("agent_responses", {}),
            "aggregator": final_message.content
        }
    }, goto=goto)