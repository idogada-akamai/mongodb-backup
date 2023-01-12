#! /bin/bash
set -e

#project_id=$1 Check whether env var or command line arguments is better
cluster_name=$1
snapshot_description="$2"
snapshot_id=""

# S3 bucket to upload the backup to
s3_bucket="$3"

function create_snapshot() {
    echo "Creating an on demmand snapshot for cluster $cluster_name"
    snapshot_id=$(atlas backup snapshots create $cluster_name --desc "$snapshot_description" -o json | jq -r '.id')

    echo "Waiting for snapshot $snapshot_id to complete"
    atlas backup snapshots watch $snapshot_id --clusterName $cluster_name
}

function download_snapshot() {

    # Create the manual download job
    echo "Creating a download restore job"
    local restore_job_id=$(atlas backups restores start download --clusterName $cluster_name --snapshotId $snapshot_id -o json | jq -r '.id')
    echo "restore_job_id is: $restore_job_id"

    # Wait until snapshot is available for downlod
    echo "Waiting for snapshot URL to become available"
    while ! $(atlas backup restore describe --clusterName $cluster_name $restore_job_id -o json | jq -e 'has("deliveryUrl")'); do
        echo "Donload URL not yet avaiable"
        sleep 5
    done

    # Download the snapshot
    local download_url=$(atlas backup restore describe --clusterName $cluster_name $restore_job_id -o json | jq -r '.deliveryUrl[0]')
    snapshot_file_name=${download_url##*/}
    wget -c $download_url -O /tmp/$snapshot_file_name

}

function upload_to_s3() {
    echo "Uploading snapshot to S3 bucket: $s3_bucket"
    python upload_to_s3.py \
        --file /tmp/$snapshot_file_name \
        --object-name $snapshot_file_name \
        --bucket $s3_bucket
}

create_snapshot
download_snapshot
upload_to_s3
