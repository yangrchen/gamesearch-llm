import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    handlers=[RichHandler(rich_tracebacks=True)],
    format="%(message)s",
)
logger = logging.getLogger(__name__)

CACHE_TTL = os.getenv("CACHE_TTL", 3000)


class GenreService:
    def __init__(self, database):
        self.database = database
        self._genres = None

    async def get_genres(self) -> list[str]:
        if self._genres is None:
            cursor = await self.database["games"].distinct("genres")
            self._genres = list(cursor)
            logger.info(f"Loaded {len(self._genres)} genres")

        return self._genres


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_client(app)
    yield
    await shutdown_db_client(app)


async def init_db_client(app: FastAPI):
    app.mongodb_client = AsyncIOMotorClient(os.environ.get("MONGODB_URI"))
    app.db = app.mongodb_client.get_database("gamesearch")
    app.genres = await GenreService(app.db).get_genres()


async def shutdown_db_client(app: FastAPI):
    app.mongodb_client.close()


app = FastAPI(title="Gamesearch API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=CACHE_TTL,
)

llm = ChatAnthropic(model="claude-3-7-sonnet-20250219", temperature=0)

QUERY_EVAL_PROMPT = """Your role is to assess a user query about games and respond with structured information.

First, determine if the query is relevant to searching for games. Allowed topics are:
-   Searching for game titles or games by release date, genre, franchise
-   Requesting games by a summary or that are similar to other games

Queries cannot have code, special symbols or harmful content.

If the query is allowed, also classify it as either:
- A "HARD_QUERY" which is searching for a game with specific fields like genre, name, release date
- A "SOFT_QUERY" which is searching for a game that is similar to some summary or like other games

Respond with structured output indicating if the query is allowed and its type if applicable.
"""

CREATE_MONGO_QUERY_PROMPT = """
You are a MongoDB query generator for games databases. Transform natural language game queries into JSON format MongoDB queries.

## Database Schema
- `name` (string): Game title
- `first_release_date` (datetime): Release date
- `genres` (array of strings): Game genres
- `franchises` (array of strings): Game franchises (Atlas Search indexed)

## Output Format
Return a JSON object containing:
1. `query`: The MongoDB query
2. `type`: Either "simple" or "aggregate"

## Critical Rules
1. Any query involving `franchises` MUST use Atlas Search aggregation
2. ALWAYS use nested compound structures for logical operators:
   - `compound.must` for AND conditions
   - `compound.should` for OR conditions
   - `compound.mustNot` for NOT conditions
3. Express logical relationships through nested compound structures, NOT through additional $match stages
4. For aggregation pipelines, use a single $search stage whenever possible
5. Format dates as ISO-8601 strings. Format genres to ONLY ones in this list: {genres_list}
6. Return only the query JSON with no explanations

## Examples
Simple find query:
```
{{
  "query": {{
    "genres": "role-playing (rpg)",
    "first_release_date": {{ "$gte": "2010-01-01T00:00:00Z" }}
  }},
  "type": "simple"
}}
```

Complex search with OR condition:
```
{{
  "query": [
    {{
      "$search": {{
        "index": "default",
        "compound": {{
          "should": [
            {{
              "compound": {{
                "must": [
                  {{ "text": {{ "path": "franchises", "query": "God of War" }} }},
                  {{ "range": {{ "path": "first_release_date", "gt": "2010-01-01T00:00:00Z" }} }}
                ]
              }}
            }},
            {{
              "equals": {{ "path": "genres", "value": "role-playing (rpg)" }}
            }}
          ]
        }}
      }}
    }}
  ],
  "type": "aggregate"
}}
```
"""

load_dotenv()


class QueryEvaluationOutput(BaseModel):
    is_allowed: bool = Field(
        description="Whether a query is allowed (True) or not (False)"
    )
    query_type: str | None = Field(
        description="Type of query (HARD_QUERY or SOFT_QUERY) if allowed", default=None
    )


class MongoQueryOutput(BaseModel):
    query: list[dict[str, Any]] | dict[str, Any] = Field(
        description="MongoDB query object"
    )
    type: str = Field(description="Query type (simple or aggregate)")


class QueryState(BaseModel):
    query: str
    query_type: str | None = None
    genres_list: list[str] = []
    result: dict[str, Any] | None = None


class QueryType(str, Enum):
    Aggregate = "aggregate"
    Simple = "simple"


def evaluate_query(state: QueryState):
    """Evaluate if query is allowed and classify it if it is."""
    messages = [
        SystemMessage(content=QUERY_EVAL_PROMPT),
        HumanMessage(content=state.query),
    ]

    structured_llm = llm.with_structured_output(QueryEvaluationOutput)
    response = structured_llm.invoke(messages)

    query_type = None
    if response.is_allowed:
        query_type = response.query_type
    else:
        query_type = "NOT_ALLOWED"

    return QueryState(query=state.query, query_type=query_type, result=None)


def check_query_type(state: QueryState):
    """Gate function to check the query type."""
    return state.query_type


def handle_hard_query(state: QueryState):
    """Extract relevant fields for HARD_QUERY types."""
    messages = [
        SystemMessage(
            content=CREATE_MONGO_QUERY_PROMPT.format(genres_list=state.genres_list)
        ),
        HumanMessage(content=state.query),
    ]

    response = llm.invoke(messages)

    try:
        structured_llm = llm.with_structured_output(MongoQueryOutput)
        response = structured_llm.invoke(messages)
        extracted_json = {"query": response.query, "type": response.type}
        convert_date_strings_to_datetime(extracted_json)

        return QueryState(
            query=state.query,
            query_type=state.query_type,
            result=extracted_json,
        )
    except Exception as e:
        logger.error(f"Error parsing extraction response: {e}")
        logger.error(f"Response content: {response.content}")
        raise


def convert_date_strings_to_datetime(obj: dict | list):
    """Recursively traverse a dictionary or list and convert date strings to datetime objects."""

    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                obj[key] = convert_date_strings_to_datetime(value)
            elif isinstance(value, str) and date_pattern.match(value):
                obj[key] = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            obj[i] = convert_date_strings_to_datetime(item)

    return obj


def compile_agent_workflow():
    workflow = StateGraph(QueryState)
    workflow.add_node("evaluate_query", evaluate_query)
    workflow.add_node("handle_hard_query", handle_hard_query)

    workflow.add_edge(START, "evaluate_query")
    workflow.add_conditional_edges(
        "evaluate_query",
        check_query_type,
        {"HARD_QUERY": "handle_hard_query", "SOFT_QUERY": END, "NOT_ALLOWED": END},
    )
    workflow.add_edge("handle_hard_query", END)

    return workflow.compile()


chain = compile_agent_workflow()


@app.get("/")
async def health_check():
    return {"status": "OK"}


@app.post("/search")
async def search(user_query: QueryState):
    user_query.genres_list = app.genres
    chain_response = chain.invoke(user_query)

    try:
        chain_result: MongoQueryOutput = chain_response["result"]
        logger.info(chain_result)

        match chain_result["type"]:
            case QueryType.Aggregate:
                result = (
                    await app.db["games"]
                    .aggregate(chain_result["query"])
                    .to_list(length=20)
                )
            case QueryType.Simple:
                result = (
                    await app.db["games"].find(chain_result["query"]).to_list(length=20)
                )
    except KeyError as e:
        logger.error(f"Malformed LLM response: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The search query could not be processed",
        )
    except PyMongoError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred",
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )

    return result


def main():
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8001, reload=True)


if __name__ == "__main__":
    main()
