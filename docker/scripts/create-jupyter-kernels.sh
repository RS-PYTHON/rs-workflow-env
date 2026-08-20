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
# {"python_version": "3.13.12", "dask_version": "2026.3.0"},
# ...
echo "Read: '$deps_file'"
cat "$deps_file"

# Install dependencies
apt update && apt install -y jq

# Install yq (https://github.com/mikefarah/yq#wget)
wget --max-redirect=1 https://github.com/mikefarah/yq/releases/download/v4.53.6/yq_linux_amd64 -O /usr/local/bin/yq
chmod +x /usr/local/bin/yq

# For each set of python/dask versions
deps=$(yq -o json "$deps_file" | jq -c '.deps[]')
for dep in $deps; do
    python_version=$(jq -r '."python_version"' <<< "$dep")
    dask_version=$(jq -r '."dask_version"' <<< "$dep")
    dep_name="py${python_version}-${dask_version}"
    used_by=$(jq -r '.used_by[]' <<< "${dep}")

    # Create the conda environment
    conda create -y -n "$dep_name" python="$python_version"
    # shellcheck source=/dev/null
    conda init bash zsh && source ~/.zshrc # note: sourcing ~/.bashrc doesn't work because we're in non-interactive mode
    conda activate "$dep_name"

    # Install dependencies.
    # --no-compile skips generating .pyc bytecode caches: it's regenerated lazily on first import,
    # and skipping it shaves a meaningful chunk off these heavy, duplicated-per-kernel installs.
    pip install --only-binary :all: -U pip
    pip install --only-binary :all: --no-compile \
        ipykernel \
        "dask[complete]==${dask_version}" \
        dask-gateway=="${DASK_GATEWAY_TAG}" \
        prefect=="${PREFECT_TAG}" \
        python-socks \
        ipywidgets
    if [[ ${used_by} == "dpr" ]]; then
        cpm_version=$(jq -r '."cpm_version"' <<< "${dep}")
        # asciitree (pulled in by zarr, a eopf dependency) only ships a source distribution on
        # PyPI, so it must be excluded from the --only-binary :all: constraint.
        pip install --only-binary :all: --no-binary asciitree --no-compile eopf=="${cpm_version}"
    fi

    # Install the Jupyter kernel
    python -m ipykernel install --name "$dep_name"

    # Back to default conda env
    conda deactivate
done

# Remove dependencies
apt autoremove -y jq
rm -f /usr/local/bin/yq
