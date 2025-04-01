from dotenv import load_dotenv
load_dotenv()

from graph import db_app


messages = db_app.invoke(
    {
        "messages": [("user", "Is the class org.keycloak.transaction.JtaTransactionWrapper abstract ?")]
    }
)
json_str = messages["messages"][-1].tool_calls[0]["args"]["final_answer"]
print(json_str)
# print(messages)
# messages: Annotated[list[AnyMessage], add_messages]
# context: Annotated[Optional[str], "Context infomration about user query"]
# repo_path: Annotated[Optional[str], "Path to the local git repository"]
# code_response: Annotated[list[AnyMessage], add_messages]
# iteration_count: Annotated[Optional[int], "Current iteration count"]
# max_iterations: Annotated[Optional[int], "Max iterations allowed"]