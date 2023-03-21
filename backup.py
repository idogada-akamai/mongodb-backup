import logging
import operator
import os
from datetime import date, datetime, time, timedelta, timezone
from time import sleep
from typing import Any, List

import boto3
from atlasapi.atlas import Atlas
from atlasapi.cloud_backup import (
    DeliveryType,
    SnapshotRestoreResponse,
    SnapshotStatus,
    SnapshotType,
)
from dotenv import load_dotenv
from rclone.rclone import RClone
from rclone.rclone_config.storage_system import S3, Http


class Filter:
    def __init__(self, attribute: str, comparison: operator, value: Any):
        self.attribute = attribute
        self.comparison = comparison
        self.value = value

    def __call__(self, obj: object) -> bool:
        return self.comparison(getattr(obj, self.attribute), self.value)

    @classmethod
    def match_all(cls, obj: Any, filters: List["Filter"]) -> bool:
        return all(f(obj) for f in filters)


class MaxRetriesError(Exception):
    """Raised when maximum retries of a given a code have been reached"""

    def __init__(
        self,
        max_retries: int,
        message: str = "Max retries have been reached (max_retries={})",
    ) -> None:
        self.max_retries = max_retries
        Exception.__init__(self, message.format(self.max_retries))


class RestoreJobNotFoundError(Exception):
    pass


def atlas_auth():
    return Atlas(
        os.environ["MONGODB_ATLAS_PUBLIC_API_KEY"],
        os.environ["MONGODB_ATLAS_PRIVATE_API_KEY"],
        os.environ["MONGODB_ATLAS_PROJECT_ID"],
    )


def get_latest_snapshot_by_date_range(
    atlas_client: Atlas, cluster_name: str, min_date: datetime, max_date: datetime
):
    logging.debug(
        f"Looking for latest snapshot older than {max_date} and newer than {min_date}. In cluster {cluster_name}"
    )
    filters = [
        Filter("created_at", operator.ge, min_date),
        Filter("created_at", operator.lt, max_date),
        Filter("status", operator.eq, SnapshotStatus.COMPLETED),
        Filter("snapshot_type", operator.eq, SnapshotType.SCHEDULED),
    ]

    snapshot_iterator = filter(
        lambda x: Filter.match_all(x, filters),
        atlas_client.CloudBackups.get_backup_snapshots_for_cluster(cluster_name),
    )
    snapshots = list(snapshot_iterator)
    snapshots.sort(key=lambda x: x.created_at, reverse=False)
    snapshot_id = snapshots[0].id
    # TODO: check that snapshot has been found and raise error or return the ID
    logging.info(f"Found snapshot: {snapshot_id}")
    return snapshot_id


def create_download_restore_job(
    atlas_client: Atlas, cluster_name: str, snapshot_id: str
) -> str:
    logging.debug(
        f"Creating a download restore job for snapshot {snapshot_id}, in cluster {cluster_name}"
    )
    restore_job: SnapshotRestoreResponse = (
        atlas_client.CloudBackups.request_snapshot_restore(
            source_cluster_name=cluster_name,
            snapshot_id=snapshot_id,
            delivery_type=DeliveryType.download,
            target_cluster_name=cluster_name,
            allow_same=True,
        )
    )
    return restore_job.restore_id


def wait_for_delivery_url(
    atlas_client: Atlas,
    cluster_name: str,
    restore_id: str,
    max_retries: int = 100,
    interval: int = 10,
) -> str:
    logging.info(
        f"Waiting for a download url to be available for snapshot with restore id {restore_id}"
    )
    for _ in range(max_retries):
        # The function returns an iterator, therefore we're getting the first and checking that it's not None
        restore_job: SnapshotRestoreResponse = next(
            atlas_client.CloudBackups.get_snapshot_restore_requests(
                cluster_name=cluster_name, restore_id=restore_id
            ),
            None,
        )
        if not isinstance(restore_job, SnapshotRestoreResponse):
            raise RestoreJobNotFoundError(
                f"Could not find snapshot with {restore_id:d}"
            )
        if restore_job.delivery_url:
            logging.info(
                f"Delivery URL found, for restore job {restore_id}, has been found"
            )
            return restore_job.delivery_url[0]
        logging.debug(
            f"Delivery URL not yet available. Sleeping for {interval} seconds"
        )
        sleep(interval)
    raise MaxRetriesError(max_retries)


def rclone_copy_to_s3(
    source_http_config: Http,
    source_file: str,
    destination_s3_config: S3,
    destination_bucket_name: str,
    destination_path: str = "",
    flags: List[str] = None,
):
    if not flags:
        flags = []

    rclone_client = RClone(source_http_config, destination_s3_config)
    source_string = f"{source_http_config.name}:{source_file}"
    destination_string = (
        f"{destination_s3_config.name}:{destination_bucket_name}/{destination_path}"
    )
    rclone_client.copy(source_string, destination_string, flags)


