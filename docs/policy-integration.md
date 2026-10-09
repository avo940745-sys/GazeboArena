# 外部控制策略接入

GazeboArena 负责生成环境和模型，策略作为独立程序运行。无需使用某一种策略框架；可以连接 Gazebo Transport，也可以启用 ROS 2 Humble 桥接。

## 内置救援小车接口

| 接口 | ROS 2 类型 | 方向 |
| --- | --- | --- |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | 策略 → Gazebo |
| `/fork/left/cmd`、`/fork/right/cmd` | `std_msgs/msg/Float64` | 策略 → Gazebo |
| `/camera/image`、`/camera/gripper/image` | `sensor_msgs/msg/Image` | Gazebo → 策略 |
| `/odom` | `nav_msgs/msg/Odometry` | Gazebo → 策略 |
| `/imu` | `sensor_msgs/msg/Imu` | Gazebo → 策略 |
| `/fork/joint_states` | `sensor_msgs/msg/JointState` | Gazebo → 策略 |
| `/fork/contact_left`、`right`、`front` | `ros_gz_interfaces/msg/Contacts` | Gazebo → 策略 |
| `/simulation/stats` | `ros_gz_interfaces/msg/WorldStatistics` | Gazebo → 策略 |
| `/clock` | `rosgraph_msgs/msg/Clock` | Gazebo → 策略 |

小车采用差速驱动，`linear.x` 和 `angular.z` 控制运动；这不是完整麦克纳姆动力学模型。夹爪关节命令单位为米，范围 `[-0.046, 0]`，0 为张开。双侧执行器分别控制，接触约束是真实物理约束，不使用吸附或物块瞬移。

## 示例流程

```bash
gazeboarena export --preset rescue --bridge --output generated
gazeboarena view /absolute/path/output_directory/world.sdf
```

从终端输出或本轮 `runs/.../session.json` 获取 `IGN_PARTITION`，在桥接终端中设置：

```bash
export IGN_PARTITION=gazeboarena-实际分区值
source /opt/ros/humble/setup.bash
ros2 run ros_gz_bridge parameter_bridge --ros-args -p config_file:=/absolute/path/bridge.yaml
```

策略终端同样设置分区并 source ROS。最小运动命令：

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}, angular: {z: 0.0}}'
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.0}, angular: {z: 0.0}}'
```

使用原生 Transport 可以执行 `ign topic -l` 和 `ign topic -t /cmd_vel -m ignition.msgs.Twist -p 'linear: {x: 0.05}'`。务必使用同一分区，不能拿默认分区的话题列表判断当前预览是否正常。

桥接配置不包含模型位姿真值评分话题。本项目不将原控制器在固定救援场景的成功记录当作新地形验证结果；使用者应根据自己的任务定义评测指标和传感器约束。
