"""Owned process groups, isolated transport partition, portable resource paths."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import json
import os
import platform
import shutil
import signal
import subprocess
import time
import uuid

from .validation import resource_roots, validate_world


def gazebo_environment(world: Path, partition: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("QT_QPA_PLATFORM_PLUGIN_PATH", "QT_QPA_FONTDIR", "QT_PLUGIN_PATH"):
        env.pop(key, None)
    roots = resource_roots(world.resolve())
    env["IGN_GAZEBO_RESOURCE_PATH"] = os.pathsep.join(dict.fromkeys(str(p) for p in roots if p.is_dir()))
    env["IGN_PARTITION"] = partition or "gazeboarena-" + uuid.uuid4().hex
    return env


class GazeboSession:
    def __init__(self, world: str | Path, headless=False, iterations: int | None = None, log_root=None):
        self.world = Path(world).resolve()
        self.headless = headless
        self.iterations = iterations
        self.log_root = Path(log_root) if log_root else self.world.parent / "runs"
        self.partition = "gazeboarena-" + uuid.uuid4().hex
        self.process = None
        self.log_file = None
        self.directory = None
        self.stopped = False

    def start(self):
        if self.process is not None:
            raise RuntimeError("同一会话不能重复启动")
        if platform.system() != "Linux" or not shutil.which("ign"):
            raise ValueError("预览需要 Ubuntu + Gazebo Fortress。请将完整导出目录复制到 Ubuntu，运行 bash view.sh。")
        validate_world(self.world)
        command = ["ign", "gazebo", "-r", "--render-engine", "ogre"]
        command += ["-s"] if self.headless else ["--render-engine-gui", "ogre"]
        if not self.headless and (self.world.parent / "arena_gui.config").is_file():
            command += ["--gui-config", str(self.world.parent / "arena_gui.config")]
        if self.iterations:
            command += ["--iterations", str(self.iterations)]
        command.append(str(self.world))
        self.directory = self.log_root / (datetime.now().strftime("run_%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8])
        self.directory.mkdir(parents=True)
        # Record operational metadata, never the inherited environment/credentials.
        (self.directory / "session.json").write_text(json.dumps({"world": str(self.world), "partition": self.partition,
            "command": command, "headless": self.headless}, indent=2), encoding="utf-8")
        self.log_file = (self.directory / "gazebo.log").open("w", encoding="utf-8")
        try:
            env = gazebo_environment(self.world, self.partition)
            # Fortress starts its server and GUI in separate process groups.
            # This private token belongs only to the launched process subtree;
            # external controllers sharing IGN_PARTITION do not receive it.
            env["GAZEBOARENA_PROCESS_TOKEN"] = self.partition
            self.process = subprocess.Popen(command, cwd=self.world.parent,
                env=env, start_new_session=True,
                stdout=self.log_file, stderr=subprocess.STDOUT)
        except Exception:
            self.log_file.close()
            raise
        return self

    def _owned_pids(self):
        token = ("GAZEBOARENA_PROCESS_TOKEN="+self.partition).encode()
        owned = []
        for directory in Path("/proc").iterdir():
            if not directory.name.isdigit(): continue
            try:
                if token in (directory/"environ").read_bytes().split(b"\0"):
                    owned.append(int(directory.name))
            except (OSError,PermissionError): pass
        return owned

    def stop(self):
        if self.stopped: return
        self.stopped = True
        if self.process:
            for pid in self._owned_pids():
                try: os.kill(pid, signal.SIGTERM)
                except ProcessLookupError: pass
            try: self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try: self.process.kill()
                except ProcessLookupError: pass
                self.process.wait(timeout=5)
            deadline = time.monotonic()+3
            while self._owned_pids() and time.monotonic()<deadline:
                time.sleep(.05)
            for pid in self._owned_pids():
                try: os.kill(pid, signal.SIGKILL)
                except ProcessLookupError: pass
        if self.log_file and not self.log_file.closed:
            self.log_file.close()

    def wait(self):
        try:
            return self.process.wait()
        finally:
            self.stop()

    def poll(self):
        return self.process.poll() if self.process else None

    def log_tail(self):
        if self.directory:
            path = self.directory / "gazebo.log"
            return path.read_text(encoding="utf-8", errors="replace")[-5000:]
        return ""
