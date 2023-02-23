import operator
import os
from datetime import date, datetime, time, timedelta, timezone
from time import sleep
from typing import Any, List

from atlasapi.atlas import Atlas
from atlasapi.cloud_backup import (
    DeliveryType,
    SnapshotRestoreResponse,
    SnapshotStatus,
    SnapshotType,
)

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


def get_snapshot_by_date_range(
    atlas_client: Atlas, cluster_name: str, min_date: datetime, max_date: datetime
):
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
    # TODO: check that snapshot has been found and raise error or return the ID
    return snapshots[0].id


def create_download_restore_job(
    atlas_client: Atlas, cluster_name: str, snapshot_id: str
) -> str:
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
    for _ in range(max_retries):
        # The function returns an iterator, therefore we're getting the first and checking that it's no None
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
            print("Delivery URL found")
            return restore_job.delivery_url[0]
        print(f"Delivery URL not yet available. Sleeping for {interval} seconds")
        sleep(interval)
    raise MaxRetriesError(max_retries)


def rclone_copy_to_s3(
    source_http_config: Http,
    source_file: str,
    destination_s3_config: S3,
    destination_bucket_name: str,
    flags: List[str] = None,
):
    if not flags:
        flags = []

    rclone_client = RClone(source_http_config, destination_s3_config)
    source_string = f"{source_http_config.name}:{source_file}"
    destination_string = f"{destination_s3_config.name}:{destination_bucket_name}"
    rclone_client.copy(source_string, destination_string, flags)


def s3_delete_old_snapshots(older_than: datetime, min_to_keep: int):
    pass


def main():
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

    today = date.today()
    today_midnight = datetime.combine(today, time(), timezone.utc)
    yesterday_midnight = datetime.combine(
        today - timedelta(days=1), time(), timezone.utc
    )

    snapshot_id = get_snapshot_by_date_range(
        atlas_client=atlas_client,
        cluster_name=cluster_name,
        min_date=yesterday_midnight,
        max_date=today_midnight,
    )

    restore_job_id = create_download_restore_job(
        atlas_client=atlas_client, cluster_name=cluster_name, snapshot_id=snapshot_id
    )

    delivery_url = wait_for_delivery_url(
        atlas_client=atlas_client, cluster_name=cluster_name, restore_id=restore_job_id
    )

    file_name = delivery_url[delivery_url.rindex("/") + 1 : :]
    http_url = delivery_url.removesuffix(file_name)
    http_config = Http(name="http", url=http_url)

    rclone_flags = os.environ.get("RCLONE_FLAGS", "").split(" ")
    rclone_copy_to_s3(
        source_http_config=http_config,
        source_file=file_name,
        destination_s3_config=s3_config,
        destination_bucket_name=s3_bucket_name,
        flags=rclone_flags,
    )


if __name__ == "__main__":
    main()
