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

PYTHON_VERSION=3.13.12
DASK_GATEWAY_TAG=2026.3.0
PREFECT_TAG=3.7.5

####################
# Retrieve options #
####################

PUSH=false
TARGET="all"

help() {
    echo "Usage: $0 [-p|--push] [-t|--target <target>]"
    echo "Target can be one of: all, python, dask, prefect"
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

        # Refreeze Dockerfile.requirements.txt files based on Dockerfile.requirements.in
        # as in https://github.com/dask/dask-gateway/blob/main/.github/workflows/refreeze-dockerfile-requirements-txt.yaml#L34
        for matrix_image in "dask-gateway" "dask-gateway-server"; do
            (\
                cd "${matrix_image}" && \
                docker run --rm \
                    --env=DASK_GATEWAY_SERVER__NO_PROXY=1 \
                    --volume="$PWD":/opt/${matrix_image} \
                    --workdir=/opt/${matrix_image} \
                    --user=root \
                    "ghcr.io/rs-python/python:${python_version}-slim-bookworm" \
                    sh -c 'pip install pip-tools==7.* && pip-compile --allow-unsafe --strip-extras --upgrade --output-file=Dockerfile.requirements.txt Dockerfile.requirements.in' \
            )
            req=$(realpath "${matrix_image}/Dockerfile.requirements.txt")

            # Force the dask versions (in dask-gateway)
            sed -i "s|dask==.*|dask==${dask_tag}|g" "$req"
            sed -i "s|distributed==.*|distributed==${dask_tag}|g" "$req"
            sed -i "s|fsspec==.*|fsspec|g" "$req"

            # Comment the line that installs dask-gateway-server from sources (in dask-gateway-server).
            # We install it with pip from our Dockerfile instead.
            sed -i "s|\(^\s*dask-gateway-server\)|# \1|g" "$req"
        done

        # Copy Dockerfile requirements
        cp -t "${tmp}/dask-gateway" "${CUSTOM_REQ}/layer-cleanup.sh" "${CUSTOM_REQ}/restore-apt.sh" "${CUSTOM_REQ}/dask-scheduler" "${CUSTOM_REQ}/dask-worker"

        # Target environments supported: local and k8s
        localenv="local"
        k8senv="k8s"

        # Build the docker image for each target (local and k8s)
        for env in "$localenv" "$k8senv"; do
            target="ghcr.io/rs-python/dask/dask-gateway:${env}-py${python_version}-${dask_tag}"
            docker build \
                --build-arg "PYTHON_VERSION_BASE=${python_version}" \
                --build-arg "DASK_TAG=${dask_tag}" \
                --build-arg "DASK_GATEWAY_TAG=${DASK_GATEWAY_TAG}" \
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
