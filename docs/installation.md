# 安装与运行

## Windows：编辑与导出

安装 Python 3.10+，在仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[gui]'
.\.venv\Scripts\gazeboarena.exe edit
```

也可运行 `./install.ps1`。使用虚拟环境中的完整命令路径，无需改变 PowerShell 执行策略。导出后，将完整目录复制到 Ubuntu。Windows 上不会尝试启动 Gazebo 或建立 SSH 连接。

## Ubuntu 22.04：完整使用

按照 [Gazebo Fortress 官方安装说明](https://gazebosim.org/docs/fortress/install_ubuntu/) 安装 `ignition-fortress`。确认 `ign gazebo --versions` 为 6.x。本项目不使用 Gazebo Classic，也不混装 Harmonic。

```bash
sudo apt-get install python3-venv libxcb-cursor0 libxkbcommon-x11-0 libxcb-xinerama0
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[gui]'
gazeboarena edit
```

也可运行 `bash install.sh`。安装脚本仅安装项目的 Python 依赖，不自动修改系统 Gazebo/ROS 软件源。

GUI 预览需要可用的桌面与 OpenGL 环境。虚拟机优先启用 3D 加速；软件渲染回退可显式设置 `LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=softpipe`。预览启动器清理 Qt 插件路径，避免编辑器的 Qt 6 或 OpenCV 路径干扰 Gazebo 的 Qt 5。

无界面检查可运行 `gazeboarena view world.sdf --headless --iterations 100`。带相机的服务器仍需渲染设备；没有桌面时可使用 `xvfb-run`，结果不能替代真实 GUI 验收。

## 可选 ROS 2

已有 ROS 2 Humble 时安装 `ros-humble-ros-gz`，在单独终端 source ROS 后启动桥接：

```bash
source /opt/ros/humble/setup.bash
ros2 run ros_gz_bridge parameter_bridge --ros-args -p config_file:=/absolute/path/bridge.yaml
```

桥接终端和控制器终端必须设置成预览日志 `session.json` 中的同一个 `IGN_PARTITION`。若使用导出目录的 `view.sh`，分区会在启动时打印。详见 [策略接入](policy-integration.md)。

## 诊断

- `validate` 检查 XML 世界结构和本地资源；`--native` 额外调用 Fortress `ign sdf -k`，不会把基础检查冒充原生验证。
- 本地模型必须自包含；无法打包的资源会给出具体 URI。外部世界可通过 `IGN_GAZEBO_RESOURCE_PATH` 指定额外本地搜索目录。
- `gazeboarena view` 的运行目录位于世界旁的 `runs/`。启动参数、分区与 Gazebo 输出分别写入 `session.json` 和 `gazebo.log`。
- 关闭编辑器会停止其当前预览；Fortress 会为服务器与 GUI 创建独立进程组，因此停止操作使用本轮专属进程标记识别自己启动的进程，不按名称批量结束其他仿真或同分区的外部控制器。
