from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Any

import voyageai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import PyMongoError
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    handlers=[RichHandler(rich_tracebacks=True)],
    format="%(message)s",
)
logger = logging.getLogger(__name__)

CACHE_TTL: int | str = os.getenv("CACHE_TTL", 3000)


class GenreService:
    def __init__(self, database):
        self.database = database
        self._genres: list[str] = None

    async def get_genres(self) -> list[str]:
        if self._genres is None:
            cursor: list[str] = await self.database["games"].distinct("genres")
            self._genres = list(cursor)
            logger.info(f"Loaded {len(self._genres)} genres")

        return self._genres


class EmbeddingService:
    """Embedding service using Voyage AI."""

    def __init__(self, api_key: str) -> None:
        """Initialize service with Voyage AI client."""
        self.client = voyageai.Client(api_key=api_key)

    async def generate_embeddings(
        self,
        texts: list[str],
        input_type: str = "document",
    ) -> list[list[float]] | list[list[int]]:
        """Generate embeddings using Voyage AI client."""
        try:
            result = self.client.embed(
                texts=texts,
                model="voyage-3",
                input_type=input_type,
            )
        except Exception:
            logger.exception("Error generating embeddings")
            raise
        else:
            return result.embeddings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_client(app)
    yield
    await shutdown_client(app)


async def init_client(app: FastAPI):
    app.mongodb_client = AsyncIOMotorClient(os.environ.get("MONGODB_URI"))
    app.db = app.mongodb_client.get_database("gamesearch")
    app.genres = await GenreService(app.db).get_genres()
    app.embedding_service = EmbeddingService(api_key=os.environ.get("VOYAGEAI_API_KEY"))


async def shutdown_client(app: FastAPI):
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

GUARDRAILS_PROMPT = """Your role is to assess if a user query about games is safe and appropriate.

Check if the query:
-   Is relevant to searching for games
-   Contains no harmful, offensive, or inappropriate content
-   Contains no code injection attempts or special symbols that could be malicious
-   Is a legitimate search request

Respond with structured output indicating if the query is allowed and a reason for why the query was not allowed.
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
2. `type`: Either "SIMPLE" or "AGGREGATE"
3. `project`: Dictionary that maps all fields in the schema to 1

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
7. Only project the fields name, summary, genres, first_release_date

## Examples
Simple find query:
```
{{
  "query": {{
    "genres": "role-playing (rpg)",
    "first_release_date": {{ "$gte": "2010-01-01T00:00:00Z" }}
  }},
  "project": {{"name": 1, "first_release_date": 1, "genres": 1, "franchises": 1}},
  "type": "SIMPLE"
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
  "project": {{"name": 1, "first_release_date": 1, "genres": 1, "franchises": 1}},
  "type": "AGGREGATE"
}}
```
"""

load_dotenv()


class MongoQueryType(str, Enum):
    Aggregate = "AGGREGATE"
    Simple = "SIMPLE"


class QueryEvaluationOutput(BaseModel):
    is_allowed: bool = Field(
        description="Whether a query is allowed (True) or not (False)",
    )
    violation_reason: str | None = Field(
        description="Violation reason for why the query was not allowed",
        default=None,
    )


class MongoQueryOutput(BaseModel):
    query: list[dict[str, Any]] | dict[str, Any] = Field(
        description="MongoDB query object",
    )
    project: dict[str, int] = Field(
        description="Dictionary of fields to include in MongoDB execution",
    )
    type: str = Field(description="Query type (SIMPLE or AGGREGATE)")


class QueryState(BaseModel):
    query: str
    use_vector_search: bool
    evaluation_output: QueryEvaluationOutput | None = None
    genres_list: list[str] = []
    error: str | None = None
    result: list[Any] | None = None

    model_config = ConfigDict(exclude_none=True)


def evaluate_query(state: QueryState):
    """Evaluate if query is allowed and return status as structured output."""
    messages = [
        SystemMessage(content=GUARDRAILS_PROMPT),
        HumanMessage(content=state.query),
    ]

    structured_llm = llm.with_structured_output(QueryEvaluationOutput)
    state.evaluation_output = structured_llm.invoke(messages)
    state.result = None

    return state


def check_allowed(state: QueryState):
    """Routing function to handle if the query is allowed."""
    return state.evaluation_output.is_allowed


