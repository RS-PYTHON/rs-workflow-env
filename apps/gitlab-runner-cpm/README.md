# CPM V3 GitLab Runner on RSPY

This directory packages the GitLab CI runner for CPM (Core Python Modules) on the RSPY infrastructure.

## Overview

* **Chart**: `gitlab-runner` v0.76.3
* **Namespace**: `processing` (configurable via `{{ jupyterhub.ops.namespace }}`)
* **Instance**: `gitlab-runner-cpm`
* **Target Project**: `https://gitlab.eopf.copernicus.eu/cpm/eopf-cpm`

## Mounted Volumes & Storage

1. **Ephemeral Job Workspace (`/builds`)**:
   * Uses `topologySpreadConstraints` to balance load across nodes.
   * Dynamically provisions a 100 GiB `ReadWriteOnce` cinder volume per build pod (`csi-cinder-high-speed`).

2. **CI Cache Volume (`shared-cpm-ci-data` mounted at `/data/cache-ci`)**:
   * 200 GiB `ReadWriteMany` Manila NFS PVC.
   * Holds the 105+ GB `dpr-common` test dataset (`l0`, `s01`, `s02`, `s03`) under `/data/cache-ci/ci_test_data/`.

3. **Shared Tests Volume (`shared-cpm-tests` mounted at `/mnt/test-data`)**:
   * 500 GiB `ReadWriteMany` Manila NFS PVC.
   * Shared between GitLab Runner, JupyterHub (`CPM Dev Environment`), and Dask Gateway workers.

## Populating / Synchronizing the 105 GB `dpr-common` Dataset

To synchronize or refresh the 105 GB dataset into `/data/cache-ci/ci_test_data/`:

```bash
# Run dry-run test
DRY_RUN=true ./scripts/sync-dpr-common-dataset.sh /data/cache-ci/ci_test_data/

# Run live synchronization
./scripts/sync-dpr-common-dataset.sh /data/cache-ci/ci_test_data/
```
