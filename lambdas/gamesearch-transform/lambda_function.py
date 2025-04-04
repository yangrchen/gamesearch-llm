import io
import json
import logging
import os

import boto3
import polars as pl
import s3fs

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")


def read_json_from_s3(bucket: str, key: str) -> pl.DataFrame:
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        df = pl.read_json(io.StringIO(content))
        return df
    except Exception as e:
        logger.error(f"Error retrieving {key} from S3: {str(e)}")
        raise


def lambda_handler(event, context):
    bucket_name = os.environ.get("S3_BUCKET")

    if not bucket_name:
        raise ValueError("S3_BUCKET variable is required but not set")

    try:
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

        games_df = games_df.with_columns(
            genres=pl.col("genres")
            .cast(pl.List(pl.String))
            .list.eval(pl.element().replace(genres_map)),
            franchises=pl.col("franchises")
            .cast(pl.List(pl.String))
            .list.eval(pl.element().replace(franchises_map)),
        )

        fs = s3fs.S3FileSystem()
        dest = f"s3://{bucket_name}/transformed_games.json"
        with fs.open(dest, mode="wb") as f:
            games_df.write_json(f)

        logger.info("Finished processing game data and wrote to S3")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Game data processed successfully",
                    "games_count": games_df.height,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error processing game data: {str(e)}")
        raise
