"""Optional Humble bridge smoke test, isolated from existing ROS sessions."""
from pathlib import Path
import os
import signal
import subprocess
import shlex
import time
from gazeboarena import make_preset,export_scene
from gazeboarena.runtime import GazeboSession,gazebo_environment
from verify_fortress import ready

scene=make_preset('rescue')
path=export_scene(scene,'generated/bridge-verification',bridge=True)
session=GazeboSession(path/'world.sdf',True).start()
bridge=None
env=gazebo_environment(session.world,session.partition)
env['ROS_DOMAIN_ID']='172'
env['ROS_LOCALHOST_ONLY']='1'
env['ROS2CLI_DISABLE_DAEMON']='1'
try:
    ready(session,scene.name)
    config=shlex.quote(str(path/'bridge.yaml'))
    log=(path/'bridge.log').open('w')
    bridge=subprocess.Popen(['bash','-c',f'source /opt/ros/humble/setup.bash; exec ros2 run ros_gz_bridge parameter_bridge --ros-args -p config_file:={config}'],
        env=env,start_new_session=True,stdout=log,stderr=subprocess.STDOUT)
    for topic,msg in (('/imu','sensor_msgs/msg/Imu'),('/odom','nav_msgs/msg/Odometry'),('/clock','rosgraph_msgs/msg/Clock')):
        command=f'source /opt/ros/humble/setup.bash; ros2 topic echo {topic} {msg} --once'
        result=subprocess.run(['bash','-c',command],env=env,capture_output=True,text=True,timeout=35)
        if result.returncode or not result.stdout.strip():raise RuntimeError(f'Bridge stream missing: {topic} '+result.stderr)
        print('ROS stream passed:',topic,flush=True)
    session.stop()
    # A controller/bridge may share the transport partition, but it is external
    # to the preview subtree and must not be killed by the preview manager.
    assert bridge.poll() is None
    print('Bridge mapping and external-process preservation passed',flush=True)
finally:
    session.stop()
    if bridge:
        os.killpg(bridge.pid,signal.SIGTERM)
        try:bridge.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(bridge.pid,signal.SIGKILL);bridge.wait()
        log.close()
