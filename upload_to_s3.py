import os
import threading
import sys

import boto3
from boto3.s3.transfer import S3Transfer
import argparse

class ProgressPercentage(object):
        def __init__(self, filename):
            self._filename = filename
            self._size = float(os.path.getsize(filename))
            self._seen_so_far = 0
            self._lock = threading.Lock()

        def __call__(self, bytes_amount):
            # To simplify we'll assume this is hooked up
            # to a single filename.
            with self._lock:
                self._seen_so_far += bytes_amount
                percentage = (self._seen_so_far / self._size) * 100
                sys.stdout.write(
                    "\r%s  %s / %s  (%.2f%%)" % (
                        self._filename, self._seen_so_far, self._size,
                        percentage))
                sys.stdout.flush()

def get_s3_env_variables() -> dict[str,str]:
    return {k.lower()[3:]:v for k,v in os.environ.items() if k.lower().startswith("s3_")}

def create_s3_client() -> boto3.client:
    client_init_kwargs = get_s3_env_variables()
    return boto3.client(service_name="s3", use_ssl=True, **client_init_kwargs)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload local file to S3")
    parser.add_argument("-f","--file", help="The local file to upload to S3"),
    parser.add_argument("-o","--object-name", help="The name of the object to upload to the bucket. If not specified will the file name", default=None)
    parser.add_argument("-b", "--bucket", help="The name of the bucket to push the file to")
    return parser.parse_args()
    
    

if __name__ == "__main__":
    args = parse_args()
    s3_client = create_s3_client()
    transfer = S3Transfer(s3_client)
    object_name = args.object_name or os.path.basename(args.file)
    print(f"Uploading {args.file} to bucket {args.bucket} as {object_name}")
    transfer.upload_file(args.file, args.bucket, object_name, callback=ProgressPercentage(args.file))
