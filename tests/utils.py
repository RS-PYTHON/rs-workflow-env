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


"""Utilities shared by the pytests of the python code and configuration files of the apps."""

import importlib.util
import sys
from pathlib import Path

import jinja2
import yaml

APPS_DIR = Path(__file__).resolve().parent.parent / "apps"
DASK_GATEWAY_DIR = APPS_DIR / "dask-gateway"


def load_named_kube_backend():
    """Import the named_kube_backend.py module (its directory name contains a '-', so it isn't a python package)."""
    spec = importlib.util.spec_from_file_location("named_kube_backend", DASK_GATEWAY_DIR / "named_kube_backend.py")
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def render_yaml(app_dir: Path, template: str, **variables):
    """
    Return a YAML file of an app, rendered with Jinja as the rs-infra-core app installer does (Ansible template),
    with these inventory variables. The other inventory variables are ignored.
    """
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(app_dir),
        trim_blocks=True,  # Ansible default
        undefined=jinja2.ChainableUndefined,  # ignore the inventory variables
        autoescape=False,  # nosec B701: this is a YAML file, not HTML
    )
    # Ansible filters used in the templates. The ignored inventory variables are rendered as null.
    env.filters["to_yaml"] = lambda value: "null" if isinstance(value, jinja2.Undefined) else yaml.safe_dump(value)
    return yaml.safe_load(env.get_template(template).render(**variables))
