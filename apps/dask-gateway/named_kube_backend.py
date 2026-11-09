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
Dask Gateway Kubernetes backend that names the clusters after their label.

By default, Dask Gateway names each DaskCluster resource with a random uuid, so the scheduler and worker pods are
named dask-scheduler-<uuid> and dask-worker-<uuid>-<random>. This backend prefixes the name with the cluster
label (the 'cluster_name' option), e.g. the label 'dask-s1ard.userA.latest' gives the pod name
dask-scheduler-s1ard-usera-latest-<12 hex chars>.

This file is included in the gateway.extraConfig of the dask-gateway values.yaml file (Jinja include, at deployment
time), so it is executed in the Dask Gateway configuration file. It must not contain Jinja syntax.
"""

import re
import uuid

from dask_gateway_server.backends.kubernetes import KubeBackend

# The cluster name is used in the 'dask-<name>' Service name, which must be a DNS-1035 label of 63 chars max,
# and in the 'gateway.dask.org/cluster' label value of 63 chars max. It can't contain any '.' because the gateway
# splits the '<namespace>.<name>' full cluster names on the '.' character.
CLUSTER_NAME_PREFIX_MAX_LENGTH = 40
CLUSTER_NAME_SUFFIX_LENGTH = 12


def make_cluster_name(label: str | None) -> str:
    """
    Return a unique and Kubernetes-compliant cluster name from the cluster label.

    Args:
        label: cluster label, i.e. the 'cluster_name' option, e.g. 'dask-s1ard.userA.latest'

    Returns:
        '<prefix>-<random suffix>' where the prefix is the lowercase label with only alphanumeric characters
        and '-', without the leading 'dask-', e.g. 's1ard-usera-latest-0123456789ab'.
        Return a random uuid, as Dask Gateway does by default, if the prefix is empty.
    """
    prefix = re.sub(r"[^a-z0-9]+", "-", (label or "").lower()).strip("-")
    prefix = prefix.removeprefix("dask-")[:CLUSTER_NAME_PREFIX_MAX_LENGTH].rstrip("-")
    if not prefix:
        return uuid.uuid4().hex
    return f"{prefix}-{uuid.uuid4().hex[:CLUSTER_NAME_SUFFIX_LENGTH]}"


class NamedKubeBackend(KubeBackend):
    """Kubernetes backend that names the DaskCluster resources (and so the pods) after the cluster label."""

    def make_cluster_object(self, username, options, config):
        """Create the DaskCluster resource, named after the 'cluster_name' option."""
        cluster = super().make_cluster_object(username, options, config)
        name = make_cluster_name(options.get("cluster_name"))
        cluster["metadata"]["name"] = name
        cluster["metadata"]["labels"] = self.get_labels(name)
        return cluster
