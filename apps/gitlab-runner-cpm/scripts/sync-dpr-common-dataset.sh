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

# S3 dpr-common source configuration
S3_ACCESS_KEY="${S3_COMMON_ACCESS_KEY:-7c6864894e3440149aa7f537f645e585}"
S3_SECRET_KEY="${S3_COMMON_SECRET_KEY:-7215de3f38a649a8bb9494df7ec2ae0c}"
S3_HOST="${S3_COMMON_HOST:-s3.sbg.perf.cloud.ovh.net}"
S3_BUCKET="${S3_COMMON_BUCKET:-s3://dpr-common/cpm-test-data/ci_test_data/}"

DEST_DIR="${1:-/data/cache-ci/ci_test_data/}"
DRY_RUN="${DRY_RUN:-false}"

echo "=== S3 Sync of 105GB dpr-common dataset ==="
echo "Source:      ${S3_BUCKET} (${S3_HOST})"
echo "Destination: ${DEST_DIR}"
echo "Dry run:     ${DRY_RUN}"
echo "Started at:  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

mkdir -p "${DEST_DIR}"

EXTRA_ARGS=()
if [ "${DRY_RUN}" = "true" ]; then
    EXTRA_ARGS+=("--dry-run")
fi

s3cmd sync \
    --access_key="${S3_ACCESS_KEY}" \
    --secret_key="${S3_SECRET_KEY}" \
    --host="${S3_HOST}" \
    --host-bucket="${S3_HOST}/%(bucket)s" \
    --signature-v2 \
    --no-progress \
    --stats \
    "${EXTRA_ARGS[@]}" \
    "${S3_BUCKET}" "${DEST_DIR}"

if [ "${DRY_RUN}" != "true" ]; then
    echo "Fixing permissions on ${DEST_DIR}..."
    chmod -R 777 "${DEST_DIR}"
    echo "Completed at: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "Directory summary:"
    du -sh "${DEST_DIR}"* 2>/dev/null || true
fi
