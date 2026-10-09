"""Local resources only; no Fuel downloads or implicit dependency resolution."""
from __future__ import annotations
from pathlib import Path
import shutil
from urllib.parse import unquote
import xml.etree.ElementTree as ET


def model_file(directory: Path) -> Path:
    if not directory.is_dir():
        raise ValueError(f"模型目录不存在: {directory}")
    config = directory / "model.config"
    if config.is_file():
        root = ET.parse(config).getroot()
        item = root.find("sdf")
        if item is None or not item.text:
            raise ValueError(f"model.config 缺少 sdf: {directory}")
        path = (directory / item.text.strip()).resolve()
    else:
        path = (directory / "model.sdf").resolve()
    if not path.is_relative_to(directory.resolve()) or not path.is_file():
        raise ValueError(f"模型缺少有效 SDF: {directory}")
    root = ET.parse(path).getroot()
    if root.tag != "sdf" or len(root.findall("model")) != 1 or root.find("world") is not None:
        raise ValueError(f"需要单个 Gazebo 模型目录: {directory}")
    return path


def local_uri(uri: str, context: Path, model_roots: list[Path], allow_absolute=False) -> Path:
    uri = unquote(uri.strip())
    if uri.startswith("model://"):
        relative = Path(uri[8:])
        candidates = [root / relative for root in model_roots]
    elif uri.startswith("file://") and allow_absolute:
        from urllib.parse import urlsplit
        from urllib.request import url2pathname
        parsed = urlsplit(uri)
        if parsed.netloc not in ("", "localhost"):
            raise ValueError(f"仅支持本地 file URI: {uri}")
        candidates = [Path(url2pathname(parsed.path))]
    elif "://" in uri:
        raise ValueError(f"无法打包 URI（仅支持本地相对路径与 model://）: {uri}")
    else:
        path = Path(uri)
        if (path.is_absolute() or (len(uri) > 1 and uri[1] == ":")) and not allow_absolute:
            raise ValueError(f"模型包含绝对资源路径，请改为相对路径: {uri}")
        candidates = [context / path]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise ValueError(f"缺失资源: {uri}")


def check_model_resources(directory: Path) -> None:
    model_file(directory)
    root_dir = directory.resolve()
    for sdf in directory.rglob("*.sdf"):
        root = ET.parse(sdf).getroot()
        # Nested includes would need model composition and dependency ordering.
        if root.find(".//include") is not None:
            raise ValueError("首版导入模型不支持嵌套 include；请先将依赖展开为自包含模型")
        for elem in resource_elements(root):
            if elem.text:
                resolved = local_uri(elem.text, sdf.parent, [directory.parent])
                if not resolved.is_relative_to(root_dir):
                    raise ValueError(f"模型依赖目录外资源，请先整理为自包含目录: {elem.text}")
        for elem in root.findall(".//collision/geometry/mesh/uri"):
            if elem.text:
                mesh = local_uri(elem.text,sdf.parent,[directory.parent])
                if mesh.suffix.lower() == ".obj":
                    lines = mesh.read_text(encoding="utf-8",errors="replace").splitlines()
                    normals = sum(line.startswith("vn ") for line in lines)
                    faces = [line.split()[1:] for line in lines if line.startswith("f ")]
                    if not normals or not faces or any(len(f)!=3 or any(len(v.split('/'))!=3 or not v.split('/')[2] for v in f) for f in faces):
                        raise ValueError(f"Fortress 碰撞 OBJ 需要三角面和显式法线，请先转换网格: {mesh.name}")
    for file in directory.rglob("*"):
        if file.is_symlink():
            raise ValueError("模型目录含符号链接，请复制实际资源后导入")
        if file.suffix.lower() in (".obj", ".mtl"):
            for line in file.read_text(encoding="utf-8", errors="replace").splitlines():
                words = line.split(maxsplit=1)
                if len(words) == 2 and words[0] in ("mtllib", "map_Kd", "map_Ka", "map_Ks", "map_bump", "bump"):
                    resolved = local_uri(words[1], file.parent, [directory.parent])
                    if not resolved.is_relative_to(root_dir):
                        raise ValueError(f"网格材质依赖目录外资源: {words[1]}")
        elif file.suffix.lower() == ".dae":
            root = ET.parse(file).getroot()
            for elem in root.findall(".//{*}library_images/{*}image/{*}init_from"):
                if elem.text:
                    resolved = local_uri(elem.text, file.parent, [directory.parent])
                    if not resolved.is_relative_to(root_dir):
                        raise ValueError(f"COLLADA 纹理依赖目录外资源: {elem.text}")


def resource_elements(root):
    tags = {"uri", "albedo_map", "normal_map", "metalness_map", "roughness_map", "emissive_map",
            "environment_map", "light_map", "ambient_occlusion_map", "diffuse_map", "specular_map"}
    return [elem for elem in root.iter() if elem.tag in tags]


def bundle_models(scene, data: dict, destination: Path, relative_to: Path) -> None:
    for obj, record in zip(scene.objects, data["objects"]):
        if obj.kind != "imported":
            continue
        source = (scene.base_dir / obj.source).resolve()
        check_model_resources(source)
        target = destination / obj.name / source.name
        if source != target.resolve():
            if target.resolve().is_relative_to(source):
                raise ValueError("导出目录不能位于导入模型目录内部")
            target.parent.mkdir(parents=True, exist_ok=True)
            # Existing saved-project assets are immutable snapshots.
            if target.exists():
                import uuid
                target = target.parent.parent / (obj.name + "_" + uuid.uuid4().hex[:8]) / source.name
            shutil.copytree(source, target)
        record["source"] = target.relative_to(relative_to).as_posix()


def discover_library(directory: str | Path) -> list[tuple[str, Path]]:
    root = Path(directory)
    if not root.is_dir():
        return []
    items = []
    for path in sorted(root.iterdir()):
        if path.is_file() and path.suffix.lower() in (".sdf", ".world", ".json"):
            items.append(("scene" if path.suffix.lower() == ".json" else "world", path))
        elif path.is_dir() and ((path / "model.sdf").is_file() or (path / "model.config").is_file()):
            items.append(("model", path))
    return items
