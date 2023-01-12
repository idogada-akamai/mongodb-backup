# Mongo DB Backup

This Docker image helps create an on demand image on mongodb atlas and upload it to S3.

## upload_to_s3.py

This script uploads a specified file to S3 with a specific name if specified, otherwise it will use the file name.

```shell
usage: upload_to_s3.py [-h] [-f FILE] [-o OBJECT_NAME] [-b BUCKET]

Upload local file to S3

options:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  The local file to upload to S3
  -o OBJECT_NAME, --object-name OBJECT_NAME
                        The name of the object to upload to the bucket. If not specified will the file name
  -b BUCKET, --bucket BUCKET
                        The name of the bucket to push the file to
```
### Note
Environment variables starting with `S3_` (case insensitive) will be passed down to the boto3 s3 client constructor while emitting `S3_`.

## Configuration

If running on Docker, I recommend making 2 .env files and mounting them as environment variable in the container. For example, using the `env-file` flag with `docker run`.

These are the files I recommend on creating:

* mongodb_atlas.env
```sh
# API Authentication Details
MONGODB_ATLAS_PUBLIC_API_KEY=********
MONGODB_ATLAS_PRIVATE_API_KEY=**********
# Project ID and ORG in which the API creds have been set
MONGODB_ATLAS_ORG_ID=**********************
MONGODB_ATLAS_PROJECT_ID=******************
# Optional
MONGODB_ATLAS_OUTPUT=json
```

* s3.env
```sh
# These are a must have unless a profile is configured
S3_AWS_ACCESS_KEY_ID=************
S3_AWS_SECRET_ACCESS_KEY=****************
S3_REGION_NAME=us-east-1
# When using a different provider other than AWS, set this to point to its servers
# For example with Linode
S3_ENDPOINT_URL=https://us-east-1.linodeobjects.com
```

## Command Line Arguments

The script requires the following 3 command line argument:

* $1 - The cluster name to create snapshot from
* $2 - The description of the snapshot that will be created
* $3 - The S3 bucket name to push the snapshot to

## Example
Let's put it all together.

In this example we are creating a snapshot for a database called `mydb`, and uploading it to a bucket called `mongodb-backups`.

 ```
 docker run --rm \
    --env-file mongodb_atlas.env \
    --env-file s3.env \
    idogakamai/mongodb-backup \
    mydb "snapshot description" mongodb-backups
```
