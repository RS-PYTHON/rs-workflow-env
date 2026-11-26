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

"""Tests of runner staging in the Dask base image build."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("local_source", [True, False], ids=["local-checkout", "remote-ref"])
def test_dask_build_stages_runner_without_changing_gateway_workdir(tmp_path, local_source):
    root = Path(__file__).resolve().parents[1]
    docker = tmp_path / "docker"
    shutil.copytree(root / "docker" / "base", docker / "base", ignore=shutil.ignore_patterns("tmp"))
    shutil.copytree(root / "docker" / "scripts", docker / "scripts")
    gateway = docker / "base" / "tmp" / "dask" / "py3.13.18" / "dask-gateway"
    for component in ("dask-gateway", "dask-gateway-server"):
        directory = gateway / component
        directory.mkdir(parents=True)
        (directory / "Dockerfile.requirements.txt").write_text("dask==0\nfsspec==0\n", encoding="utf-8")
        requirement = ".\nbokeh\nnumpy\n" if component == "dask-gateway" else ".[kubernetes]\n"
        (directory / "Dockerfile.requirements.in").write_text(requirement, encoding="utf-8")

    source = tmp_path / "runner-source"
    relative_files = (
        "__init__.py",
        "runner/__init__.py",
        "runner/eopf_runner.py",
        "runner/runner_requirements.txt",
        "utils/__init__.py",
        "utils/settings.py",
        "utils/logging.py",
        "utils/init_opentelemetry.py",
    )
    for relative in relative_files:
        path = source / "rs_dpr_service" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# runner source\n", encoding="utf-8")
    (source / "do-not-copy.txt").write_text("unrelated", encoding="utf-8")

    commands = tmp_path / "bin"
    commands.mkdir()
    stubs = {
        "git": """#!/bin/sh
printf '%s\\n' "$*" >> "$GIT_CALLS"
if [ "$1" = clone ]; then
    mkdir -p "$4/.git"
elif [ "$1" = -C ] && [ "$3" = rev-parse ]; then
    echo runner-commit
elif [ "$1" = -C ] && [ "$3" = show ]; then
    cat "$RUNNER_FIXTURE_SOURCE/${4#*:}"
fi
""",
        "yq": '#!/bin/sh\necho \'{"deps":[{"python_version":"3.13.18","dask_version":"2026.7.1"}]}\'\n',
        "jq": """#!/usr/bin/env python3
import json, sys
value = json.load(sys.stdin)
expression = sys.argv[-1]
if expression == '.deps[]':
    print(json.dumps(value['deps'][0], separators=(',', ':')))
else:
    print(value[expression.strip('.\"')])
""",
        "docker": """#!/bin/sh
printf '%s\\n' "$*" >> "$DOCKER_CALLS"
""",
    }
    for name, content in stubs.items():
        path = commands / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)
    calls = tmp_path / "docker-calls"
    git_calls = tmp_path / "git-calls"
    result = subprocess.run(
        ["bash", str(docker / "base" / "build-base-images.sh"), "--target", "dask"],
        env={
            **os.environ,
            "PATH": f"{commands}{os.pathsep}{os.environ['PATH']}",
            "RSPY_RUNNER_SOURCE": str(source) if local_source else "",
            "RSPY_RUNNER_REF": "runner-ref",
            "RUNNER_FIXTURE_SOURCE": str(source),
            "DOCKER_CALLS": str(calls),
            "GIT_CALLS": str(git_calls),
        },
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    staged = gateway / "eopf-runner" / "rs_dpr_service"
    assert sorted(str(path.relative_to(staged)) for path in staged.rglob("*") if path.is_file()) == sorted(
        relative_files,
    )
    for target in ("local", "k8s"):
        requirements = (gateway / f"requirements-{target}.in").read_text()
        assert "dask-gateway==2026.3.0\n" in requirements
        assert "dask==2026.7.1\ndistributed==2026.7.1\n" in requirements
        assert "-r eopf-runner/rs_dpr_service/runner/runner_requirements.txt\n" in requirements
        assert "numpy\n" in requirements
        assert "fsspec==0" not in requirements
        if target == "local":
            assert "dask-gateway-server[kubernetes]==2026.3.0\n" in requirements
            assert "dask-gateway-server[local,kubernetes]==2026.3.0\n" in requirements
        else:
            assert "dask-gateway-server" not in requirements
    resolutions = [line for line in calls.read_text().splitlines() if line.startswith("run ")]
    assert len(resolutions) == 2
    for target in ("local", "k8s"):
        assert any(
            f"--output-file=requirements-{target}.txt requirements-{target}.in" in line for line in resolutions
        )
    builds = [line for line in calls.read_text().splitlines() if line.startswith("build ")]
    assert len(builds) == 2
    assert all(line.endswith(str(gateway)) for line in builds)
    assert any("Dockerfile.dask.local" in line for line in builds)
    assert any("Dockerfile.dask.k8s" in line for line in builds)
    if not local_source:
        assert "fetch --depth=1 origin runner-ref" in git_calls.read_text()
        assert git_calls.read_text().count(" show runner-commit:") == len(relative_files)
