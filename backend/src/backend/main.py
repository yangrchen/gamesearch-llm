import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import END, START, StateGraph
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
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


async def get_genre_service() -> GenreService:
    return app.genre_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_client(app)
    yield
    await shutdown_db_client(app)


async def init_db_client(app: FastAPI):
    app.mongodb_client = AsyncIOMotorClient(os.environ.get("MONGODB_URI"))
    app.db = app.mongodb_client.get_database("gamesearch")
    app.genre_service = GenreService(app.db)
    await app.genre_service.get_genres()


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

GUARDRAIL_PROMPT = """Your role is to assess whether the user query is relevant to searching for games or not. Allowed topics are:

- Searching for game titles or games by release date, genre, franchise
- Requesting games by a summary or that are similar to other games

Queries cannot have code, special symbols or harmful content.

If the topic is allowed, respond with "ALLOWED" otherwise say "NOT_ALLOWED". Only respond with these two results.
"""

QUERY_TYPE_PROMPT = """You are a game search assistant. Your task is to:
1. First determine if the user is asking for:
    - A "hard query" which is searching for a game with specific fields like genre, name, release date (respond with exactly: "HARD_QUERY")
    - A "soft query" which is searching for a game that is similar to some summary or like other games (respond with exactly: "SOFT_QUERY")
2. Only respond with one of these two options, nothing else.
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


class QueryState(BaseModel):
    query: str
    query_type: str | None
    genres_list: list[str] = []
    result: dict[str, Any] | None


def guard_query(state: QueryState):
    messages = [
        SystemMessage(content=GUARDRAIL_PROMPT),
        HumanMessage(content=state.query),
    ]

    response = llm.invoke(messages)
    allowed_query = response.content.strip()

    return QueryState(
        query=state.query, query_type=allowed_query, extracted_fields=None, result=None
    )


def classify_query(state: QueryState) -> QueryState:
    """Classify the query as based on the prompt provided."""
    messages = [
        SystemMessage(content=QUERY_TYPE_PROMPT),
        HumanMessage(content=state.query),
    ]

    response = llm.invoke(messages)
    query_type = response.content.strip()

    return QueryState(
        query=state.query, query_type=query_type, extracted_fields=None, result=None
    )


def check_query_type(state: QueryState):
    """Gate function to check if query is type HARD_QUERY or type SOFT_QUERY."""
    return state.query_type


def handle_hard_query(state: QueryState):
    """Extract relevant fields for HARD_QUERY types."""
    parser = JsonOutputParser()

    messages = [
        SystemMessage(
            content=CREATE_MONGO_QUERY_PROMPT.format(genres_list=state.genres_list)
        ),
        HumanMessage(content=state.query),
    ]

    response = llm.invoke(messages)

    try:
        extracted_json = parser.parse(response.content)
        convert_date_strings_to_datetime(extracted_json)
        logger.info(extracted_json)
        return QueryState(
            query=state.query,
            query_type=state.query_type,
            extracted_fields=None,
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


workflow = StateGraph(QueryState)

workflow.add_node("guard_query", guard_query)
workflow.add_node("classify_query", classify_query)
workflow.add_node("handle_hard_query", handle_hard_query)

workflow.add_edge(START, "guard_query")
workflow.add_conditional_edges(
    "guard_query", check_query_type, {"ALLOWED": "classify_query", "NOT_ALLOWED": END}
)
workflow.add_conditional_edges(
    "classify_query",
    check_query_type,
    {"HARD_QUERY": "handle_hard_query", "SOFT_QUERY": END},
)
workflow.add_edge("handle_hard_query", END)

chain = workflow.compile()


@app.get("/")
async def health_check():
    return {"status": "OK"}


@app.post("/search")
async def search(
    user_query: QueryState, genre_service: GenreService = Depends(get_genre_service)
):
    genres = await genre_service.get_genres()
    user_query.genres_list = genres
    chain_result = chain.invoke(user_query)
    result = chain_result["result"]

    return result


def main():
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8001, reload=True)


if __name__ == "__main__":
    main()
