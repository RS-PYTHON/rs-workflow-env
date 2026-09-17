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

ARG ROOT_CONTAINER=python:3.13-bookworm

FROM $ROOT_CONTAINER

ARG NB_USER="rspy"
ARG NB_UID="1001"
ARG NB_GID="1001"
ARG PYTHON_VERSION=3.13
ARG CPM_VERSION=3.0.0rc4
ARG JUPYTERHUB_VERSION=4.1.6

LABEL org.opencontainers.image.title="CPM Dev Studio image"
LABEL org.opencontainers.image.description="Jupyter Server environment for CPM development and testing on RSPY"
LABEL org.opencontainers.image.source="https://github.com/RS-PYTHON/rs-workflow-env"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

USER root

# Install essential OS dependencies for Jupyter Server
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update --yes && \
    apt-get install --yes --no-install-recommends \
    ca-certificates \
    curl \
    git \
    jq \
    locales \
    procps \
    sudo \
    tini \
    unzip \
    wget \
    zip && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen

# Configure environment
ENV SHELL=/bin/bash \
    NB_USER="${NB_USER}" \
    NB_UID=${NB_UID} \
    NB_GID=${NB_GID} \
    LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8 \
    HOME="/home/${NB_USER}" \
    PATH="/home/${NB_USER}/.local/bin:/opt/conda/bin:${PATH}"

# Copy permission fix script
COPY fix-permissions /usr/local/bin/fix-permissions
RUN chmod a+rx /usr/local/bin/fix-permissions

# Create user rspy (UID 1001, GID 1001) for RSPY compatibility + jovyan compatibility
RUN echo "auth requisite pam_deny.so" >> /etc/pam.d/su && \
    groupadd -g "${NB_GID}" "${NB_USER}" && \
    useradd --no-log-init --create-home --shell /bin/bash -g "${NB_GID}" -u "${NB_UID}" "${NB_USER}" && \
    useradd --no-log-init --shell /bin/bash -g "${NB_GID}" -u 1000 jovyan 2>/dev/null || true && \
    ln -s "/home/${NB_USER}" /home/jovyan && \
    mkdir -p /mnt/test-data && \
    chown -R "${NB_USER}:${NB_GID}" /mnt/test-data "/home/${NB_USER}" && \
    chmod 777 /mnt/test-data

# Install Python packages directly via pip (fast, lightweight, single environment)
RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
    jupyterlab \
    jupyterhub=="${JUPYTERHUB_VERSION}" \
    dask \
    dask-gateway \
    distributed \
    ipywidgets \
    pytest \
    pytest-cov \
    xarray \
    s3fs \
    boto3 \
    eopf=="${CPM_VERSION}" && \
    fix-permissions "${HOME}"

# Create compatibility symlinks for scripts expecting /opt/conda/bin
RUN mkdir -p /opt/conda/bin && \
    ln -s "$(which jupyter)" /opt/conda/bin/jupyter && \
    ln -s "$(which python3)" /opt/conda/bin/python

# Copy startup scripts and configurations
COPY start-notebook.sh start-singleuser.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/start-notebook.sh /usr/local/bin/start-singleuser.sh

COPY jupyter_server_config.py /etc/jupyter/jupyter_server_config.py

# Add EOPF specific skeleton files to /opt/eopf
COPY resources /opt/eopf/
RUN cp /home/${NB_USER}/.bashrc /opt/eopf/.bashrc 2>/dev/null || true && \
    cp /home/${NB_USER}/.profile /opt/eopf/.profile 2>/dev/null || true && \
    chmod +x /opt/eopf/bin/*.bash 2>/dev/null || true && \
    chown -R root:root /opt/eopf

EXPOSE 8888

ENTRYPOINT ["tini", "-g", "--"]
CMD ["start-notebook.sh"]

USER ${NB_UID}
WORKDIR "${HOME}"
