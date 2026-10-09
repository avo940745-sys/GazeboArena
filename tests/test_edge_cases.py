from pathlib import Path
from copy import deepcopy
import xml.etree.ElementTree as ET
import pytest

from gazeboarena import make_preset,export_scene
from gazeboarena.cli import main
from gazeboarena.exporter import ramp_mesh
from gazeboarena.resources import check_model_resources
from gazeboarena.validation import validate_world


def test_ramp_mesh_is_closed_and_outward_wound(tmp_path):
    path=tmp_path/"ramp.obj"; ramp_mesh(path,.4,.3,.06)
    vertices=[]; faces=[]
    for line in path.read_text().splitlines():
        values=line.split()
        if values[0]=="v": vertices.append(list(map(float,values[1:])))
        if values[0]=="f": faces.append([int(v.split('/')[0])-1 for v in values[1:]])
    volume=0.
    edges={}
    for face in faces:
        a,b,c=[vertices[i] for i in face]
        volume+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6
        for i,j in zip(face,face[1:]+face[:1]): edges[(i,j)]=edges.get((i,j),0)+1
    assert volume==pytest.approx(.4*.3*.06/2)
    assert all(edges.get((j,i),0)==count for (i,j),count in edges.items())


def test_external_world_accepts_existing_absolute_local_resources(tmp_path):
    mesh=tmp_path/"mesh.obj"; mesh.write_text("v 0 0 0\n")
    world=tmp_path/"world.sdf"
    world.write_text(f'<sdf version="1.8"><world name="external"><model name="box"><link name="body"><visual name="v"><geometry><mesh><uri>{mesh.as_posix()}</uri></mesh></geometry></visual></link></model></world></sdf>')
    assert validate_world(world)["structure"]=="passed"


def test_cli_malformed_xml_reports_error_without_traceback(tmp_path,capsys):
    path=tmp_path/"bad.sdf";path.write_text("<broken")
    assert main(["validate",str(path)])==2
    assert "错误" in capsys.readouterr().err


def test_changed_dynamic_target_has_updated_inertia(tmp_path):
    scene=make_preset("rescue")
    obj=next(o for o in scene.objects if o.name=="normal_1")
    obj.params.update(length=.12,width=.08,height=.06);obj.mass=.2
    root=ET.parse(export_scene(scene,tmp_path)/"world.sdf").getroot()
    inertia=root.find("world/model[@name='normal_1']/link/inertial/inertia")
    assert float(inertia.findtext("ixx"))==pytest.approx(.2*(.08**2+.06**2)/12)


def test_collada_missing_texture_rejected(tmp_path):
    model=tmp_path/"local";model.mkdir()
    (model/"model.sdf").write_text('<sdf version="1.8"><model name="m"><link name="b"><visual name="v"><geometry><mesh><uri>mesh.dae</uri></mesh></geometry></visual></link></model></sdf>')
    (model/"mesh.dae").write_text('<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema"><library_images><image id="t"><init_from>missing.png</init_from></image></library_images></COLLADA>')
    with pytest.raises(ValueError,match="缺失资源"):check_model_resources(model)


def test_collision_obj_without_normals_rejected(tmp_path):
    model=tmp_path/"local";model.mkdir()
    (model/"model.sdf").write_text('<sdf version="1.8"><model name="m"><link name="b"><collision name="c"><geometry><mesh><uri>mesh.obj</uri></mesh></geometry></collision></link></model></sdf>')
    (model/"mesh.obj").write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
    with pytest.raises(ValueError,match="显式法线"):check_model_resources(model)
