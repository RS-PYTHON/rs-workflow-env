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

"""
Tests of the HTTP route of the Dask dashboards: the dashboard links displayed by the rs-demo notebooks must be routed
to the Dask Gateway.
"""

import re

import pytest
from dask_gateway_server.backends.kubernetes import KubeClusterConfig
from dask_gateway_server.models import Cluster, ClusterStatus
from utils import APPS_DIR, DASK_GATEWAY_DIR, load_named_kube_backend, render_yaml

backend_module = load_named_kube_backend()


def inventory(namespace: str | None) -> dict:
    """Return the inventory variables that set the namespace of the notebook clusters, if any."""
    if namespace is None:
        return {}
    return {"jupyterhub": {"ops": {"services": {"daskgateway": {"namespace": namespace}}}}}


def path_regexes(namespace: str | None) -> list[re.Pattern]:
    """Return the path regular expressions of the HTTPRoute (the dashboards are routed by regex only)."""
    httproute = render_yaml(DASK_GATEWAY_DIR, "httproute.yaml", **inventory(namespace))
    matches = [match for rule in httproute["spec"]["rules"] for match in rule["matches"]]
    assert matches
    assert {match["path"]["type"] for match in matches} == {"RegularExpression"}
    return [re.compile(match["path"]["value"]) for match in matches]


def is_routed(path: str, namespace: str | None = None) -> bool:
    """
    Return True if the HTTPRoute sends this URL path to the Dask Gateway, when the namespace of the notebook clusters
    is set to this value in the inventory (None to use the default value).
    """
    return any(regex.fullmatch(path) for regex in path_regexes(namespace))


def dashboard_path(namespace: str, label: str | None) -> str:
    """
    Return the dashboard URL path of a new cluster, as Dask Gateway builds it: the cluster name of the backend, the
    full name '<namespace>.<cluster name>' of the KubeBackend, and the dashboard link of the gateway server.
    The notebooks replace the gateway address of this link by the public address dash-dask.<domain>.
    """
    backend = backend_module.NamedKubeBackend(gateway_instance="rs-instance")
    config = KubeClusterConfig(namespace=namespace)
    obj = backend.make_cluster_object("user", {"cluster_name": label}, config)
    obj["metadata"]["namespace"] = config.namespace  # set by the Kubernetes API when the object is created
    cluster = Cluster(
        name=backend.get_cluster_name(obj),
        username="user",
        token="token",
        options=obj["spec"]["options"],
        config=obj["spec"]["config"],
        status=ClusterStatus.RUNNING,
        dashboard_address="http://dask-dashboard:8787",
    )
    return cluster.to_dict()["dashboard_route"]


@pytest.mark.parametrize(
    "inventory_namespace, cluster_namespace",
    [
        (None, "processing"),  # default namespace of the notebook clusters
        ("processing-cs", "processing-cs"),  # e.g. a second Dask Gateway deployment
        (None, "dask-gateway"),  # staging cluster of rs-server-deployment
        ("processing-cs", "dask-gateway"),
    ],
)
@pytest.mark.parametrize(
    "label",
    [
        # Labels of the rs-demo notebooks: '<processor>.<user>.<docker tag>'
        "dask-s1ard.userA.latest",
        "dask-s3olci.suberti.latest",
        "dask-l0.user_B.1.2.3",
        "dask-eopf-mockup.userC.v1.0a16",
        "dask-cpm3.user-d." + "x" * 60,
        # Staging cluster of rs-server-deployment
        "dask-staging",
        # No label: random uuid
        None,
    ],
)
def test_dashboard_links_are_routed(inventory_namespace, cluster_namespace, label):
    """The dashboard links of the clusters, and their pages and resources, are routed to the Dask Gateway."""
    status = dashboard_path(cluster_namespace, label)
    assert re.fullmatch(rf"/clusters/{cluster_namespace}\.[-a-z0-9]+/status", status), status
    assert is_routed(status, inventory_namespace), status
    prefix = status.removesuffix("status")
    for page in ["workers", "individual-plots.json", "statics/css/base.css", "individual-task-stream"]:
        assert is_routed(prefix + page, inventory_namespace), prefix + page


@pytest.mark.parametrize(
    "inventory_namespace, cluster_namespace",
    [(None, "processing-cs"), (None, "default"), ("processing-cs", "processing"), ("processing", "processing-cs")],
)
def test_dashboard_links_of_other_namespaces_are_not_routed(inventory_namespace, cluster_namespace):
    """The dashboards of the clusters of other namespaces, e.g. of another Dask Gateway deployment, are not routed."""
    assert not is_routed(dashboard_path(cluster_namespace, "dask-s1ard.userA.latest"), inventory_namespace)


@pytest.mark.parametrize("inventory_namespace, expected", [(None, "processing"), ("processing-cs", "processing-cs")])
def test_notebooks_namespace(inventory_namespace, expected):
    """The notebooks create their clusters in the namespace routed by the HTTPRoute."""
    values = render_yaml(APPS_DIR / "jupyterhub", "values.yaml", **inventory(inventory_namespace))
    namespace = values["singleuser"]["extraEnv"]["DASK_GATEWAY_NAMESPACE"]
    assert namespace == expected
    assert is_routed(f"/clusters/{namespace}.s1ard-usera-latest-0123456789ab/status", inventory_namespace)


def test_dashboard_link_example():
    """A real dashboard link of the ops platform is routed."""
    assert is_routed("/clusters/processing.s3olci-suberti-latest-bef5cc6d8d0e/status")


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/clusters/",
        "/clusters/processing/status",  # no cluster name
        "/clusters/processing.s3olci-suberti-latest-bef5cc6d8d0e",  # no dashboard page
        "/clusters/.s3olci-suberti-latest-bef5cc6d8d0e/status",
        "/clusters/processing./status",
        "/clusters/processing.s3olci.suberti/status",
        "/clusters/Processing.s3olci-suberti-latest-bef5cc6d8d0e/status",
        "/api/v1/clusters/",  # the Dask Gateway API is not exposed by this route
        "/api/v1/clusters/processing.s3olci-suberti-latest-bef5cc6d8d0e",
        "/services/dask-gateway/api/v1/clusters/",
    ],
)
def test_other_paths_are_not_routed(path):
    """Only the cluster dashboards are routed, not the Dask Gateway API."""
    assert not is_routed(path)
