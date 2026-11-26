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

#
# Build the base Docker images that are used in the cluster and in the ci/cd.
# Target Docker image names:
# ghcr.io/rs-python/python:xxx-slim-bookworm
# ghcr.io/rs-python/dask/dask-gateway:xxx-pyzzz-yyy
# ghcr.io/rs-python/prefecthq/prefect:xxx-pyzzz
# ghcr.io/rs-python/prefecthq/prefect:xxx-pyzzz-k8s
#

# shellcheck disable=SC2199,SC2086,SC2034,SC2206

set -euo pipefail
set -x

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# Directory that contains custom requirements for the docker images
CUSTOM_REQ=$(realpath "${SCRIPT_DIR}/../scripts")

PYTHON_VERSION=3.13.18
DASK_GATEWAY_TAG=2026.3.0
PREFECT_TAG=3.9.1

####################
# Retrieve options #
####################

PUSH=false
TARGET="all"

help() {
    echo "Usage: $0 [-p|--push] [-t|--target <target>]"
    echo "Target can be one of: all, python, dask, prefect"
    echo "Dask runner: RSPY_RUNNER_REF selects an rs-dpr-service branch, tag or commit (default: develop)."
    echo "Set RSPY_RUNNER_SOURCE to a local rs-dpr-service checkout to include uncommitted runner changes."
}

while [[ $# -gt 0 ]] && [[ "$1" == "-"* ]] ;
do
    arg="$1";
    shift;
    case $arg in
        "--" ) break 2;;
        -p|--push)
        PUSH=true
        ;;
        -t=*|--target=*)
        TARGET="${arg#*=}"
        ;;
        -t|--target)
        TARGET="$1"
        shift # Remove the target value from processing
        ;;
        -h|--help)
        help
        exit 0
        ;;
        *)
        echo "Invalid option: $arg" >&2
        help
        exit 1
        ;;
    esac
done

##########
# Python #
##########

if [[ "$TARGET" == "all" || "$TARGET" == "python" ]]; then

    python_dockerfile="Dockerfile.python"
    python_base="python:${PYTHON_VERSION}-slim-bookworm"

    python_target="ghcr.io/rs-python/${python_base}"

    # Build the docker image
    docker build \
        --build-arg "BASE=${python_base}" \
        --progress plain \
        -f "${SCRIPT_DIR}/${python_dockerfile}" \
        -t "$python_target" \
        "$CUSTOM_REQ"

    # Push the docker image to the registry, if the --push option is specified.
    if [[ "$PUSH" == "true" ]]; then
        docker push "$python_target"
    fi
fi

########
# Dask #
########

