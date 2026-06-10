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

set -euo pipefail
set -x

PROJ_CDN_URL="https://cdn.proj.org"
PROJ_LOCAL_DIR="/usr/local/lib/python3.13/site-packages/pyproj/proj_dir/share/proj"

# Download the required grid files
# shellcheck disable=SC2043
for grid_filename in us_nga_egm08_25.tif ; do
  curl -fLs --proto '=https' --proto-redir '=https' "${PROJ_CDN_URL}/${grid_filename}" -o "${PROJ_LOCAL_DIR}/${grid_filename}"
done
