from __future__ import annotations

import datetime
import io
import json
import logging
import os
import urllib
import urllib.parse

import boto3
import polars as pl
import pymongo
import s3fs
import voyageai
from pymongo.errors import PyMongoError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")


class EmbeddingService:
    """Embedding service using Voyage AI."""

    def __init__(self, api_key: str):
        self.client = voyageai.Client(api_key=api_key)

    def generate_embeddings(
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


def create_searchable_text(
    text_df: pl.DataFrame,
    columns: list[str] | None = None,
) -> pl.DataFrame:
    """Create a comprehensive text representation of game data for embeddings."""
    exprs = []
    if columns:
        for col_name in columns:
            if isinstance(text_df.schema[col_name], pl.List):
                exprs.append(
                    pl.concat_str(
                        pl.lit(f"{col_name}: "),
                        pl.col(col_name).list.join(", "),
                    ),
                )
            else:
                exprs.append(pl.concat_str(pl.lit(f"{col_name}: "), pl.col(col_name)))
    else:
        for col_name in text_df.columns:
            if isinstance(text_df.schema[col_name], pl.List):
                exprs.append(
                    pl.concat_str(
                        pl.lit(f"{col_name}: "),
                        pl.col(col_name).list.join(", "),
                    ),
                )
            else:
                exprs.append(pl.concat_str(pl.lit(f"{col_name}: "), pl.col(col_name)))

    return text_df.with_columns(searchable_text=pl.concat_str(exprs, separator=" | "))


def read_json_from_s3(bucket: str, key: str) -> pl.DataFrame:
    """Read JSON data from S3 and return as a Polars DataFrame.

    Parameters
    ----------
    bucket : str
        The S3 bucket name.
    key : str
        The S3 object key/path.

    Returns
    -------
    polars.DataFrame
        The JSON data as a Polars DataFrame.

    Raises
    ------
    Exception
        If there's an error retrieving or parsing the S3 object.

    """
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        json_data = pl.read_json(io.StringIO(content))
    except Exception:
        logger.exception("Error retrieving %s from S3", key)
        raise
    else:
        return json_data


def connect_to_mongodb() -> pymongo.MongoClient:
    """Connect to MongoDB using environment variables for authentication."""
    try:
        base_uri = get_required_env("MONGODB_BASE_URI")
        user = get_required_env("MONGODB_USER")
        password = get_required_env("MONGODB_PASSWORD")

        user = urllib.parse.quote_plus(user)
        password = urllib.parse.quote_plus(password)

        modified_uri = f"mongodb+srv://{user}:{password}@"
        full_uri = base_uri.replace("mongodb+srv://", modified_uri)

        client = pymongo.MongoClient(full_uri)

        client.admin.command("ping")
        logger.info("Successfully connected to MongoDB database")
    except PyMongoError:
        logger.exception("Failed to connect to MongoDB")
        raise
    else:
        return client


def lambda_handler(event, context):
    bucket_name = get_required_env("S3_BUCKET")
    voyageai_api_key = get_required_env("VOYAGEAI_API_KEY")
    mongodb_database = os.environ.get("MONGODB_DATABASE", "gamesearch")
    mongodb_collection = os.environ.get("MONGODB_COLLECTION", "games")
    batch_size: int = int(os.environ.get("BATCH_SIZE", 1000))

    try:
        # Initialize embeddings service
        embedding_service = EmbeddingService(api_key=voyageai_api_key)

        # Connect to MongoDB games collection
        mongodb_client = connect_to_mongodb()
        gamesearch_db = mongodb_client[mongodb_database]
        games_collection = gamesearch_db[mongodb_collection]

        # Load raw data from S3 bucket
        games_df = read_json_from_s3(bucket_name, "games.json")
        genres_df = read_json_from_s3(bucket_name, "genres.json")
        franchises_df = read_json_from_s3(bucket_name, "franchises.json")

        logger.info(
            "Loaded data: %d games, %d genres, %d franchises",
            games_df.height,
            genres_df.height,
            franchises_df.height,
        )

        # Create text mappings of genres and franchises
        genres_df = genres_df.with_columns(name=pl.col("name").str.to_lowercase())
        genres_map = genres_df.select(pl.col("id", "name")).to_dict(as_series=False)
        genres_map = dict(zip(genres_map["id"], genres_map["name"]))

        franchises_df = franchises_df.with_columns(
            name=pl.col("name").str.to_lowercase(),
        )
        franchises_map = franchises_df.select(pl.col("id", "name")).to_dict(
            as_series=False,
        )
        franchises_map = dict(zip(franchises_map["id"], franchises_map["name"]))

        # Process games data with mappings
        games_df = games_df.with_columns(summary=pl.col("summary").str.to_lowercase())

        current_time = datetime.datetime.now(datetime.UTC)

        games_df = games_df.with_columns(
            genres=pl.col("genres")
            .cast(pl.List(pl.String))
            .list.eval(pl.element().replace(genres_map)),
            franchises=pl.col("franchises")
            .cast(pl.List(pl.String))
            .list.eval(pl.element().replace(franchises_map)),
            first_release_date=pl.from_epoch(
                pl.col("first_release_date"),
                time_unit="s",
            ),
            last_updated=pl.lit(current_time),
        ).rename({"id": "_id"})

        fs = s3fs.S3FileSystem()
        dest = f"s3://{bucket_name}/transformed_games.json"
        with fs.open(dest, mode="wb") as f:
            games_df.write_json(f)

        # Create searchable text for vector search embeddings
        games_df = create_searchable_text(
            games_df,
            columns=["name", "franchises", "genres", "summary"],
        )

        # Create batched vector embeddings
        embedding_frames = []
        for frame in games_df.iter_slices(n_rows=batch_size):
            texts = frame.get_column("searchable_text").to_list()
            embed = embedding_service.generate_embeddings(texts)
            frame = frame.with_columns(pl.Series("text_embeddings", embed))
            embedding_frames.append(frame)

        games_df = pl.concat(embedding_frames)
        games_dicts = games_df.to_dicts()

        games_collection.delete_many({})
        games_collection.insert_many(games_dicts, ordered=False)

        logger.info(
            "Finished processing game data and wrote to S3 and MongoDB database",
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Game data processed successfully",
                    "games_count": games_df.height,
                    "mongodb_status": "Data inserted successfully",
                },
            ),
        }

    except Exception:
        logger.exception("Error processing game data")
        raise


if __name__ == "__main__":
    lambda_handler(None, None)
