#!/bin/bash
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

set -euo pipefail

APPS=rs-workflow-env/apps

# Lower the CPU requests
sed -i 's!: 0.1!: 0.001!g' "${APPS}/jupyterhub/values.yaml"
sed -i 's!: 500m!: 1m!g' "${APPS}/prefect3-server/values.yaml"
sed -i 's!: "150m"!: "1m"!g' \
  "${APPS}/prefect3-worker-integrated/values.yaml" \
  "${APPS}/prefect3-worker-sandbox/values.yaml" \
  "${APPS}/prefect3-worker-monitoring/values.yaml"

# Lower jupyter specs
# yq mangles unquoted {{ }} Jinja2 expressions (it parses them as YAML flow
# mappings and rewrites them as complex-key notation), which breaks kustomize's
# YAML-to-JSON conversion later. Escape them as plain strings before yq runs,
# then restore them afterwards.
sed -i 's/{{/JINJA2OPEN/g; s/}}/JINJA2CLOSE/g' "${APPS}/jupyterhub/values.yaml"
yq -i '.scheduling.userScheduler.replicas = 1' "${APPS}/jupyterhub/values.yaml"
yq -i '.singleuser.profileList = [ .singleuser.profileList[0] ]' "${APPS}/jupyterhub/values.yaml"
sed -i 's/JINJA2OPEN/{{/g; s/JINJA2CLOSE/}}/g' "${APPS}/jupyterhub/values.yaml"

# Lower prefect specs
yq -i '.worker.replicaCount = 1' "${APPS}/prefect3-worker-sandbox/values.yaml"
yq -i '.worker.replicaCount = 1' "${APPS}/prefect3-worker-monitoring/values.yaml"
yq -i '.worker.replicaCount = 1' "${APPS}/prefect3-worker-integrated/values.yaml"
