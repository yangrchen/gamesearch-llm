import datetime
import io
import json
import logging
import os
import urllib

import boto3
import polars as pl
import pymongo
import s3fs
from pymongo.errors import PyMongoError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")


def get_required_env(var: str):
    value = os.environ.get(var)
    if not value:
        raise ValueError(f"{var} environment variable is required but not set")

    return value


def read_json_from_s3(bucket: str, key: str) -> pl.DataFrame:
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        df = pl.read_json(io.StringIO(content))
        return df
    except Exception as e:
        logger.error(f"Error retrieving {key} from S3: {str(e)}")
        raise


def connect_to_mongodb():
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

        return client
    except PyMongoError as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise


def lambda_handler(event, context):
    bucket_name = get_required_env("S3_BUCKET")
    mongodb_database = os.environ.get("MONGODB_DATABASE", "gamesearch")
    mongodb_collection = os.environ.get("MONGODB_COLLECTION", "games")

    try:
        mongodb_client = connect_to_mongodb()
        gamesearch_db = mongodb_client[mongodb_database]
        games_collection = gamesearch_db[mongodb_collection]

        games_df = read_json_from_s3(bucket_name, "games.json")

        genres_df = read_json_from_s3(bucket_name, "genres.json")
        genres_df = genres_df.with_columns(name=pl.col("name").str.to_lowercase())
        genres_map = genres_df.select(pl.col("id", "name")).to_dict(as_series=False)
        genres_map = dict(zip(genres_map["id"], genres_map["name"]))

        franchises_df = read_json_from_s3(bucket_name, "franchises.json")
        franchises_df = franchises_df.with_columns(
            name=pl.col("name").str.to_lowercase()
        )
        franchises_map = franchises_df.select(pl.col("id", "name")).to_dict(
            as_series=False
        )
        franchises_map = dict(zip(franchises_map["id"], franchises_map["name"]))

        logger.info(
            f"Loaded data: {games_df.height} games, {genres_df.height} genres, {franchises_df.height} franchises"
        )

        current_time = datetime.datetime.now(datetime.UTC)

        games_df = games_df.with_columns(
            genres=pl.col("genres")
            .cast(pl.List(pl.String))
            .list.eval(pl.element().replace(genres_map)),
            franchises=pl.col("franchises")
            .cast(pl.List(pl.String))
            .list.eval(pl.element().replace(franchises_map)),
            first_release_date=pl.from_epoch(
                pl.col("first_release_date"), time_unit="s"
            ),
            last_updated=pl.lit(current_time),
        ).rename({"id": "_id"})

        fs = s3fs.S3FileSystem()
        dest = f"s3://{bucket_name}/transformed_games.json"
        with fs.open(dest, mode="wb") as f:
            games_df.write_json(f)

        games_dicts = games_df.to_dicts()
        games_collection.delete_many({})
        games_collection.insert_many(games_dicts, ordered=False)

        logger.info(
            "Finished processing game data and wrote to S3 and MongoDB database"
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Game data processed successfully",
                    "games_count": games_df.height,
                    "mongodb_status": "Data inserted successfully",
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error processing game data: {str(e)}")
        raise
