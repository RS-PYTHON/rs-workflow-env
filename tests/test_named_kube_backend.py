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

"""Tests of the Dask Gateway backend that names the clusters after their label."""

import importlib.util
import re
import sys
from pathlib import Path

import jinja2
import pytest
import yaml
from dask_gateway_server.backends.kubernetes import KubeBackend, KubeClusterConfig
from traitlets.config import Config

APP_DIR = Path(__file__).resolve().parent.parent / "apps" / "dask-gateway"


def load_module():
    """Import the named_kube_backend.py module (its directory name contains a '-', so it isn't a python package)."""
    spec = importlib.util.spec_from_file_location("named_kube_backend", APP_DIR / "named_kube_backend.py")
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backend_module = load_module()

# Cluster name compatible with a DNS-1035 label once prefixed by "dask-" (Service name) and with a label value
CLUSTER_NAME_REGEX = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
CLUSTER_NAME_MAX_LENGTH = 63 - len("dask-")


def check_cluster_name(name: str):
    """Check that the cluster name is valid for Kubernetes and Dask Gateway."""
    assert CLUSTER_NAME_REGEX.match(name), name
    assert len(name) <= CLUSTER_NAME_MAX_LENGTH, name
    assert "." not in name


@pytest.mark.parametrize(
    "label, expected_prefix",
    [
        ("dask-s1ard.userA.latest", "s1ard-usera-latest"),
        ("dask-s3olci.userB.1.2.3", "s3olci-userb-1-2-3"),
        ("dask-staging", "staging"),
        ("dask-l0", "l0"),
        ("MyDaskCluster", "mydaskcluster"),
        ("ghcr.io/rs-python/dask/l0/k8s:latest", "ghcr-io-rs-python-dask-l0-k8s-latest"),
        ("..dask_eopf--mockup__", "eopf-mockup"),
        ("dask", "dask"),
        ("dask-" + "x" * 50, "x" * backend_module.CLUSTER_NAME_PREFIX_MAX_LENGTH),
        ("dask-" + "a" * 39 + ".b", "a" * 39),  # the trailing '-' left by the truncation is removed
    ],
)
def test_make_cluster_name_from_label(label, expected_prefix):
    """The cluster name is the sanitized label followed by a random suffix."""
    name = backend_module.make_cluster_name(label)
    prefix, suffix = name.rsplit("-", 1)
    assert prefix == expected_prefix
    assert re.fullmatch(f"[0-9a-f]{{{backend_module.CLUSTER_NAME_SUFFIX_LENGTH}}}", suffix)
    check_cluster_name(name)


@pytest.mark.parametrize("label", [None, "", "...", "-_-"])
def test_make_cluster_name_without_label(label):
    """Without a usable label, the cluster name is a random uuid, as by default in Dask Gateway."""
    name = backend_module.make_cluster_name(label)
    assert re.fullmatch("[0-9a-f]{32}", name)
    check_cluster_name(name)


def test_make_cluster_name_is_unique():
    """Two clusters with the same label have different names."""
    assert len({backend_module.make_cluster_name("dask-staging") for _ in range(100)}) == 100


@pytest.mark.parametrize(
    "options, expected_prefix",
    [({"cluster_name": "dask-s1ard.userA.latest"}, "s1ard-usera-latest-"), ({}, "")],
)
def test_make_cluster_object(options, expected_prefix):
    """The DaskCluster resource name and labels use the cluster name built from the label."""
    backend = backend_module.NamedKubeBackend(gateway_instance="rs-instance")
    cluster = backend.make_cluster_object("user", options, KubeClusterConfig())

    name = cluster["metadata"]["name"]
    assert name.startswith(expected_prefix)
    check_cluster_name(name)
    assert cluster["metadata"]["labels"] == backend.get_labels(name)
    assert cluster["metadata"]["labels"]["gateway.dask.org/cluster"] == name
    assert cluster["spec"]["username"] == "user"
    assert cluster["spec"]["options"] == options


def test_values_extra_config():
    """
    The values.yaml file, rendered with Jinja as the rs-infra-core app installer does (Ansible template module),
    includes the backend code and makes Dask Gateway use it.
    """
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(APP_DIR),
        trim_blocks=True,  # Ansible default
        undefined=jinja2.ChainableUndefined,  # ignore the inventory variables
        autoescape=False,  # nosec B701: this is a YAML file, not HTML
    )
    values = yaml.safe_load(env.get_template("values.yaml").render())
    extra_config = values["gateway"]["extraConfig"]

    # The chart executes the extraConfig entries in alphabetical order, after setting the default backend class
    config = Config()
    config.DaskGateway.backend_class = "dask_gateway_server.backends.kubernetes.KubeBackend"
    for key in sorted(extra_config):
        exec(compile(extra_config[key], f"<extraConfig.{key}>", "exec"), {"c": config})  # pylint: disable=exec-used

    backend_class = config.DaskGateway.backend_class
    assert backend_class.__name__ == "NamedKubeBackend"
    assert issubclass(backend_class, KubeBackend)
    cluster = backend_class(gateway_instance="rs-instance").make_cluster_object(
        "user",
        {"cluster_name": "dask-staging"},
        KubeClusterConfig(),
    )
    assert cluster["metadata"]["name"].startswith("staging-")
