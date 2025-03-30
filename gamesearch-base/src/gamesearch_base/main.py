import logging
import os
from typing import Any, Union

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_TTL = os.getenv("CACHE_TTL", 3000)

app = FastAPI(title="Gamesearch API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=CACHE_TTL,
)

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=0)

QUERY_TYPE_PROMPT = """You are a game search assistant. Your task is to:
1. First determine if the user is asking for:
    - A "hard query" which is searching for a game with specific fields like genre, name, release date (respond with exactly: "HARD_QUERY")
    - A "soft query" which is searching for a game that is similar to some summary or like other games (respond with exactly: "SOFT_QUERY")
2. Only respond with one of these two options, nothing else.
"""

EXTRACT_FIELDS_PROMPT = """Extract the following fields from the user's query to find a game:
- name: The specific name of the game they're asking about
- genre: Any genre mentioned in the query
- multiplayer: Whether they specifically asked about multiplayer functionality
- franchise: Any game franchise mentioned
- release_date: The release date of the game in UNIX time format

Return the results in JSON format with these fields. If a field isn't mentioned, set its value to null.
"""

load_dotenv()


class QueryState(BaseModel):
    query: str
    query_type: Union[str, None] = None
    extracted_fields: Union[dict[str, Any], None] = None


class GameQuery(BaseModel):
    query: str


class GameResponse(BaseModel):
    query_type: str
    extracted_fields: Union[dict[str, Any], None] = None
    results: Union[list[dict[str, Any]], None] = None


def classify_query(state: QueryState) -> QueryState:
    """Classify the query as either HARD_QUERY or SOFT_QUERY."""
    messages = [
        SystemMessage(content=QUERY_TYPE_PROMPT),
        HumanMessage(content=state.query),
    ]

    response = llm.invoke(messages)
    query_type = response.content.strip()

    return QueryState(query=state.query, query_type=query_type, extracted_fields=None)


def check_query_type(state: QueryState):
    """Gate function to check if query is type HARD_QUERY or type SOFT_QUERY."""
    return state.query_type


def extract_fields(state: QueryState):
    """Extract relevant fields  for HARD_QUERY types."""
    parser = JsonOutputParser()

    messages = [
        SystemMessage(content=EXTRACT_FIELDS_PROMPT),
        HumanMessage(content=state.query),
    ]

    response = llm.invoke(messages)

    try:
        extracted_json = parser.parse(response.content)
        return {
            "query": state.query,
            "query_type": state.query_type,
            "extracted_fields": extracted_json,
        }
    except Exception:
        raise


workflow = StateGraph(QueryState)

workflow.add_node("classify_query", classify_query)
workflow.add_node("extract_fields", extract_fields)

workflow.add_edge(START, "classify_query")
workflow.add_conditional_edges(
    "classify_query",
    check_query_type,
    {"HARD_QUERY": "extract_fields", "SOFT_QUERY": END},
)
workflow.add_edge("extract_fields", END)

chain = workflow.compile()


@app.get("/")
async def health_check():
    return {"status": "OK"}


@app.post("/search")
async def search(user_query: QueryState):
    result = chain.invoke(user_query)
    return result


def main():
    import uvicorn

    uvicorn.run("gamesearch_base.main:app", host="0.0.0.0", port=8001, reload=True)


if __name__ == "__main__":
    main()
