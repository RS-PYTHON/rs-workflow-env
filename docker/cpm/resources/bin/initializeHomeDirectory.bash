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

USER_HOME="${HOME:-/home/rspy}"
EOPF_HOME=/opt/eopf

copy_file() {
  if [ -f "${DEST}" ] ; then
    echo "${DEST} already exists"
  elif [ -f "${SRC}" ] ; then
    echo "${DEST} does not exist. Copying file from ${SRC}"
    DEST_DIR=$(dirname "${DEST}")
    if [ ! -d "${DEST_DIR}" ] ; then
      mkdir --parents "${DEST_DIR}" 2>/dev/null || true
    fi
    cp "${SRC}" "${DEST}" 2>/dev/null || true
  fi
}

# .bash_logout
SRC=${EOPF_HOME}/.bash_logout
DEST=${USER_HOME}/.bash_logout
copy_file

# .bashrc
SRC=${EOPF_HOME}/.bashrc
DEST=${USER_HOME}/.bashrc
copy_file

# .profile
SRC=${EOPF_HOME}/.profile
DEST=${USER_HOME}/.profile
copy_file

# README.md
SRC=${EOPF_HOME}/README.md
DEST=${USER_HOME}/README.md
copy_file

# .conda/environments.txt
SRC=${EOPF_HOME}/.conda/environments.txt
DEST=${USER_HOME}/.conda/environments.txt
copy_file

# .jupyter/jupyter_notebook_config.py
SRC=${EOPF_HOME}/.jupyter/jupyter_notebook_config.py
DEST=${USER_HOME}/.jupyter/jupyter_notebook_config.py
copy_file

# .s3cfg
SRC=${EOPF_HOME}/aws/.s3cfg
DEST=${USER_HOME}/.s3cfg
copy_file

# Initialize the JupyterLab default workspace to display the README.md file
STUDIO_DEFAULT_WORKSPACE=${EOPF_HOME}/jupyterlab/default.jupyterlab-workspace
USER_DEFAULT_WORKSPACE=${USER_HOME}/.jupyter/lab/workspaces/default-*.jupyterlab-workspace
if ls ${USER_DEFAULT_WORKSPACE} 1> /dev/null 2>&1; then
  echo "JupyterLab default workspace found in ${USER_HOME}/.jupyter/lab/workspaces"
elif [ -f "${STUDIO_DEFAULT_WORKSPACE}" ]; then
  echo "JupyterLab default workspace not found in ${USER_HOME}/.jupyter/lab/workspaces"
  echo "Importing JupyterLab default workspace from ${STUDIO_DEFAULT_WORKSPACE}"
  jupyter lab workspaces import "${STUDIO_DEFAULT_WORKSPACE}" 2>/dev/null || true
fi

# Set JupyterLab notification settings, if the file does not already exist
STUDIO_NOTIFICATION_SETTINGS=${EOPF_HOME}/jupyterlab/notification.jupyterlab-settings
USER_NOTIFICATION_SETTINGS=${USER_HOME}/.jupyter/lab/user-settings/\@jupyterlab/apputils-extension/notification.jupyterlab-settings
if ls ${USER_NOTIFICATION_SETTINGS} 1> /dev/null 2>&1; then
  echo "JupyterLab notification settings file found in ${USER_HOME}/.jupyter/lab/user-settings/\@jupyterlab/apputils-extension/"
elif [ -f "${STUDIO_NOTIFICATION_SETTINGS}" ]; then
  echo "JupyterLab notification settings not found in ${USER_HOME}/.jupyter/lab/user-settings/\@jupyterlab/apputils-extension/"
  echo "Applying JupyterLab default notification settings from ${STUDIO_NOTIFICATION_SETTINGS}"
  SRC=${STUDIO_NOTIFICATION_SETTINGS}
  DEST=${USER_NOTIFICATION_SETTINGS}
  copy_file
  jupyter labextension disable "@jupyterlab/apputils-extension:announcements" 2>/dev/null || true
fi

# Link CPM test data if directory exists
if [ -d "/mnt/test-data" ]; then
  if [ ! -e "${USER_HOME}/test-data" ]; then
    echo "Linking /mnt/test-data to ${USER_HOME}/test-data"
    ln -s /mnt/test-data "${USER_HOME}/test-data" 2>/dev/null || true
  fi
  if [ -d "/home/jovyan" ] && [ ! -e "/home/jovyan/test-data" ]; then
    ln -s /mnt/test-data "/home/jovyan/test-data" 2>/dev/null || true
  fi
fi
