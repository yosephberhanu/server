import os
import subprocess
from typing import Literal
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage

from langgraph.prebuilt import create_react_agent
from langgraph.graph import MessagesState, END, StateGraph, START
from langgraph.types import Command

def get_next_node(last_message: BaseMessage, goto: str):
    if "FINAL ANSWER" in last_message.content: # Any agent decided the work is done
        return END
    return goto

def make_system_prompt(suffix: str) -> str:
    return (
        "You are a helpful AI assistant, collaborating with other assistants."
        " Use the provided tools to answer the question."
        " If you have the final answer or deliverable, prefix your response with 'FINAL ANSWER' so the team knows to stop."
        " If you cannot finish, provide partial progress. Another assistant will continue."
        " Be direct, clear and concise. Respond witht the facts only"
        f"\n{suffix}"
    )
