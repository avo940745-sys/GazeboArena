"""Editable presets extracted from the authorized rescue simulation."""
from importlib.resources import files
import xml.etree.ElementTree as ET

from .scene import Scene, SceneObject


def baseline() -> ET.Element:
    return ET.fromstring(files("gazeboarena").joinpath("data/rescue_baseline.sdf").read_text(encoding="utf-8"))


def make_preset(name: str = "rescue") -> Scene:
    if name not in ("rescue", "blank", "obstacles"):
        raise ValueError(f"未知预设: {name}")
    scene = Scene(name="rescue_2027" if name == "rescue" else "gazeboarena")
    if name != "rescue":
        floor = scene.add("flat")
        floor.name, floor.label = "floor", "基础地面"
        floor.params.update(length=3., width=3.)
        floor.color = "0.90 0.90 0.88 1"
        if name == "obstacles":
            for kind, x, y in (("ramp", -.7, .6), ("stairs", .5, .6), ("bump", -.6, -.2),
                               ("box", .6, -.2), ("cylinder", .8, -.7), ("robot", -1., -1.)):
                scene.add(kind, x, y)
        return scene
    for model in baseline().findall("world/model"):
        name = model.get("name")
        kind = "robot" if name == "rescue_bot" else ("core" if name.startswith("core_") else "box")
        params = {}
        if kind == "box":
            dimensions = [float(v) for v in model.findtext("link/visual/geometry/box/size").split()]
            params = dict(zip(("length", "width", "height"), dimensions))
        elif kind == "core":
            params = {"scale": 1.}
        rgba = model.findtext("link/visual/material/diffuse", "0.22 0.55 0.90 1")
        label = "救援小车" if kind == "robot" else name
        scene.objects.append(SceneObject(
            name, kind, label, [float(v) for v in model.findtext("pose").split()], params,
            color=rgba, collision=bool(model.findall("link/collision")),
            static=model.findtext("static", "false") == "true",
            mass=float(model.findtext("link/inertial/mass", ".1")), template=name))
    scene.description = "智能救援近似场景；机器人非原 CAD 导出，部分尺寸/物理参数为仿真假设。入口坡面仅视觉，无碰撞。"
    scene.validate()
    return scene
