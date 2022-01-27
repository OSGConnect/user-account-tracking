#!/bin/bash
docker container run \
    -v $(pwd)/snapshots:/user-account-tracking/snapshots \
    -v $(pwd)/token_DO_NOT_VERSION:/user-account-tracking/token_DO_NOT_VERSION \
    -v $(pwd)/email_credentials_DO_NOT_VERSION:/user-account-tracking/email_credentials_DO_NOT_VERSION \
    --name test \
    --rm \
    ryantanaka/user-account-tracking \
    --start 20210409_snapshot.json \
    --end 20210412_snapshot.json


