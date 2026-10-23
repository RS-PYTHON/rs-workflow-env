#!/bin/bash
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

set -euo pipefail

SRC_ENDPOINT="${SRC_S3_ENDPOINT:-s3.sbg.perf.cloud.ovh.net}"
SRC_BUCKET="${SRC_S3_BUCKET:-dpr-common}"
SRC_ACCESS_KEY="${SRC_S3_ACCESS_KEY:-7c6864894e3440149aa7f537f645e585}"
SRC_SECRET_KEY="${SRC_S3_SECRET_KEY:-7215de3f38a649a8bb9494df7ec2ae0c}"

DST_ENDPOINT="${DST_S3_ENDPOINT:-s3.gra.io.cloud.ovh.net}"
DST_BUCKET="${DST_S3_BUCKET:-cpm-input}"
DST_ACCESS_KEY="${DST_S3_ACCESS_KEY:-61e991d2a77b4ffdb4c2c7a49499f00e}"
DST_SECRET_KEY="${DST_S3_SECRET_KEY:-246fd69bf517460f9f556a2acff710be}"

DRY_RUN="${DRY_RUN:-false}"

echo "=== CPM S3 Migration (s3cmd) ==="
echo "Source:      s3://${SRC_BUCKET}/cpm-test-data/ (${SRC_ENDPOINT})"
echo "Destination: s3://${DST_BUCKET}/cpm-test-data/ (${DST_ENDPOINT})"
echo "Dry-run:     ${DRY_RUN}"

TMP_CONFIG_SRC=$(mktemp)
TMP_CONFIG_DST=$(mktemp)
trap 'rm -f "${TMP_CONFIG_SRC}" "${TMP_CONFIG_DST}"' EXIT

cat <<EOF > "${TMP_CONFIG_SRC}"
[default]
access_key = ${SRC_ACCESS_KEY}
secret_key = ${SRC_SECRET_KEY}
host_base = ${SRC_ENDPOINT}
host_bucket = ${SRC_ENDPOINT}/%(bucket)s
signature_v2 = True
EOF

cat <<EOF > "${TMP_CONFIG_DST}"
[default]
access_key = ${DST_ACCESS_KEY}
secret_key = ${DST_SECRET_KEY}
host_base = ${DST_ENDPOINT}
host_bucket = ${DST_ENDPOINT}/%(bucket)s
EOF

TMP_DOWNLOAD_DIR=$(mktemp -d)
trap 'rm -rf "${TMP_DOWNLOAD_DIR}" "${TMP_CONFIG_SRC}" "${TMP_CONFIG_DST}"' EXIT

echo "1. Syncing ci_test_data/..."
s3cmd -c "${TMP_CONFIG_SRC}" sync \
    --exclude="*unit_test_data_2.6.2*" \
    "s3://${SRC_BUCKET}/cpm-test-data/ci_test_data/" "${TMP_DOWNLOAD_DIR}/ci_test_data/"

echo "2. Downloading unit_test_data/unit_test_data.zip..."
mkdir -p "${TMP_DOWNLOAD_DIR}/unit_test_data"
s3cmd -c "${TMP_CONFIG_SRC}" get \
    "s3://${SRC_BUCKET}/cpm-test-data/unit_test_data/unit_test_data.zip" "${TMP_DOWNLOAD_DIR}/unit_test_data/unit_test_data.zip"
s3cmd -c "${TMP_CONFIG_SRC}" get \
    "s3://${SRC_BUCKET}/cpm-test-data/unit_test_data/README.txt" "${TMP_DOWNLOAD_DIR}/unit_test_data/README.txt" || true

echo "3. Downloading cpm-test-data/README.txt..."
s3cmd -c "${TMP_CONFIG_SRC}" get \
    "s3://${SRC_BUCKET}/cpm-test-data/README.txt" "${TMP_DOWNLOAD_DIR}/README.txt" || true

if [ "${DRY_RUN}" = "true" ]; then
    echo "Dry-run enabled. Skipping upload to destination."
    exit 0
fi

echo "4. Uploading to destination s3://${DST_BUCKET}/cpm-test-data/..."
s3cmd -c "${TMP_CONFIG_DST}" sync \
    "${TMP_DOWNLOAD_DIR}/" "s3://${DST_BUCKET}/cpm-test-data/"

echo "=== S3 Migration Finished Successfully ==="
