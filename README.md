# rs-workflow-env

The virtual environment of [RS-Python](https://home.rs-python.eu/), the Copernicus Reference System Python: the
components that support the processing orchestration, deployed on top of the
[core infrastructure](https://github.com/RS-PYTHON/rs-infra-core), and the Docker images of JupyterHub and of the
Dask clusters.

## Overview

The `apps` folder contains the applications deployed with the Ansible playbooks of rs-infra-core (see
[Deploy RS-Python](https://github.com/RS-PYTHON/rs-documentation/blob/develop/docs/administration/deploy.md)):

| Application | Description |
|---|---|
| `jupyterhub` | [JupyterHub](https://jupyter.org/hub): one JupyterLab session per user, with the RS-Python libraries, see [JupyterHub](https://github.com/RS-PYTHON/rs-documentation/blob/develop/docs/services/virtual-environment/jupyterhub.md). |
| `prefect3-server`, `01-prefect3-db` | The [Prefect](https://www.prefect.io/) server and its database, protected by Keycloak. |
| `prefect3-worker-integrated`, `prefect3-worker-sandbox`, `prefect3-worker-monitoring` | The Prefect Kubernetes workers of the three [work pools](https://github.com/RS-PYTHON/rs-documentation/blob/develop/docs/services/virtual-environment/prefect.md#work-pools). |
| `prefect3-grafanadatasource` | The Grafana data source of the Prefect database. |
| `dask-gateway` | [Dask Gateway](https://gateway.dask.org/), that creates the Dask clusters, with the JupyterHub authentication, see [Add and delete Dask clusters](docs/dask-clusters.md). |
| `apikeymanager`, `01-apikeymanager-db` | The [API Key Manager](https://github.com/csgroup-oss/apikey-manager) and its database, see [User rights and API keys](https://github.com/RS-PYTHON/rs-documentation/blob/develop/docs/getting-started/user-rights.md). |
| `01-listenerset` | The [Gateway API](https://gateway-api.sigs.k8s.io/) listeners of the public host names (`processing.<domain>`, `apikeymanager.<domain>`, `dash-dask.processing.<domain>`). |
| `gitlab-runner-cpm` | A GitLab runner used to run the EOPF CPM tests on the cluster. |

The `docker` folder contains the Docker images built by the CI of this repository:

| Folder | Images |
|---|---|
| `docker/base` | Base images: Python, Jupyter, Dask (`dask-gateway`) for the cluster and local modes. |
| `docker/eopf` | Dask images of the DPR processors, see [Dask images](docs/dask_images.md). |
| `docker/jupyter` | The JupyterHub image, with the rs-client-libraries and one Jupyter kernel per Dask version. |
| `docker/jupyter-cpm` | A JupyterLab image with the EOPF CPM development tools. |

The Python and Dask versions of the Dask clusters are listed in
[`docker/scripts/dask-cluster-versions.yml`](https://github.com/RS-PYTHON/rs-workflow-env/blob/develop/docker/scripts/dask-cluster-versions.yml).

## Getting started

Deploy the virtual environment from the bastion, after the core infrastructure:

```shell
cd ~/rs-infra-core
ansible-playbook apps.yaml -i inventory/mycluster/hosts.yaml -e '{"package_paths": ["~/rs-workflow-env/apps/"]}'
```

The parameters are the `jupyterhub`, `prefect3server`, `prefect3worker`, `apikeymanager` and `dask` variables of the
inventory. After the deployment:

1. generate a JupyterHub API token and configure it for the staging service and the Dask clusters (see
   [Dask Gateway](https://github.com/RS-PYTHON/rs-infra-core/blob/develop/docs/how-to/dask-gateway.md)),
2. set the concurrency limits of the work pools if needed (see
   [Prefect work pools](https://github.com/RS-PYTHON/rs-infra-core/blob/develop/docs/how-to/prefect-work-pools.md)),
3. [initialise the processing environment](https://github.com/RS-PYTHON/rs-documentation/blob/develop/docs/administration/init-processing-environment.md).

### Several user groups

Each user group (e.g. each organisation) can have its own virtual environment: its own Prefect server and workers,
JupyterHub and Dask Gateway, in its own namespace, with its own CPU and RAM resources. Duplicate the applications
with different names and namespaces, as described in
[Isolation between user groups](https://github.com/RS-PYTHON/rs-infra-core/blob/develop/docs/how-to/isolation-user-groups.md).

## Documentation

- [Dask images](docs/dask_images.md)
- [Add and delete Dask clusters](docs/dask-clusters.md)
- [Third-party components](NOTICE.md)
- [Changelog](CHANGELOG.md)
- Online documentation of the whole project: <https://home.rs-python.eu/rs-documentation/>

## Related repositories

| Repository | Relationship |
|---|---|
| [rs-infra-core](https://github.com/RS-PYTHON/rs-infra-core) | The core infrastructure and the Ansible playbooks used to deploy this repository. |
| [rs-workflow-deployment](https://github.com/RS-PYTHON/rs-workflow-deployment) | The Prefect flows deployed in this environment. |
| [rs-client-libraries](https://github.com/RS-PYTHON/rs-client-libraries) | The library installed in the JupyterHub image. |
| [rs-dpr-service](https://github.com/RS-PYTHON/rs-dpr-service) | The service that runs the processors on the Dask clusters. |
| [rs-documentation](https://github.com/RS-PYTHON/rs-documentation) | Online documentation of the whole project. |

## Contributing

See the [contribution guidelines](https://github.com/RS-PYTHON/rs-documentation/blob/develop/docs/developers/contributing.md).
Report bugs in the [issue tracker](https://github.com/RS-PYTHON/rs-workflow-env/issues). In case of sensitive bugs like
security vulnerabilities, please contact <ops_coprs@airbus.com> directly instead of using the issue tracker.

## Licensing

The code in this project is licensed under the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0).

---

![](https://raw.githubusercontent.com/RS-PYTHON/.github/refs/heads/main/profile/banner_logo.jpg)

This project is funded by the EU and ESA.
