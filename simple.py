import json
import uvicorn
from fastapi import FastAPI, WebSocket, Query
from fastapi.middleware.cors import CORSMiddleware

from typing import Optional
from fastapi.responses import HTMLResponse
from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama
from pydantic import BaseModel
from graph import db_app

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

from model import get_classes, get_packages
@app.get("/data/classes")
async def get_classes_data(
    package: Optional[str] = Query(None, description="Optional package name to filter classes"),
    # filter: Optional[str] = Query(None, description="Optional filter object")
):
    """
    Retrieve data from a JSON file with optional filtering.
    
    Query Parameters:
    - package (optional): Package name to filter UML classes
    """
    data = get_classes(package or None)
    return {"data": data}

@app.get("/data/packages")
async def get_packages_data(
    package: Optional[str] = Query(None, description="Optional package name to filter classes"),
    # filter: Optional[str] = Query(None, description="Optional filter object")
):
    """
    Retrieve data from a JSON file with optional filtering.
    
    Query Parameters:
    - package (optional): Package name to filter UML classes
    """
    data = get_packages(package or None)
    return {"data": data}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time AI chat."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            user_input = json.loads(data)

            # Send a "Thinking..." message to client
            await websocket.send_text(json.dumps({"status": "thinking"}))
            # Stream the AI response
            question = user_input.get("message", "")
            context  = user_input.get("context", "")
            print(f"User Query: {question} \n \n in the context of \n\n {context}")
            messages = db_app.invoke( { "messages": [("user", f"User Query: {question} \n \n in the context of \n\n {context}")] } )
            await websocket.send_text(json.dumps({"final_response": messages["messages"][-1].tool_calls[0]["args"]["final_answer"]}))
    except Exception as e:
        print("Error:")
        print(e)
        await websocket.send_text(json.dumps({"error": str(e)}))
    finally:
        print("Closing ")
        await websocket.close()


if __name__ == "__main__":
    uvicorn.run("simple:app", host="0.0.0.0", port=8000, reload=True)