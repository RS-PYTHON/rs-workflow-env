"""Regression checks for shared writes and reused Jupyter spawners.

Run with: python3 -m unittest discover -s tests
"""

import asyncio
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SharedDiskTests(unittest.TestCase):
    def test_profile_switch_restores_settings(self):
        source = (ROOT / "apps/jupyterhub/values.yaml").read_text()
        hook = source.split("    10-extra-cpm-shared-volume: |\n", 1)[1]
        hook = hook.split("      c.Spawner.pre_spawn_hook", 1)[0]
        namespace = {}
        exec(textwrap.dedent(hook), namespace)
        for as_dict in (False, True):
            for original_umask in (None, "0077"):
                with self.subTest(as_dict=as_dict, umask=original_umask):
                    spawner = types.SimpleNamespace(
                        user_options={"profile": "cpm-dev-environment"},
                        node_selector={"node-role.kubernetes.io/rs_env": ""},
                        supplemental_gids=[2000],
                        environment={"TOKEN": "preserved"},
                        volumes={"existing": {"name": "existing"}} if as_dict else [{"name": "existing"}],
                        volume_mounts={} if as_dict else [],
                        log=types.SimpleNamespace(info=lambda *args: None),
                    )
                    if original_umask is not None:
                        spawner.environment["UMASK"] = original_umask
                    fields = ("node_selector", "supplemental_gids", "environment", "volumes", "volume_mounts")
                    original = {key: copy.deepcopy(getattr(spawner, key)) for key in fields}
                    for _ in range(2):
                        asyncio.run(namespace["mount_cpm_volume"](spawner))
                        self.assertEqual(len(spawner.volumes), 2)
                        self.assertIn(2000, spawner.supplemental_gids)
                    spawner.user_options = {"profile": "release-v1-0a14"}
                    asyncio.run(namespace["mount_cpm_volume"](spawner))
                    self.assertEqual({key: getattr(spawner, key) for key in fields}, original)

    def test_startup_creates_group_writable_files(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            # Stub the final application, retaining the real startup scripts.
            stub = temp / "jupyterhub-singleuser"
            stub.write_text('#!/bin/bash\ntouch "$TEST_OUTPUT"\n')
            stub.chmod(0o755)
            env = {**os.environ, "UMASK": "0002", "JUPYTERHUB_API_TOKEN": "test",
                   "PATH": f"{temp}:{os.environ['PATH']}"}
            commands = [
                ["bash", str(ROOT / "docker/jupyter-cpm" / name)]
                for name in ("start-notebook.sh", "start-singleuser.sh")
            ]
            for name, module in (("dask-worker", "dask_worker"), ("dask-scheduler", "dask_scheduler")):
                # Replace only the distributed CLI dependency, then execute
                # the actual wrapper in a fresh process with a restrictive mask.
                code = f'''
import os, runpy, sys, types
os.umask(0o022)
cli = types.ModuleType("distributed.cli.{module}")
def main():
    with open(os.environ["TEST_OUTPUT"], "w"):
        pass
cli.main = main
sys.modules[cli.__name__] = cli
runpy.run_path({str(ROOT / "docker/scripts" / name)!r}, run_name="__main__")
'''
                commands.append([sys.executable, "-c", code])
            runner = (ROOT / "apps/gitlab-runner-cpm/values.yaml").read_text()
            pre_build = runner.split('pre_build_script = "', 1)[1].split('"', 1)[0]
            commands.append(["bash", "-c", pre_build + '\ntouch "$TEST_OUTPUT"'])
            for index, command in enumerate(commands):
                with self.subTest(command=command[:2]):
                    output = temp / f"output-{index}"
                    subprocess.run(command, env={**env, "TEST_OUTPUT": str(output)}, check=True)
                    self.assertEqual(output.stat().st_mode & 0o777, 0o664)


if __name__ == "__main__":
    unittest.main()
