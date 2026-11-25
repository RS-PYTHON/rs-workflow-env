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

"""Post-build check of the Dask EOPF images: the processor and its dependencies can be imported.

It detects e.g. a missing dependency or system library, or a processor that is not compatible with the installed CPM
version. Run in the built image by the CI, before the push:

    docker run --rm -i --entrypoint python --workdir /tmp <image> - <processor> < check_imports.py
"""

import importlib
import sys
from dataclasses import dataclass, field
from importlib.metadata import entry_points, version

from opentelemetry.instrumentation.eopf import EopfInstrumentor


@dataclass
class Checks:
    """What to check in a processor image"""

    # Modules to import, with the attributes to read from them, e.g. the processing units of the task tables used by
    # rs-dpr-service
    imports: dict[str, list[str]]

    # Python packages whose version is displayed
    packages: list[str]

    # EOPF readers that must be declared as entry points (CPM >= 3.1 discovers the readers this way only)
    readers: list[str] = field(default_factory=list)


CHECKS = {
    "cpm3": Checks(
        # SAFE to Zarr conversion run by rs-dpr-service, with the SAFE readers of eopf-safe. scipy is needed by the
        # SAFE reader of the S1 products, but it is not an eopf or eopf-safe dependency.
        imports={"eopf.store.convert": ["convert"], "eopf_safe": [], "scipy": []},
        packages=["eopf", "eopf-safe", "scipy"],
        readers=["safe"],
    ),
    "l0": Checks(
        imports={
            "l0.s1.s1_l0_processor": ["S1L0Processor"],
            "l0.s3.s3_l0_processor": ["S3L0Processor"],
            "eopf_safe": [],
        },
        packages=["eopf", "eopf-safe", "l0"],
        readers=["cadu", "s3_cache"],
    ),
    "s1ard": Checks(
        imports={"s1_ard.computing.ard_processing_units": ["Calibration"], "eopf_safe": []},
        packages=["eopf", "eopf-safe", "s1-ard", "s1-ard-core"],
    ),
    "s3olci": Checks(
        imports={
            "s3olci.s3_ol1.ol1_processor": ["OL1Processor"],
            "s3olci.s3_ol2.ol2_processor": ["OL2Processor"],
            "eopf_safe": [],
        },
        packages=["eopf", "eopf-safe", "s3olci"],
    ),
}


def check_imports(processor: str):
    """Check that the modules, readers and OpenTelemetry instrumentation of the processor image can be loaded"""
    checks = CHECKS[processor]

    for module_name, attributes in checks.imports.items():
        module = importlib.import_module(module_name)
        print(f"import {module_name}: OK")
        for attribute in attributes:
            print(f"{module_name}.{attribute}: {getattr(module, attribute)}")

    readers = {entry_point.name: entry_point for entry_point in entry_points(group="eopf_readers")}
    for reader in checks.readers:
        if reader not in readers:
            raise RuntimeError(f"EOPF reader {reader!r} is not declared, found: {sorted(readers)}")
        print(f"EOPF reader {reader}: {readers[reader].load()}")

    # The OpenTelemetry instrumentation of eopf, enabled in the Dask workers, must accept the installed CPM version
    instrumentor = EopfInstrumentor()
    instrumentor.instrument()
    if not instrumentor.is_instrumented_by_opentelemetry:
        raise RuntimeError("eopf is not instrumented by OpenTelemetry")
    print("OpenTelemetry instrumentation of eopf: OK")

    for package in checks.packages:
        print(f"{package}: {version(package)}")
    print(f"OK: dask/{processor} image")


if __name__ == "__main__":
    if (len(sys.argv) != 2) or (sys.argv[1] not in CHECKS):
        sys.exit(f"usage: python - <{'|'.join(CHECKS)}> < check_imports.py")
    check_imports(sys.argv[1])
