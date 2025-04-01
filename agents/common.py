## TODO: Use huggingface instead of langchain_ollama

# huggingface-cli download mistralai/Mistral-7B-Instruct-v0.2 --local-dir ./models/mistral-7b --local-dir-use-symlinks False
# from langchain.llms import HuggingFacePipeline
# from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

# model_path = "./models/mistral-7b"  # Adjust this to your model's path

# tokenizer = AutoTokenizer.from_pretrained(model_path)
# model = AutoModelForCausalLM.from_pretrained(
#     model_path,
#     device_map="auto",
#     torch_dtype="auto",
#     load_in_4bit=True  # recommended for large models
# )

# pipe = pipeline(
#     "text-generation",
#     model=model,
#     tokenizer=tokenizer,
#     do_sample=True,
#     max_new_tokens=512,
#     temperature=0.2,
# )
# llm = HuggingFacePipeline(pipeline=pipe)

from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

qwen = ChatOllama(model="qwen2.5")
deepseek = ChatGroq(model="deepseek-r1-distill-llama-70b")
llama = ChatGroq(model="llama-3.3-70b-versatile")

llms = {
    "orchestrator": deepseek,
    "source_code": llama,
    "history": qwen,
    "docs": qwen,
    "issues": qwen,
    "orchestrator": qwen,
    "aggregator": qwen,
    "discussion": qwen
    
}


from typing import List, Optional, Dict, Literal
from typing_extensions import Annotated, TypedDict

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


    # issues_url: Annotated[Optional[str], "URL to the issue tracker (e.g., GitHub issues)"]

    # documentation_url: Annotated[Optional[str], "URL to the project documentation"]

    # discussion_database: Annotated[Optional[str], "Connection string to the discussion database (e.g., PostgreSQL)"]

    # A mapping for the individual agents (one per information source) where each agent’s state includes its name, configuration parameters, and the last response it generated.
    # agent_states: Annotated[Dict[str, AgentState], "Mapping from agent identifiers to their state"]    
    # Example initialization might include agents like:
    # {
    #     "git_history": {"name": "git_history", "config": {...}, "last_response": None},
    #     "github_issues": {"name": "github_issues", "config": {...}, "last_response": None},
    #     "documentation": {"name": "documentation", "config": {...}, "last_response": None},
    #     "source_code": {"name": "source_code", "config": {...}, "last_response": None},
    #     "team_discussions": {"name": "team_discussions", "config": {...}, "last_response": None},
    # }

    # holds all project-specific data including the repository path 
    # project_metadata: Annotated[Dict[str, str], "Project-specific metadata like repository path, issue tracker URL, documentation URL, discussion database, etc."]
    # Example initialization for project_metadata might include:
    # {
    #     "repo_path": "/path/to/local/git/repository",
    #     "issues_url": "https://github.com/org/project/issues",
    #     "documentation_url": "https://project-docs.example.com",
    #     "discussion_database": "postgresql://user:pass@host/db",
    # }

 