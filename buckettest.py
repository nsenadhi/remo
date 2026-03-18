import os

import boto3

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("S3_KEY_ID", ""),
    aws_secret_access_key=os.getenv("S3_SECRET_KEY", ""),
    region_name="us-east-1"
)

response = s3.list_buckets()

for b in response["Buckets"]:
    print("Bucket:", b["Name"], "| Created:", b["CreationDate"])
