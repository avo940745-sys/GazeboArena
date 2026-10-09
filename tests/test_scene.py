from copy import deepcopy
from pathlib import Path
import json
import shutil
import xml.etree.ElementTree as ET

import pytest

from gazeboarena import make_preset, load_scene, save_scene, export_scene
from gazeboarena.presets import baseline
from gazeboarena.scene import Scene, SceneObject
from gazeboarena.validation import validate_world


def test_rescue_geometry_and_interfaces_preserved(tmp_path):
    scene = make_preset("rescue")
    path = export_scene(scene,tmp_path,bridge=True)
    before = baseline().find("world")
    after = ET.parse(path/"world.sdf").getroot().find("world")
    assert len(before.findall("model")) == len(after.findall("model")) == 38
    for original in before.findall("model"):
        model = after.find(f"model[@name='{original.get('name')}']")
        assert [float(x) for x in original.findtext("pose").split()] == pytest.approx([float(x) for x in model.findtext("pose").split()])
        assert len(model.findall(".//collision")) == len(original.findall(".//collision"))
        sizes = model.findall(".//box/size")
        originals = original.findall(".//box/size")
        assert len(sizes) == len(originals)
        for size, expected in zip(sizes, originals):
            assert list(map(float,size.text.split())) == pytest.approx(list(map(float,expected.text.split())))
    bot = after.find("model[@name='rescue_bot']")
    assert len(bot.findall(".//sensor")) == 6
    assert len(bot.findall("plugin")) == 4
    assert float(bot.findtext("plugin[@name='ignition::gazebo::systems::DiffDrive']/wheel_separation")) == .13
    assert after.findtext("physics/max_step_size") == "0.001"
    assert "weights" not in (path/"scene.json").read_text()
    assert validate_world(path/"world.sdf")["resources"] == "passed"


@pytest.mark.parametrize("preset",["rescue","blank","obstacles"])
def test_save_load_and_export_relocation(preset,tmp_path):
    scene = make_preset(preset)
    json_path = tmp_path/"中文 空间"/"scene.json"
    save_scene(scene,json_path)
    restored = load_scene(json_path)
    assert restored.to_dict() == scene.to_dict()
    path = export_scene(restored,tmp_path/"exports")
    moved = tmp_path/"移动 场景"
    shutil.copytree(path,moved)
    assert validate_world(moved/"world.sdf")["structure"] == "passed"
    assert load_scene(moved/"scene.json").to_dict() == restored.to_dict()


@pytest.mark.parametrize("field,value",[("length",0),("width",-2),("physics_step",float("nan"))])
def test_invalid_scene_dimensions(field,value):
    scene=make_preset("blank"); setattr(scene,field,value)
    with pytest.raises(ValueError): scene.validate()


@pytest.mark.parametrize("mutation",["duplicate","robots","nan_pose","version","bad_color","negative_mass","invalid_count","kind"])
def test_reject_invalid_objects(mutation):
    scene=make_preset("obstacles")
    if mutation == "duplicate": scene.objects.append(deepcopy(scene.objects[0]))
    elif mutation == "robots": scene.objects.append(deepcopy(scene.objects[-1])); scene.objects[-1].name="other_bot"
    elif mutation == "nan_pose": scene.objects[0].pose[0]=float("nan")
    elif mutation == "version": scene.version=2
    elif mutation == "bad_color": scene.objects[0].color="1 2 3 4"
    elif mutation == "negative_mass": scene.objects[0].mass=-.1
    elif mutation == "invalid_count": next(o for o in scene.objects if o.kind=="stairs").params["count"]=1.5
    elif mutation == "kind": scene.objects[0].kind="unknown"
    with pytest.raises(ValueError): scene.validate()


def test_scene_version_rejected():
    with pytest.raises(ValueError): Scene.from_dict({"version":42})


def test_repeated_exports_never_overwrite(tmp_path):
    scene=make_preset("blank")
    a=export_scene(scene,tmp_path); b=export_scene(scene,tmp_path)
    assert a != b and a.is_dir() and b.is_dir()


def test_robot_pose_override_leaves_link_geometry(tmp_path):
    scene=make_preset("rescue")
    robot=next(o for o in scene.objects if o.kind=="robot")
    robot.pose=[.1,.2,.03,0,0,.75]
    world=ET.parse(export_scene(scene,tmp_path)/"world.sdf").getroot()
    result=world.find("world/model[@name='rescue_bot']")
    assert list(map(float,result.findtext("pose").split())) == robot.pose
    assert result.findtext("link[@name='left_wheel']/pose") == baseline().findtext("world/model[@name='rescue_bot']/link[@name='left_wheel']/pose")


def test_bridge_world_names_and_no_truth_topic(tmp_path):
    scene=make_preset("obstacles"); scene.name="custom_arena"
    yaml=(export_scene(scene,tmp_path,True)/"bridge.yaml").read_text()
    assert "/world/custom_arena/stats" in yaml
    assert "/world/custom_arena/model/rescue_bot/link/left_fork" in yaml
    assert "pose/info" not in yaml
    with pytest.raises(ValueError): export_scene(make_preset("blank"),tmp_path,True)


def test_ramp_and_stairs_real_geometry(tmp_path):
    path=export_scene(make_preset("obstacles"),tmp_path)
    root=ET.parse(path/"world.sdf").getroot()
    ramp=root.find("world/model[@name='ramp_1']")
    assert ramp.findtext("link/collision/geometry/mesh/uri") == ramp.findtext("link/visual/geometry/mesh/uri")
    mesh=path/"models/arena_meshes/ramp_1.obj"
    assert len([x for x in mesh.read_text().splitlines() if x.startswith("v ")]) == 6
    assert len([x for x in mesh.read_text().splitlines() if x.startswith("f ")]) == 8
    stairs=root.find("world/model[@name='stairs_1']")
    assert len(stairs.findall("link/collision")) == 4


def test_missing_mesh_fails_resource_validation(tmp_path):
    path=export_scene(make_preset("rescue"),tmp_path)
    (path/"models/rescue_assets/tetra.obj").unlink()
    with pytest.raises(ValueError,match="缺失资源"): validate_world(path/"world.sdf")
