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
#!/usr/bin/env python
import os
import shlex
import sys

# Copy saved files into the user's HOME directory.
# When Studio is executed by Kubernetes a volume is used to make
# the HOME directory persitent. The first time the user starts the
# Jupyter environment,
# the volume is empty == the HOME directory is empty.
#
# Existing files are not overwritten by the script.
os.system("/opt/eopf/bin/initializeHomeDirectory.bash")

# Entrypoint is start.sh
command = ["jupyterhub-singleuser"]

# set default ip to 0.0.0.0
if "--ip=" not in os.environ.get("NOTEBOOK_ARGS", ""):
    command.append("--ip=0.0.0.0")

# Append any optional NOTEBOOK_ARGS we were passed in.
# This is supposed to be multiple args passed on to the notebook command,
# so we split it correctly with shlex
if "NOTEBOOK_ARGS" in os.environ:
    command += shlex.split(os.environ["NOTEBOOK_ARGS"])

# Pass any other args we have been passed through
command += sys.argv[1:]

# Execute the command!
print("Executing: " + " ".join(command))
os.execvp(command[0], command)