def route_allowed_by_type(state: QueryState):
    """Routing function to handle allowed queries by their query type."""
    return state.use_vector_search


def handle_not_allowed(state: QueryState):
    """Respond to a query that is not allowed."""
    state.error = "This type of query is not allowed. Please try again with a search for game-related topics."

    return state


def handle_allowed(state: QueryState):
    return state


async def handle_hard_query(state: QueryState):
    """Extract relevant fields for HARD_QUERY types."""
    messages = [
        SystemMessage(
            content=CREATE_MONGO_QUERY_PROMPT.format(genres_list=state.genres_list),
        ),
        HumanMessage(content=state.query),
    ]

    response = llm.invoke(messages)

    try:
        structured_llm = llm.with_structured_output(MongoQueryOutput)
        response = structured_llm.invoke(messages)
        extracted_json = response.model_dump()
        _convert_date_strings_to_datetime(extracted_json)
        logger.info(extracted_json)

        match extracted_json["type"]:
            case MongoQueryType.Aggregate:
                extracted_json["query"].append({"$project": extracted_json["project"]})
                state.result = (
                    await app.db["games"]
                    .aggregate(extracted_json["query"])
                    .to_list(length=20)
                )
            case MongoQueryType.Simple:
                state.result = (
                    await app.db["games"]
                    .find(extracted_json["query"], extracted_json["project"])
                    .to_list(length=20)
                )
    except Exception:
        logger.exception("Error parsing extraction response")
        raise
    else:
        return state


async def handle_vector_query(state: QueryState):
    """Run a user query as a vector search in MongoDB database."""
    try:
        user_embed = await app.embedding_service.generate_embeddings(state.query)
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "text_embeddings",
                    "queryVector": user_embed[0],
                    "numCandidates": 150,
                    "limit": 20,
                },
            },
            {
                "$project": {
                    "_id": 1,
                    "name": 1,
                    "summary": 1,
                    "first_release_date": 1,
                    "genres": 1,
                    "franchises": 1,
                },
            },
        ]
        state.result = await app.db["games"].aggregate(pipeline).to_list()
    except Exception:
        logger.exception("Error running vector search")
        raise
    else:
        return state


def _convert_date_strings_to_datetime(obj: dict | list):
    """Recursively traverse a dictionary or list and convert date strings to datetime objects."""
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                obj[key] = _convert_date_strings_to_datetime(value)
            elif isinstance(value, str) and date_pattern.match(value):
                obj[key] = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            obj[i] = _convert_date_strings_to_datetime(item)

    return obj


def compile_agent_workflow():
    workflow = StateGraph(QueryState)
    workflow.add_node("evaluate_query", evaluate_query)
    workflow.add_node("handle_allowed", handle_allowed)
    workflow.add_node("handle_not_allowed", handle_not_allowed)
    workflow.add_node("handle_hard_query", handle_hard_query)
    workflow.add_node("handle_vector_query", handle_vector_query)

    workflow.add_edge(START, "evaluate_query")
    workflow.add_conditional_edges(
        "evaluate_query",
        check_allowed,
        {True: "handle_allowed", False: "handle_not_allowed"},
    )
    workflow.add_conditional_edges(
        "handle_allowed",
        route_allowed_by_type,
        {False: "handle_hard_query", True: "handle_vector_query"},
    )
    workflow.add_edge("handle_not_allowed", END)
    workflow.add_edge("handle_hard_query", END)
    workflow.add_edge("handle_vector_query", END)

    return workflow.compile()


chain = compile_agent_workflow()


@app.get("/")
async def health_check():
    return {"status": "OK"}


@app.post("/search")
async def search(user_query: QueryState):
    if len(user_query.query.strip()) == 0:
        logger.info(user_query)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The search query was empty",
        )

    user_query.genres_list = app.genres

    try:
        chain_response = await chain.ainvoke(user_query)
        chain_result: list[Any] = chain_response["result"]
        logger.info(chain_result)

    except KeyError as e:
        logger.exception("Malformed LLM response")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The search query could not be processed",
        ) from e
    except PyMongoError as e:
        logger.exception("Database error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e

    return chain_response


def main():
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8001, reload=True)


if __name__ == "__main__":
    main()