if [[ "$TARGET" == "all" || "$TARGET" == "dask" ]]; then

    runner_source="${RSPY_RUNNER_SOURCE:-}"
    if [[ -n "$runner_source" ]]; then
        runner_source=$(realpath "$runner_source")
    else
        runner_repo="${SCRIPT_DIR}/tmp/rs-dpr-service"
        if [[ ! -d "${runner_repo}/.git" ]]; then
            git clone --no-checkout https://github.com/RS-PYTHON/rs-dpr-service.git "$runner_repo"
        fi
        git -C "$runner_repo" fetch --depth=1 origin "${RSPY_RUNNER_REF:-develop}"
        runner_revision=$(git -C "$runner_repo" rev-parse FETCH_HEAD)
        echo "Building runner from rs-dpr-service commit ${runner_revision}"
    fi

    runner_files=(
        rs_dpr_service/__init__.py
        rs_dpr_service/runner/__init__.py
        rs_dpr_service/runner/eopf_runner.py
        rs_dpr_service/runner/runner_requirements.txt
        rs_dpr_service/utils/__init__.py
        rs_dpr_service/utils/settings.py
        rs_dpr_service/utils/logging.py
        rs_dpr_service/utils/init_opentelemetry.py
    )

    # We read the json file that contains the sets of dependency versions needed by the different processors.
    # After conversion to json, its content should be something like:
    # {"deps": [
    # {"python_version": "3.11.7", "dask_version": "2024.5.2"},
    # {"python_version": "3.13.12", "dask_version": "2026.3.0"},
    # ...
    deps_file="${CUSTOM_REQ}/dask-cluster-versions.yml"

    # For each set of python/dask versions
    deps=$(yq -o json $deps_file | jq -c '.deps[]')
    for dep in $deps; do
        python_version=$(jq -r '."python_version"' <<< $dep)
        dask_tag=$(jq -r '."dask_version"' <<< $dep)
        dep_name="py${python_version}-${dask_tag}"

        # Checkout the dask-gateway git repository into a local ./tmp folder
        tmp="${SCRIPT_DIR}/tmp/dask/py${python_version}"
        mkdir -p "$tmp"
        cd "$tmp"
        if [[ ! -d dask-gateway ]]; then
        git clone https://github.com/dask/dask-gateway.git
        fi
        cd dask-gateway
        git checkout "tags/$DASK_GATEWAY_TAG"
        git reset --hard

        # Stage only the runner and its shared helpers inside the Docker build context.
        runner_context="${tmp}/dask-gateway/eopf-runner"
        for file in "${runner_files[@]}"; do
            mkdir -p "${runner_context}/$(dirname "$file")"
            if [[ -n "$runner_source" ]]; then
                cp "${runner_source}/${file}" "${runner_context}/${file}"
            else
                git -C "$runner_repo" show "${runner_revision}:${file}" > "${runner_context}/${file}"
            fi
        done

        # Copy Dockerfile requirements
        cp -t "${tmp}/dask-gateway" "${CUSTOM_REQ}/layer-cleanup.sh" "${CUSTOM_REQ}/restore-apt.sh" "${CUSTOM_REQ}/dask-scheduler" "${CUSTOM_REQ}/dask-worker"

        # Target environments supported: local and k8s
        localenv="local"
        k8senv="k8s"

        # Build the docker image for each target (local and k8s)
        for env in "$localenv" "$k8senv"; do
            requirements="requirements-${env}"
            # Resolve the full image together, not independently frozen dependency trees.
            # Replace upstream self-references with the matching published packages.
            sed -E "s|^\.(\[[^]]+\])?|dask-gateway\1==${DASK_GATEWAY_TAG}|" \
                dask-gateway/Dockerfile.requirements.in > "${requirements}.in"
            if [[ "$env" == "$localenv" ]]; then
                sed -E "s|^\.(\[[^]]+\])?|dask-gateway-server\1==${DASK_GATEWAY_TAG}|" \
                    dask-gateway-server/Dockerfile.requirements.in >> "${requirements}.in"
                printf '\ndask-gateway-server[local,kubernetes]==%s\n' "$DASK_GATEWAY_TAG" >> "${requirements}.in"
            fi
            printf '\ndask==%s\ndistributed==%s\nbokeh>=3.1.0\njupyter-server-proxy\n-r eopf-runner/rs_dpr_service/runner/runner_requirements.txt\n' \
                "$dask_tag" "$dask_tag" >> "${requirements}.in"
            docker run --rm \
                --volume="$PWD":/opt/dask-base \
                --workdir=/opt/dask-base \
                --user=root \
                "ghcr.io/rs-python/python:${python_version}-slim-bookworm" \
                sh -c 'pip install pip-tools==7.* && pip-compile --allow-unsafe --strip-extras --upgrade "$@"' \
                sh "--output-file=${requirements}.txt" "${requirements}.in"

            target="ghcr.io/rs-python/dask/dask-gateway:${env}-py${python_version}-${dask_tag}"
            docker build \
                --build-arg "PYTHON_VERSION_BASE=${python_version}" \
                -f "${SCRIPT_DIR}/Dockerfile.dask.${env}" \
                -t "${target}" \
                --progress=plain \
                "${tmp}/dask-gateway"

            # Push the docker image to the registry, if the --push option is specified.
            if [[ "$PUSH" == "true" ]]; then
                docker push "$target"
            fi
        done

    done
fi

###########
# Prefect #
###########

if [[ "$TARGET" == "all" || "$TARGET" == "prefect" ]]; then

    # Checkout the prefect git repository into a local ./tmp folder
    tmp="${SCRIPT_DIR}/tmp/prefect"
    mkdir -p "$tmp"
    cd "$tmp"
    if [[ ! -d prefect ]]; then
    git clone https://github.com/PrefectHQ/prefect.git
    fi
    cd prefect
    git checkout "tags/$PREFECT_TAG"
    git reset --hard

    # NOTE: build the image as in /prefect/.github/workflows/docker-images.yaml

    # For each suffix and extra packages, separated by a ;
    for params in \
        "-k8s;--build-arg PREFECT_EXTRAS=[redis,kubernetes]" \
        ""
    do
        suffix=$(echo "$params" | cut -d ";" -f 1)
        prefect_extras=$(echo "$params" | cut -d ";" -f 2)

        # Add our hosting github organization to the docker image
        target="ghcr.io/rs-python/prefecthq/prefect:${PREFECT_TAG}-py${PYTHON_VERSION}${suffix}"

        # Build the docker image
        prefect_root="${SCRIPT_DIR}/tmp/prefect/prefect"
        docker build \
            --build-arg "PYTHON_VERSION=${PYTHON_VERSION}" \
            --build-arg "NODE_VERSION=$(cat .nvmrc)" \
            $prefect_extras \
            --progress plain \
            -f "${prefect_root}/Dockerfile" \
            -t "$target" \
            "$prefect_root"

        # Push the docker image to the registry, if the --push option is specified.
        if [[ "$PUSH" == "true" ]]; then
            docker push "$target"
        fi
    done
fi
