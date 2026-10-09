"""SDF export shared by the desktop application and CLI."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime
from importlib.resources import files
from pathlib import Path
import json
import math
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET

from .presets import baseline
from .resources import bundle_models, model_file
from .scene import Scene, SceneObject


def child(parent, tag, text=None, **attrs):
    item = ET.SubElement(parent, tag, attrs)
    if text is not None:
        item.text = str(text)
    return item


def numbers(values):
    return " ".join(format(float(v), ".12g") for v in values)


def geometry(parent, shape, value):
    g = child(parent, "geometry")
    node = child(g, shape)
    if shape == "box":
        child(node, "size", numbers(value))
    elif shape == "cylinder":
        child(node, "radius", value[0]); child(node, "length", value[1])
    else:
        child(node, "uri", value)


def link_shape(model, obj, shape, value, pose=None, index=0):
    link = child(model, "link", name=f"body_{index}")
    if pose:
        child(link, "pose", numbers(pose))
    if not obj.static:
        inertial = child(link, "inertial")
        child(inertial, "mass", obj.mass)
        inertia = child(inertial, "inertia")
        if shape == "box":
            a, b, c = value
            diag = (obj.mass*(b*b+c*c)/12, obj.mass*(a*a+c*c)/12, obj.mass*(a*a+b*b)/12)
        else:
            r, h = value
            diag = (obj.mass*(3*r*r+h*h)/12, obj.mass*(3*r*r+h*h)/12, obj.mass*r*r/2)
        for key, v in zip(("ixx", "iyy", "izz"), diag): child(inertia, key, v)
        for key in ("ixy", "ixz", "iyz"): child(inertia, key, 0)
    if obj.collision:
        collision = child(link, "collision", name=f"collision_{index}")
        geometry(collision, shape, value)
        if obj.friction is not None:
            ode = child(child(child(collision, "surface"), "friction"), "ode")
            child(ode, "mu", obj.friction); child(ode, "mu2", obj.friction)
    visual = child(link, "visual", name=f"visual_{index}")
    geometry(visual, shape, value)
    material = child(visual, "material")
    child(material, "ambient", obj.color); child(material, "diffuse", obj.color)


def ramp_mesh(path: Path, length: float, width: float, height: float):
    # Closed triangular prism; top rises along local +x. All face normals point out.
    vertices = [(-length/2, -width/2, 0), (length/2, -width/2, 0), (length/2, -width/2, height),
                (-length/2, width/2, 0), (length/2, width/2, 0), (length/2, width/2, height)]
    faces = [(1,2,3), (4,6,5), (1,5,2), (1,4,5), (2,6,3), (2,5,6), (1,6,4), (1,3,6)]
    lines = ["v " + numbers(v) for v in vertices]
    for face in faces:
        a,b,c = [vertices[i-1] for i in face]
        u,v = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
        normal = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        norm = math.sqrt(sum(n*n for n in normal))
        lines.append("vn " + numbers(n/norm for n in normal))
    for index,face in enumerate(faces,1):
        lines.append("f " + " ".join(f"{i}//{index}" for i in face))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def model_element(obj: SceneObject, world_base: ET.Element, directory: Path, record: dict) -> ET.Element:
    if obj.kind == "imported":
        source = directory / record["source"]
        include = ET.Element("include")
        child(include, "uri", model_file(source).relative_to(directory).as_posix())
        child(include, "name", obj.name)
        child(include, "pose", numbers(obj.pose))
        return include
    if obj.template:
        source = world_base.find(f"model[@name='{obj.template}']")
        if source is None: raise ValueError(f"未知内置模型模板: {obj.template}")
        model = deepcopy(source)
        model.set("name", obj.name)
        model.find("pose").text = numbers(obj.pose)
        if obj.kind == "robot": return model
        if model.find("static") is None: child(model, "static", str(obj.static).lower())
        else: model.find("static").text = str(obj.static).lower()
        for link in model.findall("link"):
            original_size = link.findtext("visual/geometry/box/size")
            if not obj.collision:
                for c in link.findall("collision"): link.remove(c)
            elif not link.findall("collision"):
                g = link.find("visual/geometry")
                if g is not None:
                    child(link, "collision", name="added_collision").append(deepcopy(g))
            for size in link.findall(".//geometry/box/size"):
                size.text = numbers([obj.params[k] for k in ("length", "width", "height")])
            for mesh in link.findall(".//geometry/mesh"):
                scale = mesh.find("scale")
                if scale is None: scale = child(mesh, "scale")
                scale.text = numbers([obj.params.get("scale", 1.)] * 3)
            for material in link.findall("visual/material"):
                for tag in ("ambient", "diffuse"):
                    if material.find(tag) is not None: material.find(tag).text = obj.color
            mass = link.find("inertial/mass")
            if mass is not None:
                original_mass = float(mass.text)
                ratio = obj.mass/original_mass
                mass.text = str(obj.mass)
                if ratio != 1 or (obj.kind == "core" and obj.params["scale"] != 1):
                    for tag in ("ixx", "iyy", "izz", "ixy", "ixz", "iyz"):
                        i = link.find(f"inertial/inertia/{tag}")
                        if i is not None: i.text = str(float(i.text)*ratio*obj.params.get("scale",1.)**2)
            dimensions = [obj.params[k] for k in ("length", "width", "height")] if obj.kind == "box" else None
            changed_size = dimensions and original_size and any(abs(a-float(b)) > 1e-12 for a,b in zip(dimensions, original_size.split()))
            if not obj.static and dimensions and (mass is None or changed_size):
                inertial = link.find("inertial")
                if inertial is not None: link.remove(inertial)
                inertial = child(link, "inertial"); child(inertial, "mass", obj.mass)
                inertia = child(inertial, "inertia"); a,b,c = dimensions
                for key,value in zip(("ixx","iyy","izz"),(obj.mass*(b*b+c*c)/12,obj.mass*(a*a+c*c)/12,obj.mass*(a*a+b*b)/12)):
                    child(inertia,key,value)
                for key in ("ixy","ixz","iyz"): child(inertia,key,0)
            if obj.friction is not None:
                for c in link.findall("collision"):
                    surface = c.find("surface")
                    if surface is None: surface = child(c, "surface")
                    friction = surface.find("friction")
                    if friction is None: friction = child(surface, "friction")
                    ode = friction.find("ode")
                    if ode is None: ode = child(friction, "ode")
                    for tag in ("mu", "mu2"):
                        node = ode.find(tag)
                        if node is None: node = child(ode, tag)
                        node.text = str(obj.friction)
        return model
    model = ET.Element("model", name=obj.name)
    child(model, "static", str(obj.static).lower()); child(model, "pose", numbers(obj.pose))
    p = obj.params
    if obj.kind == "ramp":
        mesh_dir = directory / "models" / "arena_meshes"
        mesh_dir.mkdir(parents=True, exist_ok=True)
        ramp_mesh(mesh_dir / f"{obj.name}.obj", p["length"], p["width"], p["height"])
        link_shape(model, obj, "mesh", f"model://arena_meshes/{obj.name}.obj")
    elif obj.kind == "stairs":
        depth = p["length"]/p["count"]
        for i in range(p["count"]):
            h = (i+1)*p["height"]
            link_shape(model, obj, "box", (depth, p["width"], h),
                       (-p["length"]/2+(i+.5)*depth, 0, h/2, 0, 0, 0), i)
    elif obj.kind == "cylinder":
        link_shape(model, obj, "cylinder", (p["radius"], p["height"]))
    else:
        link_shape(model, obj, "box", [p[k] for k in ("length", "width", "height")])
    return model


def bridge_config(world: str) -> str:
    rows = [
        ("/simulation/stats", f"/world/{world}/stats", "ros_gz_interfaces/msg/WorldStatistics", "WorldStatistics", "GZ_TO_ROS"),
        ("/clock", "/clock", "rosgraph_msgs/msg/Clock", "Clock", "GZ_TO_ROS"),
        ("/camera/image", "/camera/image", "sensor_msgs/msg/Image", "Image", "GZ_TO_ROS"),
        ("/camera/gripper/image", "/camera/gripper/image", "sensor_msgs/msg/Image", "Image", "GZ_TO_ROS"),
        ("/imu", "/imu", "sensor_msgs/msg/Imu", "IMU", "GZ_TO_ROS"),
        ("/odom", "/odom", "nav_msgs/msg/Odometry", "Odometry", "GZ_TO_ROS"),
        ("/fork/joint_states", "/fork/joint_states", "sensor_msgs/msg/JointState", "Model", "GZ_TO_ROS"),
        ("/cmd_vel", "/cmd_vel", "geometry_msgs/msg/Twist", "Twist", "ROS_TO_GZ"),
    ]
    for side in ("left", "right"):
        rows.append((f"/fork/{side}/cmd", f"/fork/{side}/cmd", "std_msgs/msg/Float64", "Double", "ROS_TO_GZ"))
    for side, link, sensor in (("left", "left_fork", "left_contact"), ("right", "right_fork", "right_contact"),
                               ("front", "base_link", "bumper_contact")):
        rows.append((f"/fork/contact_{side}", f"/world/{world}/model/rescue_bot/link/{link}/sensor/{sensor}/contact",
                     "ros_gz_interfaces/msg/Contacts", "Contacts", "GZ_TO_ROS"))
    return "\n".join(f"- ros_topic_name: {r}\n  gz_topic_name: {g}\n  ros_type_name: {rt}\n  gz_type_name: ignition.msgs.{gt}\n  direction: {d}" for r,g,rt,gt,d in rows) + "\n"


def export_scene(scene: Scene, output: str | Path, bridge: bool = False) -> Path:
    scene.validate()
    if bridge and not any(o.kind == "robot" for o in scene.objects):
        raise ValueError("ROS 桥接配置需要内置救援小车")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Build privately and atomically publish a unique directory on success.
    with tempfile.TemporaryDirectory(prefix=".arena-export-", dir=output) as staging:
        directory = Path(staging)
        data = scene.to_dict()
        bundle_models(scene, data, directory / "models", directory)
        source_world = baseline().find("world")
        root = ET.Element("sdf", version="1.8")
        world = child(root, "world", name=scene.name)
        for item in source_world:
            if item.tag != "model": world.append(deepcopy(item))
        world.find("physics/max_step_size").text = str(scene.physics_step)
        for obj, record in zip(scene.objects, data["objects"]):
            world.append(model_element(obj, source_world, directory, record))
        if any(o.kind == "core" for o in scene.objects):
            mesh = directory / "models" / "rescue_assets"
            mesh.mkdir(parents=True, exist_ok=True)
            (mesh / "tetra.obj").write_bytes(files("gazeboarena").joinpath("data/rescue_assets/tetra.obj").read_bytes())
        ET.indent(root)
        ET.ElementTree(root).write(directory / "world.sdf", encoding="utf-8", xml_declaration=True)
        (directory / "scene.json").write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        if bridge: (directory / "bridge.yaml").write_text(bridge_config(scene.name), encoding="utf-8")
        gui = files("gazeboarena").joinpath("data/fortress_gui.config").read_text(encoding="utf-8")
        extent = max(scene.length,scene.width)
        gui = gui.replace("0 -3 3.4 0 0.847 1.57079632679", numbers((0,-extent,extent*3.4/3,0,.847,math.pi/2)))
        (directory / "arena_gui.config").write_text(gui,encoding="utf-8")
        (directory / "view.sh").write_text('#!/usr/bin/env bash\nset -euo pipefail\ncd -- "$(dirname -- "$0")"\nexport IGN_GAZEBO_RESOURCE_PATH="$PWD/models${IGN_GAZEBO_RESOURCE_PATH:+:$IGN_GAZEBO_RESOURCE_PATH}"\nexport IGN_PARTITION="gazeboarena-$(python3 -c \'import uuid; print(uuid.uuid4().hex)\')"\nenv -u QT_QPA_PLATFORM_PLUGIN_PATH -u QT_QPA_FONTDIR -u QT_PLUGIN_PATH ign gazebo -r --render-engine ogre --render-engine-gui ogre world.sdf\n', encoding="utf-8")
        script = directory / "view.sh"
        script.write_text(script.read_text(encoding="utf-8").replace('env -u QT_QPA', 'echo "IGN_PARTITION=$IGN_PARTITION"\nenv -u QT_QPA').replace('ogre world.sdf', 'ogre --gui-config arena_gui.config world.sdf'), encoding="utf-8")
        from .validation import validate_world
        validate_world(directory / "world.sdf")
        stem = datetime.now().strftime("output_%Y%m%d_%H%M%S")
        i = 0
        while True:
            target = output / (stem if i == 0 else f"{stem}_{i}")
            if not target.exists():
                try:
                    directory.rename(target)
                    break
                except FileExistsError: pass
            i += 1
        return target
