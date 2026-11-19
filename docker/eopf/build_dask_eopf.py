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
import os
import subprocess  # nosec
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

# NOTE: run "./build_dask_eopf.py -h" to display help.

# This script directory
THIS_DIR = Path(__file__).parent

DOCKER_SCRIPTS = THIS_DIR.parent / "scripts"

# Default Docker registry of the images
DEFAULT_REGISTRY = "ghcr.io/rs-python"

# Environment variables that give access to the confidential GMV GitLab repositories.
# They are passed to the docker build as secrets, never as build arguments, so they are not stored in the image.
GMV_SECRETS = ["GMV_GITLAB_URL", "GMV_GITLAB_TOKEN", "CRISTAL_L0_PROJECT_ID", "CRISTAL_COMMON_PROJECT_ID"]

# Optional IP address of the GMV GitLab, while its domain name is not in the DNS. When it is set, the build resolves
# the GitLab host name to this address and the GitLab certificate is not verified.
GMV_GITLAB_IP = "GMV_GITLAB_IP"

########
# Init #
########


@dataclass
class Image:
    """Docker image information. Each Docker image is specific to a single processor."""

    # Versions used by the processor
    python_version: str
    dask_version: str

    # This is used mainly to identify the files that are specific to the processor:
    # requirements-${IMAGE2BUILD}.txt, post-install-${IMAGE2BUILD}.sh, ...
    # But it's not used in the name of the docker image itself.
    image2build: str

    # Confidential processor: its sources are not public and its image must not be pushed to the
    # public registry. It needs the GMV_SECRETS environment variables and an explicit --registry.
    # It is not built with the "all" option.
    confidential: bool = False

    def name(self, proc_name: str, prefix: str, target: str) -> str:
        """Docker image name, e.g. ghcr.io/rs-python/dask/<proc>/<target> with target=k8s, local or localcluster"""
        return f"{prefix}/dask/{proc_name}/{target}"


