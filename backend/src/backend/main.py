"""Main driver for agent execution and interacting with the games database."""

from __future__ import annotations

import datetime
import logging
import os
import re
import urllib
from contextlib import asynccontextmanager
from enum import Enum
from typing import TYPE_CHECKING, Any

import voyageai
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo.errors import PyMongoError
from rich.logging import RichHandler
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from langgraph.graph.graph import CompiledGraph
    from motor.motor_asyncio import AsyncIOMotorDatabase

logging.basicConfig(
    level=logging.INFO,
    handlers=[RichHandler(rich_tracebacks=True)],
    format="%(message)s",
)
logger = logging.getLogger(__name__)

CACHE_TTL = int(os.getenv("CACHE_TTL", "3000"))


class GenreService:
    """Genre service to retrieve existing game genres.

    This service manages the retrieval and caching of game genres from
    the MongoDB database.

    Attributes
    ----------
    database : motor.motor_asyncio.AsyncIOMotorDatabase
        MongoDB database connection
    _genres : list[str] or None
        Cached list of game genres

    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        """Initialize service with MongoDB connection.

        Parameters
        ----------
        db : motor.motor_asyncio.AsyncIOMotorDatabase
            MongoDB database connection

        """
        self.db = db
        self._genres: list[str] = None

    async def get_genres(self) -> list[str]:
        """Retrieve list of game genres from the database.

        Fetches distinct genres from the games collection. Results are
        cached after first retrieval.

        Returns
        -------
        list[str]
            List of unique game genres

        """
        if self._genres is None:
            exec_query: list[str] = await self.db["games"].distinct(
                "genres",
                {"genres": {"$ne": None}},
            )
            self._genres = list(exec_query)
            logger.info("Loaded %d genres", len(self._genres))

        return self._genres


class EmbeddingService:
    """Embedding service using Voyage AI.

    This service provides text embedding generation capabilities using
    the Voyage AI API.

    Attributes
    ----------
    client : voyageai.Client
        Voyage AI client instance

    """

    def __init__(self, api_key: str) -> None:
        """Initialize service with Voyage AI client.

        Parameters
        ----------
        api_key : str
            Voyage AI API key for authentication

        """
        self.client = voyageai.Client(api_key=api_key)

    async def generate_embeddings(
        self,
        texts: list[str],
        input_type: str = "document",
    ) -> list[list[float]] | list[list[int]]:
        """Generate embeddings using Voyage AI client.

        Parameters
        ----------
        texts : list[str]
            List of text strings to generate embeddings for
        input_type : str, optional
            Type of input text, by default "document"

        Returns
        -------
        list[list[float]] or list[list[int]]
            List of embedding vectors for each input text

        Raises
        ------
        Exception
            If embedding generation fails

        """
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


def get_required_env(var: str) -> str:
    """Raise an exception for env variables that should be provided.

    Parameters
    ----------
    var : str
        The name of the environment variable to retrieve.

    Returns
    -------
    str
        The value of the environment variable.

    Raises
    ------
    ValueError
        If the environment variable is not set or is empty.

    """
    value = os.environ.get(var)
    if not value:
        msg = f"{var} environment variable is required but not set"
        raise ValueError(msg)

    return value


def load_config():
    """Load configuration based on environment."""
    environment = os.getenv("ENVIRONMENT", "development")

    if environment == "development":
        try:
            from dotenv import load_dotenv

            load_dotenv()
            logger.info("Development mode: Loaded configuration from .env file")
        except ImportError:
            logger.warning("python-dotenv not available, using environment variables")
    else:
        logger.info("Production mode: Loaded configuration from environment variables")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Manage FastAPI application lifespan.

    Handles initialization and cleanup of database connections and
    services during application startup and shutdown.

    Parameters
    ----------
    app : FastAPI
        FastAPI application instance

    Yields
    ------
    None
        Control during application runtime

    """
    load_config()

    await init_client(app)
    yield
    await shutdown_client(app)


async def init_client(app: FastAPI) -> None:
    """Initialize database client and services.

    Sets up MongoDB connection, database reference, genre service,
    and embedding service for the FastAPI application.

    Parameters
    ----------
    app : FastAPI
        FastAPI application instance to attach services to

    """
    base_uri = get_required_env("MONGODB_BASE_URI")
    mongodb_user = get_required_env("MONGODB_USER")
    mongodb_password = get_required_env("MONGODB_PASSWORD")

    mongodb_user = urllib.parse.quote_plus(mongodb_user)
    mongodb_password = urllib.parse.quote_plus(mongodb_password)

    modified_uri = f"mongodb+srv://{mongodb_user}:{mongodb_password}@"
    full_uri = base_uri.replace("mongodb+srv://", modified_uri)

    app.mongodb_client = AsyncIOMotorClient(full_uri)
    app.db = app.mongodb_client.get_database("gamesearch")
    app.genres = await GenreService(app.db).get_genres()
    app.embedding_service = EmbeddingService(api_key=os.environ.get("VOYAGEAI_API_KEY"))


