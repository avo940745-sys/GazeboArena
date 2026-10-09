"""Structural/resource checks everywhere; native SDF checks on Fortress hosts."""
from pathlib import Path
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET

from .resources import local_uri, model_file, resource_elements


def resource_roots(path: Path) -> list[Path]:
    roots = [path.parent / "models", path.parent, path.parent.parent]
    models = path.parent / "models"
    if models.is_dir():
        # Imported folders are namespaced by object, then original folder name.
        roots.extend(p for p in models.iterdir() if p.is_dir())
    roots.extend(Path(p) for p in os.environ.get("IGN_GAZEBO_RESOURCE_PATH", "").split(os.pathsep) if p)
    return roots


def validate_world(path: str | Path, native: bool = False) -> dict:
    path = Path(path).resolve()
    root = ET.parse(path).getroot()
    worlds = root.findall("world")
    if root.tag != "sdf" or len(worlds) != 1:
        raise ValueError("需要包含一个 world 的 SDF 场景")
    visited = set()

    def inspect(file: Path, extra_roots: list[Path]):
        file = file.resolve()
        if file in visited:
            raise ValueError(f"循环 SDF include: {file.name}")
        visited.add(file)
        node = ET.parse(file).getroot()
        names = [item.get("name") for item in node.findall("world/model")]
        names += [item.findtext("name") for item in node.findall("world/include") if item.findtext("name")]
        if len(names) != len(set(names)):
            raise ValueError("SDF 存在重复模型名称")
        for uri in resource_elements(node):
            if not uri.text:
                if uri.tag == "uri": raise ValueError("SDF 包含空资源 URI")
                continue
            target = local_uri(uri.text, file.parent, extra_roots, allow_absolute=True)
            if target.is_dir(): target = model_file(target)
            if target.suffix.lower() in (".sdf", ".world"):
                inspect(target, [target.parent.parent] + extra_roots)
        visited.remove(file)

    inspect(path, resource_roots(path))
    report = {"structure": "passed", "resources": "passed", "native": "not_run", "world": worlds[0].get("name")}
    if native:
        if not shutil.which("ign"):
            raise ValueError("缺少 Gazebo Fortress 的 ign 命令，无法执行原生检查")
        from .runtime import gazebo_environment
        result = subprocess.run(["ign", "sdf", "-k", str(path)], capture_output=True, text=True,
                                timeout=45, env=gazebo_environment(path), cwd=path.parent)
        if result.returncode or "Error" in result.stderr or "Error" in result.stdout:
            raise ValueError("Fortress 原生检查失败:\n" + result.stdout + result.stderr)
        report["native"] = "passed"
        report["native_output"] = result.stdout.strip()
    return report
