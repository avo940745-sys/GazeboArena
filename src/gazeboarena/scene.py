"""Versioned editable scenes. Positions are metres; angles are radians."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import copy
import json
import math
import re

KINDS = ("box", "flat", "ramp", "stairs", "bump", "cylinder", "core", "robot", "imported")
LABELS = {"box": "箱体", "flat": "平地", "ramp": "实体斜坡", "stairs": "台阶",
          "bump": "减速带", "cylinder": "圆柱", "core": "核心物资", "robot": "救援小车", "imported": "本地模型"}
DEFAULTS = {
    "box": dict(length=.20, width=.20, height=.10),
    "flat": dict(length=1., width=1., height=.03),
    "ramp": dict(length=.40, width=.30, height=.06),
    "stairs": dict(length=.50, width=.30, height=.02, count=4),
    "bump": dict(length=.20, width=.018, height=.016),
    "cylinder": dict(radius=.08, height=.15),
    "core": dict(scale=1.), "robot": {}, "imported": {},
}


@dataclass
class SceneObject:
    name: str
    kind: str
    label: str = ""
    pose: list[float] = field(default_factory=lambda: [0.] * 6)
    params: dict = field(default_factory=dict)
    color: str = "0.22 0.55 0.90 1"
    collision: bool = True
    static: bool = True
    mass: float = .1
    friction: float | None = None
    template: str | None = None
    source: str | None = None


@dataclass
class Scene:
    version: int = 1
    name: str = "gazeboarena"
    length: float = 3.
    width: float = 3.
    physics_step: float = .001
    objects: list[SceneObject] = field(default_factory=list)
    description: str = ""
    base_dir: Path = field(default_factory=Path.cwd, repr=False, compare=False)

    def to_dict(self) -> dict:
        return {"version": self.version, "name": self.name, "length": self.length,
                "width": self.width, "physics_step": self.physics_step,
                "description": self.description, "objects": [asdict(o) for o in self.objects]}

    @classmethod
    def from_dict(cls, data: dict, base_dir: Path | None = None) -> Scene:
        if data.get("version") != 1:
            raise ValueError("不支持的 scene.json 版本 / unsupported scene version")
        values = dict(data)
        values["objects"] = [SceneObject(**o) for o in values.get("objects", [])]
        values["base_dir"] = base_dir or Path.cwd()
        scene = cls(**values)
        scene.validate()
        return scene

    def validate(self) -> None:
        def finite(value):
            return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)
        def positive(value):
            return finite(value) and value > 0
        if self.version != 1 or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", self.name):
            raise ValueError("场景名需为字母、数字、下划线或连字符，且不以数字开头")
        if not all(positive(v) for v in (self.length, self.width, self.physics_step)):
            raise ValueError("场地尺寸和物理步长必须为有限正数")
        names = set()
        for o in self.objects:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", o.name) or o.name in names:
                raise ValueError(f"对象名称非法或重复: {o.name}")
            names.add(o.name)
            if o.kind not in KINDS or len(o.pose) != 6 or not all(finite(v) for v in o.pose):
                raise ValueError(f"无效对象类型或位姿: {o.name}")
            if not isinstance(o.collision, bool) or not isinstance(o.static, bool):
                raise ValueError(f"碰撞/static 必须为布尔值: {o.name}")
            if o.kind in ("ramp", "stairs", "flat", "bump") and not o.static:
                raise ValueError(f"地形组件必须为静态对象: {o.name}")
            for key in DEFAULTS[o.kind]:
                if not positive(o.params.get(key)):
                    raise ValueError(f"{o.name}: {key} 必须为有限正数")
            if o.kind == "stairs" and (not isinstance(o.params["count"], int) or not 1 <= o.params["count"] <= 100):
                raise ValueError("台阶数量必须为 1–100 的整数")
            try:
                rgba = [float(v) for v in o.color.split()]
            except (ValueError, AttributeError):
                rgba = []
            if len(rgba) != 4 or not all(finite(v) and 0 <= v <= 1 for v in rgba):
                raise ValueError(f"无效 RGBA 颜色: {o.name}")
            if not positive(o.mass) or (o.friction is not None and not (finite(o.friction) and o.friction >= 0)):
                raise ValueError(f"质量/摩擦系数非法: {o.name}")
            if o.kind == "imported" and not o.source:
                raise ValueError(f"模型缺少来源目录: {o.name}")
            if o.template and (o.kind == "imported" or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", o.template)):
                raise ValueError(f"非法模板: {o.name}")
            if o.kind == "robot" and o.template != "rescue_bot":
                raise ValueError("内置小车必须使用 rescue_bot 模板")
            if o.kind == "core" and o.template not in ("core_1", "core_2"):
                raise ValueError("核心物资必须使用内置四面体模板")
            if o.template == "rescue_bot" and o.kind != "robot":
                raise ValueError("小车模板只能用于 robot 对象")
        robots = [o for o in self.objects if o.kind == "robot"]
        if len(robots) > 1:
            raise ValueError("首版每个场景最多放置一台内置救援小车")
        if robots and robots[0].name != "rescue_bot":
            raise ValueError("内置小车名称固定为 rescue_bot，以保持传感器话题一致")

    def add(self, kind: str, x: float = 0., y: float = 0.) -> SceneObject:
        if kind not in DEFAULTS or kind == "imported":
            raise ValueError(f"不能直接添加类型: {kind}")
        if kind == "robot" and any(o.kind == "robot" for o in self.objects):
            raise ValueError("场景已包含救援小车")
        number = 1
        names = {o.name for o in self.objects}
        while f"{kind}_{number}" in names:
            number += 1
        name = "rescue_bot" if kind == "robot" else f"{kind}_{number}"
        params = copy.deepcopy(DEFAULTS[kind])
        z = params.get("height", 0.) / 2 if kind in ("box", "bump", "cylinder") else 0.
        if kind == "flat":
            z = -params["height"] / 2
        if kind == "core":
            z = .001
        obj = SceneObject(name, kind, LABELS[kind], [x, y, z, 0., 0., 0.], params,
                          static=kind not in ("core", "robot"),
                          mass=.025 if kind == "core" else .1,
                          template="rescue_bot" if kind == "robot" else ("core_1" if kind == "core" else None))
        self.objects.append(obj)
        return obj


def load_scene(path: str | Path) -> Scene:
    path = Path(path).resolve()
    return Scene.from_dict(json.loads(path.read_text(encoding="utf-8")), path.parent)


def save_scene(scene: Scene, path: str | Path) -> Path:
    """Bundle imported model folders next to JSON, making saved projects movable."""
    from .resources import bundle_models
    scene.validate()
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = scene.to_dict()
    bundle_models(scene, data, path.parent / (path.stem + "_assets"), path.parent)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(path)
    return path
