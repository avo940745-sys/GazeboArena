"""Native Fortress smoke/contact checks used locally and in CI.

Produces a JSON report; tests use fresh, isolated sessions and no controller.
"""
from pathlib import Path
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

from gazeboarena import make_preset, export_scene, save_scene, load_scene
from gazeboarena.runtime import GazeboSession, gazebo_environment
from gazeboarena.scene import SceneObject
from gazeboarena.validation import validate_world


def read_topic(session, topic, seconds=3):
    env=gazebo_environment(session.world,session.partition)
    try:
        result=subprocess.run(["ign","topic","-e","-t",topic],env=env,capture_output=True,timeout=seconds)
        data=result.stdout
    except subprocess.TimeoutExpired as error:
        data=error.stdout or b""
    return data.decode("utf-8",errors="replace")


def ready(session, world_name):
    deadline=time.monotonic()+35
    while time.monotonic()<deadline:
        if session.poll() is not None:
            raise RuntimeError("Gazebo 在加载期间退出:\n"+session.log_tail())
        text=read_topic(session,f"/world/{world_name}/stats",2)
        if re.search(r"iterations:\s*[1-9][0-9]*",text): return text
    raise RuntimeError("未观察到推进中的 Fortress 统计:\n"+session.log_tail())


def last_position(text,name):
    # Gazebo protobuf text may omit zero components; default them to zero.
    matches=list(re.finditer(r'name:\s*"'+re.escape(name)+r'"[\s\S]*?position\s*\{([^}]*)\}',text))
    if not matches: raise RuntimeError(f"动态位姿缺失: {name}")
    block=matches[-1].group(1)
    return {axis:float(m.group(1)) if (m:=re.search(r'\b'+axis+r':\s*([-+\deE.]+)',block)) else 0. for axis in ('x','y','z')}


def main():
    report={"presets":[],"contact":{},"import":{},"sessions":[]}
    root=Path("generated/fortress-verification").resolve(); root.mkdir(parents=True,exist_ok=True)
    versions=subprocess.check_output(["ign","gazebo","--versions"],text=True).strip()
    if not re.search(r"\b6\.",versions): raise RuntimeError("本检查仅面向 Gazebo Fortress 6.x")
    report["gazebo_version"]=versions
    for preset in ("blank","rescue","obstacles"):
        scene=make_preset(preset)
        original=export_scene(scene,root/preset)
        moved=root/(preset+"-relocated")
        if moved.exists():
            moved=root/(preset+"-relocated-"+str(time.time_ns()))
        shutil.copytree(original,moved)
        native=validate_world(moved/"world.sdf",native=True)
        session=GazeboSession(moved/"world.sdf",headless=True).start()
        try:
            stats=ready(session,scene.name)
            if any(o.kind=="robot" for o in scene.objects):
                required=("/camera/image","/camera/gripper/image","/odom","/imu","/fork/joint_states")
                deadline=time.monotonic()+30
                while True:
                    topics=subprocess.check_output(["ign","topic","-l"],env=gazebo_environment(session.world,session.partition),text=True,timeout=12)
                    missing=[topic for topic in required if topic not in topics.splitlines()]
                    if not missing: break
                    if session.poll() is not None or time.monotonic()>deadline:
                        raise RuntimeError(f"传感器话题缺失: {missing}\n"+session.log_tail())
                    time.sleep(.3)
                imu=read_topic(session,"/imu",3)
                if "orientation" not in imu: raise RuntimeError("IMU 未发布数据")
                for camera in ("/camera/image","/camera/gripper/image"):
                    image=subprocess.check_output(["ign","topic","-e","-n","1","-t",camera],
                        env=gazebo_environment(session.world,session.partition),timeout=12)
                    if b'width: 640' not in image or b'height: 480' not in image or b'data:' not in image:
                        raise RuntimeError(f"双相机图像数据无效: {camera}")
            report["presets"].append({"name":preset,"native":native["native"],"loading":"passed","relocated":True})
        finally:
            session.stop()
            report["sessions"].append({"partition":session.partition,"exit":session.poll()})
        print(f"Preset {preset}: native + loading + relocation passed",flush=True)
    scene=make_preset("blank")
    ramp=scene.add("ramp",0,0); ramp.friction=1.
    stairs=scene.add("stairs",0,.8); stairs.friction=1.
    for name,x,y in (("probe_floor",.8,0),("probe_ramp",0,0),("probe_stairs",.0625,.8)):
        obj=scene.add("box",x,y); obj.name=name; obj.params=dict(length=.04,width=.04,height=.04)
        obj.pose[2]=.35; obj.static=False; obj.mass=.035; obj.friction=1.
    path=export_scene(scene,root/"contact")
    validate_world(path/"world.sdf",native=True)
    session=GazeboSession(path/"world.sdf",headless=True).start()
    try:
        ready(session,scene.name)
        positions=read_topic(session,f"/world/{scene.name}/dynamic_pose/info",5)
        for name,expected in (("probe_floor",.02),("probe_ramp",.05),("probe_stairs",.08)):
            pose=last_position(positions,name)
            if name == "probe_ramp":
                # The box tilts/slides slightly on impact. Compare to the actual
                # analytical surface at its measured x, rather than spawn x.
                if abs(pose["x"]) > .17 or abs(pose["y"]) > .13:
                    raise RuntimeError("斜坡接触测试物块已离开有效坡面")
                expected=.03+.15*pose["x"]+.02*math.sqrt(1+.15**2)
            if abs(pose["z"]-expected)>.003:
                raise RuntimeError(f"接触高度不符: {name} {pose}, expected z={expected}")
            report["contact"][name]={"pose":pose,"expected_z":expected,"passed":True}
        print("Physical floor/ramp/stairs contact passed",flush=True)
    finally: session.stop()
    # Exercise a genuine external model with preserved local mesh URI after relocation.
    source=root/"import-source"/"sample_model"; source.mkdir(parents=True,exist_ok=True)
    (source/"model.sdf").write_text('<sdf version="1.8"><model name="external"><static>true</static><link name="body"><collision name="c"><geometry><box><size>.1 .1 .1</size></box></geometry></collision><visual name="v"><geometry><box><size>.1 .1 .1</size></box></geometry></visual></link></model></sdf>')
    scene=make_preset("blank"); scene.objects.append(SceneObject("external_instance","imported",pose=[0,0,.05,0,0,.3],source=str(source)))
    project=root/"import-project"/"scene.json"; save_scene(scene,project)
    imported=export_scene(load_scene(project),root/"import-export")
    native=validate_world(imported/"world.sdf",True)
    session=GazeboSession(imported/"world.sdf",True).start()
    try: ready(session,scene.name); report["import"]={"native":native["native"],"loading":"passed"}
    finally: session.stop()
    assert len({s["partition"] for s in report["sessions"]})==3
    report["passed"]=True
    (root/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return 0


if __name__=="__main__":
    sys.exit(main())
