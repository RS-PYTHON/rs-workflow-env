<!--
  Copyright 2022-2023 ESA

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
-->

# EOPF Studio

Welcome to the EOPF Studio environment, a pre-configured development
environment including recommended tools for EOPF development.

Studio offers a virtual workspace including a
[Jupyter](https://jupyterlab.readthedocs.io/en/latest/index.html) environment
and an Integrated Development Environment based on
[Code Server](https://code.visualstudio.com/docs/remote/vscode-server),
a version of Visual Studio Code for the Web.

Please see the [Studio](https://sde.pages.eopf.copernicus.eu/sde/main/user-manual/studio/index.html)
section of the EOPF SDE documentation for more information.

## Updating the $HOME directory

Your `$HOME` directory is initialized the first time your Studio
environment is started. However, any changes introduced by later
versions of Studio will not be automatically applied,
to not overwrite any user-specific changes.

You can check for changes by comparing your local files to the ones
provided with Studio, which are available in `/opt/eopf` and
eventually introduce changes yourself.

## JupyterLab Launcher tab

The JupyterLab's Launcher tab is available from the `File > New Launcher`
menu item or by clicking the `+` button at the top of the
[main work area](https://jupyterlab.readthedocs.io/en/latest/user/interface.html#main-area).

## Virtual environments

Using lightweight Python
[virtual environments](https://docs.python.org/3/library/venv.html)
is strongly encouraged!
Virtual environments allow handling independent set of Python packages installed in
their [site](https://docs.python.org/3/library/site.html#module-site)
directories.

## Using the EOPF Core Python Modules (CPM)

As new versions of the
[EOPF CPM](https://gitlab.eopf.copernicus.eu/cpm/eopf-cpm)
are released regularly, users are invited to install the library
themselves.

First, in a terminal, set the `EOPF_CPM_VERSION` environment variable
specifying the EOPF CPM version to use. _The available versions are
listed by the EOPF CPM's
[tags](https://gitlab.eopf.copernicus.eu/cpm/eopf-cpm/-/tags) page_.

```bash
export EOPF_CPM_VERSION=1.5.0
```

In the above example, version `1.5.0` is specified. Please replace
this version either with the latest one or the one applicable to
you development context.

To create a virtual environment with the EOPF CPM, either execute the
below instructions that
creates both the virtual environment and a
[Jupyter kernel](https://docs.jupyter.org/en/latest/projects/kernels.html)
that allows running notebooks within the virtual environment.

To create and activate the virtual environment, execute the following
commands:

```bash
python -m venv --system-site-packages ${HOME}/envs/eopf-cpm-${EOPF_CPM_VERSION}
source ${HOME}/envs/eopf-cpm-${EOPF_CPM_VERSION}/bin/activate
```

Install the EOPF CPM in the virtual environment:

```bash
pip install eopf==${EOPF_CPM_VERSION}
```

Then, create a Jupyter kernel for the virtual environment:

```bash
python -m ipykernel install --user --name eopf-cpm-${EOPF_CPM_VERSION} --display-name "EOPF CPM ${EOPF_CPM_VERSION}"
```

That is it. You are ready to use the EOPF CPM.

## EOPF Core Python Modules Notebooks

The online EOPF documentation is completed by a set of Jupyter
notebooks that allow illustrating the EOPF concepts and use cases.
The notebooks can be found in the
[CPM Notebooks](https://gitlab.eopf.copernicus.eu/cpm/cpm-notebooks)
project.

To run the notebooks, a Jupyter kernel with the EOPF CPM must be
created as described previously.
