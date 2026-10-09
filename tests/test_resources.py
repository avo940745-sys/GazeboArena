from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
import pytest

from gazeboarena import make_preset, export_scene, load_scene, save_scene
from gazeboarena.resources import check_model_resources, discover_library
from gazeboarena.scene import SceneObject
from gazeboarena.validation import validate_world


def write_model(path,uri=None):
    path.mkdir(parents=True)
    geometry=f'<mesh><uri>{uri}</uri></mesh>' if uri else '<box><size>.1 .2 .3</size></box>'
    (path/"model.sdf").write_text(f'<sdf version="1.8"><model name="local"><static>true</static><link name="body"><collision name="c"><geometry>{geometry}</geometry></collision><visual name="v"><geometry>{geometry}</geometry></visual></link></model></sdf>',encoding="utf-8")


def test_imported_model_saved_and_exported_without_source(tmp_path):
    source=tmp_path/"源模型 空间"/"custom"
    write_model(source,"model://custom/mesh.obj")
    (source/"mesh.obj").write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nvn 0 0 1\nf 1//1 2//1 3//1\n")
    scene=make_preset("blank")
    scene.objects.append(SceneObject("local_obj","imported",pose=[.4,.3,0,0,0,.5],source=str(source)))
    project=tmp_path/"保存 工程"/"scene.json"
    save_scene(scene,project)
    restored=load_scene(project)
    assert not Path(restored.objects[-1].source).is_absolute()
    # Source disappears; only saved assets must be used.
    shutil.rmtree(source)
    path=export_scene(restored,tmp_path/"exports")
    moved=tmp_path/"另一目录"
    shutil.copytree(path,moved)
    assert validate_world(moved/"world.sdf")["resources"] == "passed"
    include=ET.parse(moved/"world.sdf").getroot().find("world/include")
    assert include.findtext("name")=="local_obj"
    assert list(map(float,include.findtext("pose").split())) == [.4,.3,0,0,0,.5]
    second=export_scene(load_scene(moved/"scene.json"),tmp_path/"reexport")
    assert validate_world(second/"world.sdf")["structure"] == "passed"


@pytest.mark.parametrize("uri",["missing.obj","https://example.com/mesh.obj","file:///tmp/mesh.obj","model://other/mesh.obj"])
def test_unbundlable_resources_fail(uri,tmp_path):
    source=tmp_path/"custom"; write_model(source,uri)
    with pytest.raises(ValueError): check_model_resources(source)


def test_model_config_selected_file(tmp_path):
    source=tmp_path/"custom"; write_model(source)
    (source/"model.sdf").rename(source/"v1.sdf")
    (source/"model.config").write_text('<model><name>custom</name><version>1</version><sdf version="1.8">v1.sdf</sdf></model>')
    check_model_resources(source)
    assert discover_library(tmp_path)==[("model",source)]


def test_export_failure_does_not_publish_partial_scene(tmp_path):
    scene=make_preset("blank"); scene.objects.append(SceneObject("bad","imported",source="not_found"))
    output=tmp_path/"out"
    with pytest.raises(ValueError): export_scene(scene,output)
    assert not list(output.iterdir())


def test_mesh_material_missing_texture_rejected(tmp_path):
    source=tmp_path/"custom"; write_model(source,"mesh.obj")
    (source/"mesh.obj").write_text("mtllib material.mtl\nv 0 0 0\n")
    (source/"material.mtl").write_text("map_Kd nonexistent.png\n")
    with pytest.raises(ValueError): check_model_resources(source)