def get_snapshots_to_delete(
    s3_client: boto3.client,
    older_than: datetime,
    min_to_keep: int,
    bucket: str,
    cluster_name: str,
) -> list[str]:
    logging.info(
        f"Getting snapshots to delete according the this plan. {older_than=}, {min_to_keep=}"
    )
    response = s3_client.list_objects(Bucket=bucket, Prefix=f"{cluster_name}/")

    snapshots_files: List[dict] = response["Contents"]
    snapshots_files.sort(key=lambda x: x["LastModified"], reverse=False)
    max_snapshots_to_delete = len(snapshots_files) - min_to_keep

    snapshot_files = (
        snapshot
        for snapshot in snapshots_files
        if snapshot["LastModified"] <= older_than
    )
    snapshots_to_delete = []

    for _ in range(max_snapshots_to_delete):
        try:
            snapshots_to_delete.append(next(snapshot_files))
        except StopIteration as e:
            logging.debug(
                f"Reached end of snapshot list before max snapshots to delete({max_snapshots_to_delete})"
            )
            break
    logging.debug(f"The follwing snapshots have been found {snapshots_to_delete}")
    return snapshots_to_delete


def s3_delete_old_snapshots(
    older_than: datetime,
    min_to_keep: int,
    bucket: str,
    cluster_name: str,
    s3_config: S3,
):
    s3_client = boto3.client(
        service_name="s3",
        use_ssl=True,
        aws_access_key_id=s3_config.access_key_id,
        aws_secret_access_key=s3_config.secret_access_key,
        region_name=s3_config.region,
        endpoint_url=s3_config.endpoint,
    )

    if snapshot_to_delete := get_snapshots_to_delete(
        s3_client=s3_client,
        older_than=older_than,
        min_to_keep=min_to_keep,
        cluster_name=cluster_name,
        bucket=bucket,
    ):
        delete_objects = [{"Key": snapshot} for snapshot in snapshot_to_delete]

        logging.info(
            f"Deleting the following files in {bucket}/{cluster_name}, {snapshot_to_delete}"
        )

        response = s3_client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": delete_objects},
        )

        # Logging for error and success
        if response.get("Deleted", []):
            successful_deletions = ",".join(
                deletion["Deleted"]["Key"] for deletion in response
            )
            logging.info(f"Successfully deleted snapshots {successful_deletions}")

        if response.get("Errors", []):
            for error in response["Errors"]:
                snapshot_name = error["Key"]
                error_message = error["Message"]
                error_code = error["Code"]

            logging.error(
                f"Failed to delete snapshot {snapshot_name}({error_code}) - {error_message}"
            )
    else:
        logging.warning(
            f"No matching snapshot to delete have been found at {bucket}/{cluster_name}"
        )


def main():
    ## Initial config ##
    logging.basicConfig(
        level=logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO")),
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    load_dotenv(os.environ.get("DOTENV_PATH", ".env"))
    atlas_client = atlas_auth()
    s3_config = S3(
        name="s3",
        provider=os.environ["S3_PROVIDER"],
        access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        region=os.environ["S3_REGION"],
        endpoint=os.environ["S3_ENDPOINT"],
    )
    s3_bucket_name = os.environ["S3_BUCKET_NAME"]
    cluster_name = os.environ["MONGODB_ATLAS_CLUSTER_NAME"]

    ## Get latest snapshot ##
    today = date.today()
    today_midnight = datetime.combine(today, time.min, timezone.utc)
    yesterday_midnight = today_midnight - timedelta(days=1)
    snapshot_id = get_latest_snapshot_by_date_range(
        atlas_client=atlas_client,
        cluster_name=cluster_name,
        min_date=yesterday_midnight,
        max_date=today_midnight,
    )

    ## Create download URL ##
    restore_job_id = create_download_restore_job(
        atlas_client=atlas_client, cluster_name=cluster_name, snapshot_id=snapshot_id
    )
    delivery_url = wait_for_delivery_url(
        atlas_client=atlas_client, cluster_name=cluster_name, restore_id=restore_job_id
    )

    ## Copy snapshot to S3 ##
    file_name = delivery_url[delivery_url.rindex("/") + 1 : :]
    http_url = delivery_url.removesuffix(file_name)
    http_config = Http(name="http", url=http_url)
    rclone_flags = os.environ.get("RCLONE_FLAGS", "").split(" ")
    rclone_copy_to_s3(
        source_http_config=http_config,
        source_file=file_name,
        destination_s3_config=s3_config,
        destination_bucket_name=s3_bucket_name,
        destination_path=cluster_name,
        flags=rclone_flags,
    )

    ## Delete old snapshots ##
    snapshot_retention_days = int(os.environ["SNAPSHOT_RETENTION_DAYS"])
    max_snapshot_count = int(os.environ["SNAPSHOT_RETENTION_COUNT"])
    max_snapshot_date = today_midnight - timedelta(days=snapshot_retention_days)
    s3_delete_old_snapshots(
        older_than=max_snapshot_date,
        min_to_keep=max_snapshot_count,
        bucket=s3_bucket_name,
        cluster_name=cluster_name,
        s3_config=s3_config,
    )


if __name__ == "__main__":
    main()
