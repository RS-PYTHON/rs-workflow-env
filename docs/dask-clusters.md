# Add and delete Dask clusters

The Dask clusters are created through the Dask Gateway of the [virtual environment](../README.md). They are
identified by a **label** (the `cluster_name` option), used by the flows and services to find them, e.g. the
`dask_cluster_label` parameter of the [processing flows](https://github.com/RS-PYTHON/rs-client-libraries/blob/develop/docs/doc/advanced/customise-dpr-flow.md).
See [Dask](https://github.com/RS-PYTHON/rs-documentation/blob/develop/docs/services/virtual-environment/dask.md) for
the user point of view, and [Dask images](dask_images.md) for the images.

| Cluster | Created by | How |
|---|---|---|
| Staging (`dask-staging`) | The administrators, at deployment time | The `dask-cluster-staging` application of [rs-server-deployment](https://github.com/RS-PYTHON/rs-server-deployment/blob/develop/README.md) runs a small pod that creates the staging cluster with the `rs_server_staging.dask` inventory parameters (number and size of the workers) and recreates it if it disappears. |
| DPR processors | The administrators or the users | From JupyterHub, with the notebooks of [rs-demo](https://github.com/RS-PYTHON/rs-demo), or with Python code. |

## Create a cluster from JupyterHub

The `notebooks/init-dask-clusters` folder of [rs-demo](https://github.com/RS-PYTHON/rs-demo) contains one notebook per
kind of cluster: `init_dask_cluster_l0.ipynb`, `init_dask_cluster_s1ard.ipynb`, `init_dask_cluster_s3olci.ipynb`,
`init_dask_cluster_staging.ipynb`... Each notebook:

1. must be run with the Jupyter kernel of the Python and Dask versions of the cluster (it checks it in its first
   cell),
2. has a parameters cell: number of workers (`scale`), Docker image and tag, cluster label (by default
   `<processor>.<user>.<docker tag>`), CPU and memory of the workers and of the scheduler, big or standard
   resources,
3. creates the cluster, scales it, and displays its information and the link to its dashboard,
4. can shut the cluster down (last cells).

The clusters are owned by the user who creates them (Dask Gateway uses the JupyterHub authentication). The flows
access them with the JupyterHub API token of the `env-vars` Prefect block.

## Create a cluster with Python

```python
from dask_gateway import Gateway

gateway = Gateway()  # address and authentication configured in JupyterHub
options = gateway.cluster_options()
print(options)  # available options: image, worker_cores, worker_memory, cluster_name...

options.image = "ghcr.io/rs-python/dask/l0/k8s:latest"
options.cluster_name = "dask-l0"  # the label used by the flows
cluster = gateway.new_cluster(options, shutdown_on_close=False)
cluster.scale(2)
print(cluster.name, cluster.dashboard_link)
```

More examples, e.g. to set the node affinity of the workers, are given in
[Dask Gateway](https://github.com/RS-PYTHON/rs-infra-core/blob/develop/docs/how-to/dask-gateway.md).

## CPM test clusters with shared disk

For CPM workflows and integration tests requiring shared disk access (such as Sentinel-2 processing):

* Set `options.mount_cpm_shared_disk = True`, or
* Use a CPM image (e.g. `image="ghcr.io/rs-python/rs-workflow-env-cpm:latest"` or any image containing `cpm` in its name).

The shared disk (`shared-cpm-tests` PVC) is automatically mounted at `/mnt/test-data` on all Dask workers and the scheduler.

## List and delete clusters

```python
from dask_gateway import Gateway

gateway = Gateway()
for report in gateway.list_clusters():
    print(report.name, report.status, report.options.get("cluster_name"))

gateway.connect("<cluster name>").shutdown()  # delete one cluster
```

Deleting a cluster stops the processors running on it. A cluster with no activity is not deleted automatically:
delete the clusters you don't use anymore, to free the resources.
