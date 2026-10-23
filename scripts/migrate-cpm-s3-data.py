#!/usr/bin/env python3
# Copyright 2023-2026 Airbus, CS Group
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
CPM S3 Test Data Migration Tool.

Migrates test datasets from SDE S3 (dpr-common) to RSPY S3 (cpm-input),
excluding obsolete/unnecessary datasets (e.g. 2.6.2 unit test data).
"""

import argparse
import logging
import os
import sys

try:
    import boto3
    from botocore.config import Config
except ImportError:
    boto3 = None
    Config = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cpm-s3-migrator")

EXCLUDED_PATTERNS = [
    "unit_test_data_2.6.2.zip",
    "unit_test_data_2.6.2.zip.sha256",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Migrate CPM S3 test datasets from SDE to RSPY.")
    parser.add_argument(
        "--src-endpoint",
        default=os.getenv("SRC_S3_ENDPOINT", "https://s3.sbg.perf.cloud.ovh.net"),
        help="Source S3 endpoint URL (SDE)",
    )
    parser.add_argument(
        "--src-bucket",
        default=os.getenv("SRC_S3_BUCKET", "dpr-common"),
        help="Source S3 bucket",
    )
    parser.add_argument(
        "--src-prefix",
        default="cpm-test-data/",
        help="Source prefix in bucket",
    )
    parser.add_argument(
        "--src-access-key",
        default=os.getenv("SRC_S3_ACCESS_KEY", "7c6864894e3440149aa7f537f645e585"),
        help="Source S3 access key",
    )
    parser.add_argument(
        "--src-secret-key",
        default=os.getenv("SRC_S3_SECRET_KEY", "7215de3f38a649a8bb9494df7ec2ae0c"),
        help="Source S3 secret key",
    )
    parser.add_argument(
        "--dst-endpoint",
        default=os.getenv("DST_S3_ENDPOINT", "https://s3.gra.io.cloud.ovh.net"),
        help="Destination S3 endpoint URL (RSPY)",
    )
    parser.add_argument(
        "--dst-bucket",
        default=os.getenv("DST_S3_BUCKET", "cpm-input"),
        help="Destination S3 bucket",
    )
    parser.add_argument(
        "--dst-prefix",
        default="cpm-test-data/",
        help="Destination prefix in bucket",
    )
    parser.add_argument(
        "--dst-access-key",
        default=os.getenv("DST_S3_ACCESS_KEY", "61e991d2a77b4ffdb4c2c7a49499f00e"),
        help="Destination S3 access key",
    )
    parser.add_argument(
        "--dst-secret-key",
        default=os.getenv("DST_S3_SECRET_KEY", "246fd69bf517460f9f556a2acff710be"),
        help="Destination S3 secret key",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the migration without transferring data",
    )
    return parser.parse_args()


def is_excluded(key: str) -> bool:
    for pattern in EXCLUDED_PATTERNS:
        if pattern in key:
            return True
    return False


def get_s3_client(endpoint_url, access_key, secret_key):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def main():
    args = parse_args()
    if boto3 is None:
        logger.error("boto3 is required to run this script. Please install it with 'pip install boto3'.")
        return 1
    logger.info("=== CPM S3 Migration: SDE -> RSPY ===")
    logger.info("Source:      s3://%s/%s (%s)", args.src_bucket, args.src_prefix, args.src_endpoint)
    logger.info("Destination: s3://%s/%s (%s)", args.dst_bucket, args.dst_prefix, args.dst_endpoint)
    logger.info("Dry-run:     %s", args.dry_run)

    src_s3 = get_s3_client(args.src_endpoint, args.src_access_key, args.src_secret_key)
    dst_s3 = get_s3_client(args.dst_endpoint, args.dst_access_key, args.dst_secret_key)

    paginator = src_s3.get_paginator("list_objects_v2")
    objects_to_migrate = []
    objects_excluded = []
    total_bytes = 0

    logger.info("Discovering source objects...")
    for page in paginator.paginate(Bucket=args.src_bucket, Prefix=args.src_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            size = obj["Size"]
            if is_excluded(key):
                objects_excluded.append((key, size))
            else:
                objects_to_migrate.append((key, size, obj.get("ETag", "")))
                total_bytes += size

    logger.info("Found %d objects to migrate (%0.2f GB)", len(objects_to_migrate), total_bytes / (1024**3))
    logger.info("Excluded %d obsolete/unnecessary objects", len(objects_excluded))
    for key, size in objects_excluded:
        logger.info("  [EXCLUDED] %s (%d bytes)", key, size)

    if args.dry_run:
        logger.info("Dry run complete. No data copied.")
        return 0

    transferred = 0
    errors = 0
    for idx, (key, size, etag) in enumerate(objects_to_migrate, start=1):
        rel_key = key[len(args.src_prefix):] if key.startswith(args.src_prefix) else key
        dst_key = args.dst_prefix + rel_key

        logger.info("[%d/%d] Copying %s (%d bytes) -> %s", idx, len(objects_to_migrate), key, size, dst_key)
        try:
            # Stream directly using response body
            src_obj = src_s3.get_object(Bucket=args.src_bucket, Key=key)
            dst_s3.upload_fileobj(src_obj["Body"], args.dst_bucket, dst_key)
            transferred += 1
        except Exception as e:
            logger.error("Failed to copy %s: %s", key, e)
            errors += 1

    logger.info("=== Migration Finished ===")
    logger.info("Successfully transferred: %d objects", transferred)
    logger.info("Errors encountered:       %d objects", errors)

    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
