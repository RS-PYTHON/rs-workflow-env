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

set -e

# Run home directory initialization if script exists
if [[ -x /opt/eopf/bin/initializeHomeDirectory.bash ]]; then
    /opt/eopf/bin/initializeHomeDirectory.bash
fi

# If started by JupyterHub (JUPYTERHUB_API_TOKEN is present), start jupyterhub-singleuser
if [[ -n "${JUPYTERHUB_API_TOKEN}" ]]; then
    exec jupyterhub-singleuser "$@"
else
    # Otherwise launch standalone JupyterLab
    exec jupyter lab --ip=0.0.0.0 "$@"
fi
