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
#!/bin/bash
JOVYAN_HOME=/home/jovyan
EOPF_HOME=/opt/eopf

copy_file() {
  if [ -f "${DEST}" ] ; then
    echo "${DEST} already exists"
  elif [ -f "${SRC}" ] ; then
    echo "${DEST} does not exist. Copying file from ${SRC}"
    DEST_DIR=`dirname ${DEST}`
    if [ ! -d "${DEST_DIR}" ] ; then
      sudo -u jovyan mkdir --parents ${DEST_DIR}
    fi
    sudo -u jovyan cp ${SRC} ${DEST}
  fi
}

# .bash_logout
SRC=${EOPF_HOME}/.bash_logout
DEST=${JOVYAN_HOME}/.bash_logout
copy_file

# .bashrc
SRC=${EOPF_HOME}/.bashrc
DEST=${JOVYAN_HOME}/.bashrc
copy_file

# .profile
SRC=${EOPF_HOME}/.profile
DEST=${JOVYAN_HOME}/.profile
copy_file

# README.md
SRC=${EOPF_HOME}/README.md
DEST=${JOVYAN_HOME}/README.md
copy_file

# .conda/environments.txt
SRC=${EOPF_HOME}/.conda/environments.txt
DEST=${JOVYAN_HOME}/.conda/environments.txt
copy_file

# .jupyter/jupyter_notebook_config.py
SRC=${EOPF_HOME}/.jupyter/jupyter_notebook_config.py
DEST=${JOVYAN_HOME}/.jupyter/jupyter_notebook_config.py
copy_file

# .s3cfg
SRC=${EOPF_HOME}/aws/.s3cfg
DEST=${JOVYAN_HOME}/.s3cfg
copy_file

# Initialize the JupyterLab default workspace to display the README.md file
# providing an introduction to the Jupyter environment.
# The README.md file will not be displayed any longer if the user
# chooses to close the tab.
STUDIO_DEFAULT_WORKSPACE=${EOPF_HOME}/jupyterlab/default.jupyterlab-workspace
JOVYAN_DEFAULT_WORKSPACE=${JOVYAN_HOME}/.jupyter/lab/workspaces/default-*.jupyterlab-workspace
if ls ${JOVYAN_DEFAULT_WORKSPACE} 1> /dev/null 2>&1; then
  echo "JupyterLab default workspace found in ${JOVYAN_HOME}/.jupyter/lab/workspaces"
else
  echo "JupyterLab default workspace not found in ${JOVYAN_HOME}/.jupyter/lab/workspaces"
  echo "Importing JupyterLab default workspace from ${STUDIO_DEFAULT_WORKSPACE}"
  # The script is executed by the root user
  sudo -u jovyan /opt/conda/bin/jupyter lab workspaces import ${STUDIO_DEFAULT_WORKSPACE}
fi

# Set JupyterLab notification settings, if the file does not already exist
STUDIO_NOTIFICATION_SETTINGS=${EOPF_HOME}/jupyterlab/notification.jupyterlab-settings
JOVYAN_NOTIFICATION_SETTINGS=${JOVYAN_HOME}/.jupyter/lab/user-settings/\@jupyterlab/apputils-extension/notification.jupyterlab-settings
if ls ${JOVYAN_NOTIFICATION_SETTINGS} 1> /dev/null 2>&1; then
  echo "JupyterLab notification settings file found in ${JOVYAN_HOME}/.jupyter/lab/user-settings/\@jupyterlab/apputils-extension/"
  echo "JupyterLab notification settings have not be updated"
else
  echo "JupyterLab notification settings not found in ${JOVYAN_HOME}/.jupyter/lab/user-settings/\@jupyterlab/apputils-extension/"
  echo "Applying JupyterLab default notification settings from ${STUDIO_NOTIFICATION_SETTINGS}"
  SRC=${STUDIO_NOTIFICATION_SETTINGS}
  DEST=${JOVYAN_NOTIFICATION_SETTINGS}
  copy_file
  # The script is executed by the root user.
  # Disabling an extension is recorded in the /opt/conda/etc/jupyter/labconfig/page_config.json
  # file, which can only be edited by root.
  #
  # {
  #   "disabledExtensions": {
  #     "@jupyterlab/apputils-extension:announcements": true
  #   }
  # }
  echo "JupyterLab announcements are disabled"
  /opt/conda/bin/jupyter labextension disable "@jupyterlab/apputils-extension:announcements"
fi

# Link CPM test data if directory exists
if [ -d "/mnt/test-data" ] && [ ! -e "${JOVYAN_HOME}/test-data" ]; then
  echo "Linking /mnt/test-data to ${JOVYAN_HOME}/test-data"
  sudo -u jovyan ln -s /mnt/test-data "${JOVYAN_HOME}/test-data" 2>/dev/null || ln -s /mnt/test-data "${JOVYAN_HOME}/test-data" 2>/dev/null || true
fi