async def shutdown_client(app: FastAPI) -> None:
    """Close database client connection.

    Properly closes the MongoDB client connection during application
    shutdown to prevent resource leaks.

    Parameters
    ----------
    app : FastAPI
        FastAPI application instance containing the MongoDB client

    """
    app.mongodb_client.close()


def get_allowed_origins() -> list[str]:
    """Get allowed origins from environment variable."""
    origins_env = os.environ.get("ALLOWED_ORIGINS", "")
    if not origins_env:
        return ["http://localhost:5173"]

    return [origin.strip() for origin in origins_env.split(",")]


app = FastAPI(title="Gamesearch API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["*"],
    max_age=CACHE_TTL,
)


@app.middleware("http")
async def validate_origin(request: Request, call_next):
    """Validate request origin for additional security."""
    origin = request.headers.get("origin")
    referrer = request.headers.get("referrer")

    allowed_origins = get_allowed_origins()
    if not origin and not referrer:
        if request.url.path in ["/health", "/docs", "openapi.json"]:
            response = await call_next(request)
            return response

        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Origin header required"},
        )

    request_origin = origin or referrer
    if not any(origin in request_origin for origin in allowed_origins):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Origin header required"},
        )
    response = await call_next(request)
    return response


llm = ChatAnthropic(model="claude-3-7-sonnet-20250219", temperature=0)

GUARDRAILS_PROMPT = """
Your role is to assess if a user query about games is safe and appropriate.

Check if the query:
-   Is relevant to searching for games
-   Contains no harmful, offensive, or inappropriate content
-   Contains no code injection attempts or special symbols that could be malicious
-   Is a legitimate search request

Respond with structured output indicating if the query is allowed and a reason
for why the query was not allowed.
"""

CREATE_MONGO_QUERY_PROMPT = """
You are a MongoDB query generator for games databases.
Transform natural language game queries into JSON format MongoDB queries.

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
3. Express logical relationships through nested compound structures,
NOT through additional $match stages
4. For aggregation pipelines, use a single $search stage whenever possible
5. Format dates as ISO-8601 strings. Format genres to ONLY ones in this list:
{genres_list}
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
"""  # noqa: E501


class MongoQueryType(str, Enum):
    """Enum for MongoDB query types.

    Defines the types of MongoDB queries that can be executed.

    Attributes
    ----------
    Aggregate : str
        Aggregation pipeline query type
    Simple : str
        Simple find query type

    """

    Aggregate = "AGGREGATE"
    Simple = "SIMPLE"


class QueryEvaluationOutput(BaseModel):
    """Model for query evaluation results.

    Contains the results of evaluating whether a user query is safe
    and appropriate for execution.

    Attributes
    ----------
    is_allowed : bool
        Whether a query is allowed (True) or not (False)
    violation_reason : str or None
        Violation reason for why the query was not allowed

    """

    is_allowed: bool = Field(
        description="Whether a query is allowed (True) or not (False)",
    )
    violation_reason: str | None = Field(
        description="Violation reason for why the query was not allowed",
        default=None,
    )