# All possible processor images
all_procs = {
    # Image for CPM >=3
    # WARNING: Up to first official relase, release-candidate revision is hard-coded in requirements-dask-cpm3.txt
    "cpm3": Image(
        python_version="3.13.18",
        dask_version="2026.7.1",
        image2build="dask-cpm3",
    ),
    "l0": Image(
        python_version="3.13.18",
        dask_version="2026.7.1",
        image2build="dask-l0",
    ),
    "s1ard": Image(
        python_version="3.13.18",
        dask_version="2026.7.1",
        image2build="dask-s1ard",
    ),
    "s3olci": Image(
        python_version="3.13.18",
        dask_version="2026.7.1",
        image2build="dask-s3olci",
    ),
    # CRISTAL L0 processor, installed from the GMV GitLab
    "cristal-l0": Image(
        python_version="3.13.18",
        dask_version="2026.7.1",
        image2build="dask-cristal-l0",
        confidential=True,
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
    "--dpr_service_tags",
    default="latest",
    help="For the LocalCluster image: rs-dpr-service base image tag(s) to test, as a comma-separated list "
    "e.g. 'my-branch-name,latest'. The first existing tag is used (default: latest)",
)
parser.add_argument(
    "--labels",
    default="",
    help="List of docker label lines as 'key=value'",
)
parser.add_argument(
    "-r",
    "--registry",
    default=DEFAULT_REGISTRY,
    help=f"Docker registry and namespace of the built images (default: {DEFAULT_REGISTRY}). "
    "Mandatory for the confidential processors, that must not be pushed to the default registry",
)
parser.add_argument(
    "--push",
    action="store_true",
    help="Push image to Docker registry",
)

args = parser.parse_args()
registry_prefix = args.registry.rstrip("/")

if (args.proc != "all") and all_procs[args.proc].confidential:
    if registry_prefix == DEFAULT_REGISTRY:
        parser.error(f"'{args.proc}' is confidential: set --registry to a private registry")
    if missing := [var for var in GMV_SECRETS if not os.environ.get(var)]:
        parser.error(f"'{args.proc}' is confidential: missing environment variable(s) {', '.join(missing)}")

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
    procs_to_build: list[tuple[str, bool]] = [(args.proc, args.local_cluster)]

# Build all the processors, with and without local cluster
else:
    procs_to_build = list(
        itertools.product(
            [name for name, proc_image in all_procs.items() if not proc_image.confidential],
            [False, True],
        ),
    )

for proc, local_cluster in procs_to_build:

    def get_dockerfile(localcluster) -> Path:
        """Return Dockerfile to use"""
        if localcluster:
            return THIS_DIR / "Dockerfile.dask-eopf-localcluster"
        # default
        return THIS_DIR / "Dockerfile.dask-eopf"

    def get_dpr_service_tag(proc_image: Image) -> str:
        """Return the first existing rs-dpr-service image tag from --dpr_service_tags"""
        dpr_image = f"ghcr.io/rs-python/rs-dpr-service_py{proc_image.python_version}-{proc_image.dask_version}"
        for dpr_tag in args.dpr_service_tags.split(","):
            if (
                dpr_tag
                and subprocess.run(  # nosec
                    ["docker", "manifest", "inspect", f"{dpr_image}:{dpr_tag}"],
                    check=False,
                    capture_output=True,
                ).returncode
                == 0
            ):
                print(f"Use '{dpr_image}:{dpr_tag}'")
                return dpr_tag
        raise RuntimeError(f"Could not find any of the tags '{args.dpr_service_tags}' for the image '{dpr_image}'")

    def run_command(cmd: list[str], secret_env: dict[str, str]):
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
            env={"GITLAB_EOPF_TOKEN": args.gitlab_eopf_token, **secret_env},
        ).returncode:
            joined = "' '"
            raise RuntimeError(
                f"Error running command:\n'{joined.join(cmd)}'\nReturn code: {code}",
            )

    # Docker image information
    image: Image = all_procs[proc]

    # Docker image name
    if local_cluster:
        registry = image.name(proc, registry_prefix, "localcluster")
    elif args.local:
        registry = image.name(proc, registry_prefix, "local")
    else:
        registry = image.name(proc, registry_prefix, "k8s")

    # Secrets of the confidential processors, read from the environment by "docker build --secret"
    secrets = {var: os.environ[var] for var in GMV_SECRETS} if image.confidential else {}
    if image.confidential and os.environ.get(GMV_GITLAB_IP):
        secrets[GMV_GITLAB_IP] = os.environ[GMV_GITLAB_IP]

    command = [
        "docker",
        "build",
        "--build-arg",
        f"IMAGE2BUILD={image.image2build}",
        "--secret",
        "id=GITLAB_EOPF_TOKEN",
    ]
    for var in secrets:
        command += ["--secret", f"id={var},env={var}"]
    # Add the GMV GitLab to /etc/hosts of the build containers
    if GMV_GITLAB_IP in secrets:
        command += ["--add-host", f"{urlparse(secrets['GMV_GITLAB_URL']).hostname}={secrets[GMV_GITLAB_IP]}"]
    command += [
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

    # The LocalCluster image is built from the rs-dpr-service image
    if local_cluster:
        command += ["--build-arg", f"DPR_SERVICE_TAG={get_dpr_service_tag(image)}"]

    # Extract base image used from the target name (k8s or local) and add it as an argument
    if not local_cluster:
        command += ["--build-arg", f"BASE_IMAGE_TARGET={registry.rsplit('/', 1)[1]}"]

    # Build image
    run_command(command + labels, secrets)

    # Push to registry
    if args.push:
        for tag in args.docker_tags.split(","):
            if tag:
                run_command(
                    [
                        "/bin/sh",
                        "-c",
                        f"docker login '{registry_prefix.split('/', 1)[0]}' && docker push '{registry}:{tag}'",
                    ],
                    secrets,
                )
