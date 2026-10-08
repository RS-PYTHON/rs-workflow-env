#!/usr/bin/env python3

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

"""Build the Dask EOPF/DPR Docker images for cluster and local modes."""

import argparse
import itertools
import subprocess  # nosec
import sys
from dataclasses import dataclass
from pathlib import Path

# NOTE: run "./build_dask_eopf.py -h" to display help.

# This script directory
THIS_DIR = Path(__file__).parent

DOCKER_SCRIPTS = THIS_DIR.parent / "scripts"

########
# Init #
########


@dataclass
class Image:
    """Docker image information. Each Docker image is specific to a single processor."""

    # Versions used by the processor
    python_version: str
    dask_version: str

    # Docker image name for cluster usage (registry)
    k8s_name: str

    # Docker image name for local mode usage (registry)
    local_name: str = ""

    # Name of the LocalCluster image (for debugging)
    local_cluster_name: str = ""

    # This is used mainly to identify the files that are specific to the processor:
    # requirements-${IMAGE2BUILD}.txt, post-install-${IMAGE2BUILD}.sh, ...
    # But it's not used in the name of the docker image itself.
    image2build: str = ""


# All possible processor images
all_procs = {
    # Image for CPM >=2.7.0,<3
    "cpm2": Image(
        python_version="3.11.7",
        dask_version="2026.1.2",
        k8s_name="ghcr.io/rs-python/dask/cpm2/k8s",
        local_name="ghcr.io/rs-python/dask/cpm2/local",
        local_cluster_name="ghcr.io/rs-python/dask/cpm2/localcluster",
        image2build="dask-cpm2",
    ),
    # Image for CPM >=3
    # WARNING: Up to first official relase, release-candidate revision is hard-coded in requirements-dask-cpm3.txt
    "cpm3": Image(
        python_version="3.13.12",
        dask_version="2026.3.0",
        k8s_name="ghcr.io/rs-python/dask/cpm3/k8s",
        local_name="ghcr.io/rs-python/dask/cpm3/local",
        local_cluster_name="ghcr.io/rs-python/dask/cpm3/localcluster",
        image2build="dask-cpm3",
    ),
    "l0": Image(
        python_version="3.11.7",
        dask_version="2024.5.2",
        k8s_name="ghcr.io/rs-python/dask/l0/k8s",
        local_name="ghcr.io/rs-python/dask/l0/local",
        local_cluster_name="ghcr.io/rs-python/dask/l0/localcluster",
        image2build="dask-l0",
    ),
    "s1ard": Image(
        python_version="3.13.12",
        dask_version="2026.3.0",
        k8s_name="ghcr.io/rs-python/dask/s1ard/k8s",
        local_name="ghcr.io/rs-python/dask/s1ard/local",
        local_cluster_name="ghcr.io/rs-python/dask/s1ard/localcluster",
        image2build="dask-s1ard",
    ),
    "s3olci": Image(
        python_version="3.11.7",
        dask_version="2024.5.2",
        k8s_name="ghcr.io/rs-python/dask/s3olci/k8s",
        local_name="ghcr.io/rs-python/dask/s3olci/local",
        local_cluster_name="ghcr.io/rs-python/dask/s3olci/localcluster",
        image2build="dask-s3olci",
    ),
}

######################
# PARSE COMMAND LINE #
######################

parser = argparse.ArgumentParser(
    description="Build the Dask EOPF/DPR Docker images",
    epilog=f"Example: {sys.argv[0]} l0 -t=*** -d=feat-rspyxxx --push",
)

# Positional argument
parser.add_argument(
    "proc",
    choices=["all"] + list(all_procs.keys()),
    help="Processor to build",
)

# Named arguments
parser.add_argument(
    "-t",
    "--gitlab_eopf_token",
    required=True,
    help="See: 'https://gitlab.eopf.copernicus.eu/help/user/profile/personal_access_tokens'",
)
parser.add_argument(
    "-l",
    "--local",
    action="store_true",
    help="Build the Dask local image for local deployment",
)
parser.add_argument(
    "-c",
    "--local_cluster",
    action="store_true",
    help="Build the Dask LocalCluster image for local debugging",
)
parser.add_argument(
    "-d",
    "--docker_tags",
    default="latest",
    help="Docker tag(s) to use, as a comma-separated list e.g. 'tag1,tag2' (default: latest)",
)
parser.add_argument(
    "--labels",
    default="",
    help="List of docker label lines as 'key=value'",
)
parser.add_argument(
    "--push",
    action="store_true",
    help="Push image to Docker registry",
)

args = parser.parse_args()

# Build label options: "--label key=value" for each line
labels = []
for line in args.labels.split("\n"):
    if line:
        labels += ["--label", line]

######################
# BUILD DOCKER IMAGE #
######################

# Build all images ?
build_all = args.proc == "all"

# Nominal case: we build a single processor with or without local cluster
if not build_all:
    procs_to_build = [[args.proc, args.local_cluster]]

# Build all the processors, with and without local cluster
else:
    procs_to_build = list(itertools.product(all_procs.keys(), [False, True]))  # type: ignore[arg-type]

for proc, local_cluster in procs_to_build:

    def get_dockerfile(localcluster) -> Path:
        """Return Dockerfile to use"""
        if localcluster:
            return THIS_DIR / "Dockerfile.dask-eopf-localcluster"
        # default
        return THIS_DIR / "Dockerfile.dask-eopf"

    def run_command(cmd: list[str]):
        """Run command line"""
        print(f"""
#########
# BUILD #
#########

{' '.join(cmd)}
""")

        if code := subprocess.run(  # nosec
            cmd,
            check=False,
            env={"GITLAB_EOPF_TOKEN": args.gitlab_eopf_token},
        ).returncode:
            joined = "' '"
            raise RuntimeError(
                f"Error running command:\n'{joined.join(cmd)}'\nReturn code: {code}",
            )

    # Docker image information
    image: Image = all_procs[proc]

    # Docker image name
    if local_cluster:
        registry = image.local_cluster_name
    elif args.local:
        registry = image.local_name
    else:
        registry = image.k8s_name

    command = [
        "docker",
        "build",
        "--build-arg",
        f"IMAGE2BUILD={image.image2build}",
        "--secret",
        "id=GITLAB_EOPF_TOKEN",
        "-f",
        str(get_dockerfile(local_cluster)),
    ]
    for tag in args.docker_tags.split(","):
        if tag:
            command += ["-t", f"{registry}:{tag}"]
    command += [
        "--progress=plain",
        "--build-context",
        f"docker-scripts={str(DOCKER_SCRIPTS)}",
        str(THIS_DIR),
        "--build-arg", f"PYTHON_VERSION={image.python_version}",
        "--build-arg", f"DASK_TAG={image.dask_version}"
    ]

    # Extract base image used from the target name (k8s or local) and add it as an argument
    if not local_cluster:
        command += ["--build-arg", f"BASE_IMAGE_TARGET={registry.rsplit('/', 1)[1]}"]

    # Build image
    run_command(command + labels)

    # Push to registry
    if args.push:
        for tag in args.docker_tags.split(","):
            if tag:
                run_command(
                    [
                        "/bin/sh",
                        "-c",
                        f"docker login https://ghcr.io/v2/rs-python && docker push '{registry}:{tag}'",
                    ],
                )