class MongoQueryOutput(BaseModel):
    """Model for MongoDB query output.

    Contains the structured MongoDB query information generated from
    natural language input.

    Attributes
    ----------
    query : list[dict[str, Any]] or dict[str, Any]
        MongoDB query object (aggregation pipeline or find query)
    project : dict[str, int]
        Dictionary of fields to include in MongoDB execution
    type : str
        Query type (SIMPLE or AGGREGATE)

    """

    query: list[dict[str, Any]] | dict[str, Any] = Field(
        description="MongoDB query object",
    )
    project: dict[str, int] = Field(
        description="Dictionary of fields to include in MongoDB execution",
    )
    type: str = Field(description="Query type (SIMPLE or AGGREGATE)")

    @field_validator("query", mode="after")
    @classmethod
    def convert_date_strings(
        cls,
        value: list[dict[str, Any]] | dict[str, Any],
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Field validator to automatically convert date strings into datetime objects.

        Used to convert date patterns in the processed query to datetime objects for the
        MongoDB queries to work properly.

        Parameters
        ----------
        cls : MongoQueryOutput
            The class being validated (automatically provided by Pydantic)
        value : list[dict[str, Any]] or dict[str, Any]
            The query object containing potential date strings to convert

        Returns
        -------
        list[dict[str, Any]] or dict[str, Any]
            The query object with date strings converted to datetime objects

        """
        return _convert_date_strings_to_datetime(value)


class QueryState(BaseModel):
    """Model representing the state of a query throughout processing.

    Contains all information needed to process, execute, and paginate
    through query results.

    Attributes
    ----------
    query : str
        Original user query string
    use_vector_search : bool
        Whether to use vector search instead of MongoDB query
    evaluation_output : QueryEvaluationOutput or None
        Results of query safety evaluation
    genres_list : list[str]
        List of available game genres
    error : str or None
        Error message if query processing failed
    result : list[Any] or None
        Query execution results
    page : int
        Current page number for pagination (default: 1)
    page_size : int
        Number of results per page (default: 20)
    has_next_page : bool or None
        Whether more results are available
    processed_query : MongoQueryOutput | None
        Processed MongoDB output
    vector_embedding : list[float] or None
        Vector embedding for vector search queries

    """

    query: str
    use_vector_search: bool
    evaluation_output: QueryEvaluationOutput | None = None
    processed_output: MongoQueryOutput | None = None
    genres_list: list[str] = []
    error: str | None = None
    result: list[Any] | None = None
    page: int = 1
    page_size: int = 20
    has_next_page: bool | None = None
    vector_embedding: list[float] | None = None

    model_config = ConfigDict(exclude_none=True)


def evaluate_query(state: QueryState) -> QueryState:
    """Evaluate if query is allowed and return status as structured output.

    Uses an LLM with guardrails to determine if the user query is safe
    and appropriate for execution.

    Parameters
    ----------
    state : QueryState
        Current query state containing the user query

    Returns
    -------
    QueryState
        Updated state with evaluation results

    """
    messages = [
        SystemMessage(content=GUARDRAILS_PROMPT),
        HumanMessage(content=state.query),
    ]

    structured_llm = llm.with_structured_output(QueryEvaluationOutput)
    state.evaluation_output = structured_llm.invoke(messages)
    state.result = None

    return state


def check_allowed(state: QueryState) -> bool:
    """Routing function to handle if the query is allowed.

    Parameters
    ----------
    state : QueryState
        Current query state with evaluation results

    Returns
    -------
    bool
        True if query is allowed, False otherwise

    """
    return state.evaluation_output.is_allowed


def route_allowed_by_type(state: QueryState) -> bool:
    """Routing function to handle allowed queries by their query type.

    Parameters
    ----------
    state : QueryState
        Current query state

    Returns
    -------
    bool
        True if vector search should be used, False for MongoDB query

    """
    return state.use_vector_search


def handle_not_allowed(state: QueryState) -> QueryState:
    """Respond to a query that is not allowed.

    Sets an error message for queries that failed safety evaluation.

    Parameters
    ----------
    state : QueryState
        Current query state

    Returns
    -------
    QueryState
        Updated state with error message

    """
    state.error = "This type of query is not allowed. Please try again with a search for game-related topics."

    return state


def handle_allowed(state: QueryState) -> QueryState:
    """Handle queries that passed safety evaluation.

    Passthrough function for allowed queries.

    Parameters
    ----------
    state : QueryState
        Current query state

    Returns
    -------
    QueryState
        Unchanged query state

    """
    return state


async def handle_hard_query(state: QueryState) -> QueryState:
    """Extract relevant fields for HARD_QUERY types.

    Processes natural language queries into MongoDB queries using an LLM.
    Handles both simple find queries and aggregation pipelines with pagination.

    Parameters
    ----------
    state : QueryState
        Current query state with user query and genres list

    Returns
    -------
    QueryState
        Updated state with query results and pagination information

    Raises
    ------
    Exception
        If query parsing or execution fails

    """
    messages = [
        SystemMessage(
            content=CREATE_MONGO_QUERY_PROMPT.format(genres_list=state.genres_list),
        ),
        HumanMessage(content=state.query),
    ]

    try:
        if not state.processed_output:
            structured_llm = llm.with_structured_output(MongoQueryOutput)
            state.processed_output = structured_llm.invoke(messages)

        skip_count = (state.page - 1) * state.page_size

        match state.processed_output.type:
            case MongoQueryType.Aggregate:
                # Create a copy of the query for execution
                exec_query = state.processed_output.query.copy()
                exec_query.append({"$project": state.processed_output.project})

                # Add pagination to aggregate query and get one extra to check if there
                # are more pages
                exec_query.append({"$skip": skip_count})
                exec_query.append(
                    {"$limit": state.page_size + 1},
                )

                state.result = (
                    await app.db["games"].aggregate(exec_query).to_list(length=None)
                )

                # Check if there are more results
                state.has_next_page = len(state.result) > state.page_size
                if state.has_next_page:
                    state.result = state.result[:-1]  # Remove the extra result
            case MongoQueryType.Simple:
                # Add pagination to find query
                exec_query = app.db["games"].find(
                    state.processed_output.query,
                    state.processed_output.project,
                )
                exec_query = exec_query.skip(skip_count).limit(
                    state.page_size + 1,
                )
                state.result = await exec_query.to_list(length=None)

                # Check if there are more results
                state.has_next_page = len(state.result) > state.page_size
                if state.has_next_page:
                    state.result = state.result[:-1]  # Remove the extra result
    except Exception:
        logger.exception("Error parsing extraction response")
        raise
    else:
        return state


async def handle_vector_query(state: QueryState) -> QueryState:
    """Run a user query as a vector search in MongoDB database.

    Generates embeddings for the user query and performs vector similarity
    search against the games collection with pagination support.

    Parameters
    ----------
    state : QueryState
        Current query state with user query

    Returns
    -------
    QueryState
        Updated state with vector search results and pagination information

    Raises
    ------
    Exception
        If embedding generation or vector search fails

    """
    try:
        if not state.vector_embedding:
            user_embed = await app.embedding_service.generate_embeddings(state.query)
            # Store embedding for pagination
            state.vector_embedding = user_embed[0]
        skip_count = (state.page - 1) * state.page_size

        # Get extra results to enable pagination
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "text_embeddings",
                    "queryVector": state.vector_embedding,
                    "numCandidates": 150,
                    "limit": state.page_size + 1,
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
            {"$skip": skip_count},
        ]
        state.result = await app.db["games"].aggregate(pipeline).to_list()

        # Check if there are more results
        state.has_next_page = len(state.result) > state.page_size
        if state.has_next_page:
            state.result = state.result[:-1]  # Remove the extra result
    except Exception:
        logger.exception("Error running vector search")
        raise
    else:
        return state


def _convert_date_strings_to_datetime(obj: dict | list) -> dict[str, Any]:
    """Recursively traverse a dictionary or list and convert date strings to datetime objects.

    Searches for ISO 8601 formatted date strings and converts them to Python
    datetime objects for proper MongoDB query execution.

    Parameters
    ----------
    obj : dict or list
        Object to traverse and convert date strings in

    Returns
    -------
    dict or list
        Object with date strings converted to datetime objects

    """
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z{0,1}$")

    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                obj[key] = _convert_date_strings_to_datetime(value)
            elif isinstance(value, str) and date_pattern.match(value):
                if value.endswith("Z"):
                    obj[key] = datetime.datetime.strptime(
                        value,
                        "%Y-%m-%dT%H:%M:%SZ",
                    ).astimezone(datetime.UTC)
                else:
                    obj[key] = datetime.datetime.strptime(
                        value,
                        "%Y-%m-%dT%H:%M:%S",
                    ).astimezone(datetime.UTC)

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            obj[i] = _convert_date_strings_to_datetime(item)

    return obj


def compile_agent_workflow() -> CompiledGraph:
    """Compile the agent workflow for query processing.

    Creates a state graph that routes queries through safety evaluation,
    then to either MongoDB query generation or vector search based on
    the query type.

    Returns
    -------
    langgraph.graph.graph.CompiledGraph
        Compiled workflow graph for query processing

    """
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


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for AWS load balancer."""
    try:
        await app.mongodb_client.admin.command("ping")
        return {
            "status": "healthy",
            "timestamp": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        }
    except Exception as e:
        logger.exception("Health check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy",
        ) from e


@app.post("/search")
async def search(user_state: QueryState) -> QueryState:
    """Search for games using natural language queries.

    Processes user queries through safety evaluation and routes them to either
    MongoDB queries or vector search based on query type. Supports pagination
    for large result sets.

    Parameters
    ----------
    user_state : QueryState
        Query state containing search parameters and pagination metadata

    Returns
    -------
    dict[str, Any]
        Search response with pagination metadata

    Raises
    ------
    HTTPException
        400: If query is empty
        422: If query cannot be processed
        500: If database error or unexpected error occurs

    """
    if len(user_state.query.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The search query was empty",
        )

    user_state.genres_list = app.genres

    try:
        if user_state.vector_embedding:
            response = await handle_vector_query(user_state)
        elif user_state.processed_output:
            response = await handle_hard_query(user_state)
        else:
            # Normal workflow execution
            response = await chain.ainvoke(user_state)

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

    else:
        return response


def main() -> None:
    """Start the FastAPI application server.

    Runs the application using uvicorn with development settings including
    auto-reload functionality for code changes.

    """
    import uvicorn

    is_development = os.environ.get("ENVIRONMENT", "production") == "development"

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",  # noqa: S104
        port=int(os.environ.get("PORT", "8000")),
        reload=is_development,
        workers=1 if is_development else None,
    )


if __name__ == "__main__":
    main()
