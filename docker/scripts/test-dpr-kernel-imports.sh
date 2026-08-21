#!/usr/bin/env bash
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

# Verify that every Jupyter kernel used by dpr can execute a small notebook that imports eopf,
# sentineltoolbox, matplotlib, cartopy and xarray. Exits non-zero if any kernel fails, which is
# meant to fail the CI build.
#
# eopf's public API changed between its 2.x and 3.x major versions (e.g. eopf.store.zarr.EOZarrStore
# was replaced by eopf.store.zarr_reader.EODataTreeZarrReader), so there are two notebooks: one per
# cpm_version major version, selected per kernel from dask-cluster-versions.yml.

set -euo pipefail
set -x

image=${1:-}
deps_file=${2:-}
notebook_cpm2=${3:-}
notebook_cpm3=${4:-}
if [[ (-z ${image:-}) || (-z ${deps_file:-}) || (-z ${notebook_cpm2:-}) || (-z ${notebook_cpm3:-}) ]]; then
    echo "usage: $0 IMAGE PATH_TO_DEPS_FILE PATH_TO_CPM2_NOTEBOOK PATH_TO_CPM3_NOTEBOOK"
    exit 2
fi

# Install yq (https://github.com/mikefarah/yq#wget)
curl --proto '=https' --proto-redir '=https' --max-redirs 1 --fail --silent --show-error --location \
    https://github.com/mikefarah/yq/releases/download/v4.53.6/yq_linux_amd64 -o /usr/local/bin/yq
chmod +x /usr/local/bin/yq

# dpr kernels are dependency sets whose "used_by" list contains "dpr" (see dask-cluster-versions.yml)
deps=$(yq -o json "$deps_file" | jq -c '.deps[] | select(.used_by | index("dpr") != null)')

notebook_cpm2_abs=$(realpath "$notebook_cpm2")
notebook_cpm3_abs=$(realpath "$notebook_cpm3")
failed_kernels=()

while IFS= read -r dep; do
    python_version=$(jq -r '."python_version"' <<< "$dep")
    dask_version=$(jq -r '."dask_version"' <<< "$dep")
    cpm_version=$(jq -r '."cpm_version"' <<< "$dep")
    dep_name="py${python_version}-${dask_version}"

    case ${cpm_version%%.*} in
        2) notebook_abs=$notebook_cpm2_abs ;;
        3) notebook_abs=$notebook_cpm3_abs ;;
        *)
            echo "❌ Kernel '$dep_name' has an unrecognized cpm_version '$cpm_version' (expected a 2.x or 3.x major version): add a matching test notebook"
            failed_kernels+=("$dep_name")
            continue
            ;;
    esac

    echo "🧪 Testing kernel: $dep_name (cpm ${cpm_version})"
    if ! docker run --rm \
        --entrypoint jupyter \
        -v "${notebook_abs}:/tmp/test-dpr-kernel-imports.ipynb:ro" \
        "$image" \
        nbconvert --to notebook --execute \
            --ExecutePreprocessor.kernel_name="$dep_name" \
            --ExecutePreprocessor.timeout=300 \
            --output /tmp/test-dpr-kernel-imports.out.ipynb \
            /tmp/test-dpr-kernel-imports.ipynb
    then
        echo "❌ Kernel '$dep_name' failed to execute the test notebook"
        failed_kernels+=("$dep_name")
    fi
done <<< "$deps"

# Remove dependencies
rm -f /usr/local/bin/yq

if [[ ${#failed_kernels[@]} -gt 0 ]]; then
    echo "❌ dpr kernels failing the import test: ${failed_kernels[*]}"
    exit 1
fi

echo "✅ All dpr kernels passed the import test"
