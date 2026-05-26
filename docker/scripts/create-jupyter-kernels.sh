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

# Create Jupyter kernels for each set of dependency versions needed by the different dpr and staging dask clusters

set -euo pipefail
set -x

# Read first argument = path to the file that contains the sets of dependency versions
deps_file=${1:-}
if [[ (-z ${deps_file:-}) || (${deps_file} == "-h") || (${deps_file} == "--help") ]]; then
    echo "usage: $0 PATH_TO_DEPS_FILE"
    exit 2
fi

# We read the json file that contains the sets of dependency versions needed by the different processors.
# After conversion to json, its content should be something like:
# {"deps": [
# {"python_version": "3.11.7", "dask_version": "2024.5.2"},
# {"python_version": "3.13.12", "dask_version": "2026.1.2"},
# ...
echo "Read: '$deps_file'"
cat "$deps_file"

# Install dependencies
apt update && apt install -y jq

# Install yq (https://github.com/mikefarah/yq#wget)
wget https://github.com/mikefarah/yq/releases/download/v4.49.2/yq_linux_amd64 -O /usr/local/bin/yq
chmod +x /usr/local/bin/yq

# For each set of python/dask versions
deps=$(yq -o json "$deps_file" | jq -c '.deps[]')
for dep in $deps; do
    python_version=$(jq -r '."python_version"' <<< "$dep")
    dask_version=$(jq -r '."dask_version"' <<< "$dep")
    dep_name="py${python_version}-${dask_version}"

    # Create the conda environment
    conda create -y -n "$dep_name" python="$python_version"
    # shellcheck source=/dev/null
    conda init bash zsh && source ~/.zshrc # note: sourcing ~/.bashrc doesn't work because we're in non-interactive mode
    conda activate "$dep_name"

    # Install dependencies
    pip install -U pip
    pip install \
        ipykernel \
        "dask[complete]==${dask_version}" \
        dask-gateway=="${DASK_GATEWAY_TAG}"

    # Install the Jupyter kernel
    python -m ipykernel install --name "$dep_name"

    # Back to default conda env
    conda deactivate
done

# Remove dependencies
apt autoremove -y jq
rm -f /usr/local/bin/yq
