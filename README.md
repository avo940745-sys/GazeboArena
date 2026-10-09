# GazeboArena

**面向机器人策略验证的 Gazebo 地形与场景工具。**

[English](README_en.md) · [安装指南](docs/installation.md) · [模型与地形库](docs/resources.md) · [外部策略接入](docs/policy-integration.md) · [v0.1.0](https://github.com/avo940745-sys/GazeboArena/releases/tag/v0.1.0)

GazeboArena 将场景搭建、地形参数编辑、模型资源管理和 SDF 导出放在同一个桌面工具中。你可以从救援场地或空白场地开始，布置障碍、调整机器人出生位姿，再在 Gazebo Fortress 中连接自己的控制策略。

项目参考 [ArenaX](https://github.com/Lain-Ego0/ArenaX) 的编辑流程与交互组织，自行实现 Gazebo 版本；救援预设与程序化模型来自原智能救援仿真平台。首版专注于环境构建与预览，策略由使用者自行接入。

## 界面与仿真示例

### 蓝白色桌面编辑器

左侧选择组件、对象和本地资源，中间布置俯视场景，右侧修改参数、保存和导出。首版界面使用简体中文。

![GazeboArena Windows 场景编辑器](docs/images/editor.png)

### 智能救援场景

3 米场地、围栏、出发区、安全区、减速带、八个目标和救援小车；导出后在独立 Gazebo 窗口中预览。

![Gazebo Fortress 中的智能救援场景](docs/images/gazebo-rescue.png)

### 基础越障场景

实体斜坡、台阶、减速带、箱体和圆柱同时具有视觉与碰撞几何，可用于搭建自己的接触与越障测试环境。

![Gazebo Fortress 中的基础越障场景](docs/images/gazebo-obstacles.png)

## 功能与运行环境

| 能力 | 当前支持 |
| --- | --- |
| 场景编辑 | 拖放、移动、旋转、复制、删除、缩放、5 cm 网格吸附、撤销与重做 |
| 地形组件 | 平地、实体斜坡、台阶、减速带、箱体、圆柱，以及救援物资 |
| 参数编辑 | 场地尺寸、对象尺寸和六维位姿；适用对象的颜色、碰撞、质量、摩擦与静态属性 |
| 工程保存 | 带版本号的 `scene.json`，保存后可继续编辑 |
| 资源管理 | 本地模型目录整体导入、地形库浏览、外部完整 `.sdf` / `.world` 预览 |
| 场景交付 | SDF 1.8 世界、工程文件和所需资源一起打包，相对路径可迁移 |
| 仿真预览 | 独立 Gazebo 窗口、独立 Transport 分区、每轮日志和自身进程清理 |
| 策略接口 | Gazebo Transport；可选生成内置小车的 ROS 2 Humble 桥接配置 |

| 平台 | 支持范围 |
| --- | --- |
| Windows | 编辑、保存、资源导入、导出与基础检查 |
| Ubuntu 22.04 + Gazebo Fortress 6.x | 编辑、导出、原生检查与完整预览 |
| ROS 2 Humble | 可选桥接；编辑与导出不依赖 ROS |

核心命令需要 Python 3.10+。本版 PySide6 Widgets 编辑器支持 Python 3.10–3.13，推荐使用 Python 3.10。

## 快速开始

### Windows PowerShell

先安装 Git，以及 Python 3.10–3.13 或 `uv`，然后运行：

```powershell
git clone https://github.com/avo940745-sys/GazeboArena.git
cd GazeboArena
.\install.ps1
```

脚本安装后打开编辑器。只安装、不启动时使用 `.\install.ps1 -NoRun`。已有 `uv` 时，脚本自动选择 Python 3.10；否则使用当前受支持的 Python。已有 `.venv` 会保留。

后续无需激活虚拟环境即可启动或导出：

```powershell
.\.venv\Scripts\gazeboarena.exe edit --preset obstacles
.\.venv\Scripts\gazeboarena.exe export --preset rescue --bridge --output generated
```

### Ubuntu 22.04

先按 [Fortress 官方说明](https://gazebosim.org/docs/fortress/install_ubuntu/) 安装 Gazebo；项目安装脚本只安装 Python 依赖。

```bash
sudo apt-get install git python3-venv libxcb-cursor0 libxkbcommon-x11-0 libxcb-xinerama0
git clone https://github.com/avo940745-sys/GazeboArena.git
cd GazeboArena
bash install.sh
```

只安装时使用 `bash install.sh --no-run`。后续在终端中激活环境：

```bash
source .venv/bin/activate
gazeboarena edit --preset rescue
```

完整预览需要可用的桌面与 OpenGL 环境。手动安装、虚拟机渲染和依赖诊断见 [安装指南](docs/installation.md)。

## 预设与地形组件

| 预设 | 内容 |
| --- | --- |
| `rescue` | 原 3 × 3 m 救援布局，38 个模型，含八个目标和一台救援小车 |
| `blank` | 3 × 3 m 空白场地，适合从头搭建 |
| `obstacles` | 平地、实体斜坡、台阶、减速带、箱体、圆柱和救援小车 |

```bash
gazeboarena edit --preset blank
gazeboarena edit --preset obstacles
gazeboarena export --preset rescue --bridge --output generated
```

基础组件的默认尺寸如下，长度单位均为米：

| 组件 | 默认参数 |
| --- | --- |
| 平地 `flat` | 长 1.00、宽 1.00、厚 0.03 |
| 实体斜坡 `ramp` | 长 0.40、宽 0.30、高 0.06 |
| 台阶 `stairs` | 总长 0.50、宽 0.30、每级高 0.02，共 4 级 |
| 减速带 `bump` | 长 0.20、宽 0.018、高 0.016 |
| 箱体 `box` | 长 0.20、宽 0.20、高 0.10 |
| 圆柱 `cylinder` | 半径 0.08、高 0.15 |

斜坡沿局部 **+X** 方向升高，使用闭合三棱柱网格；台阶由实体箱体组成。平地、斜坡、台阶和减速带保持静态，箱体与圆柱可以设为动态对象。

## 编辑与导出流程

1. 打开预设或已有 `scene.json`，从左侧组件库拖入对象。
2. 在画布上移动对象，在右侧修改尺寸、位置和朝向，点击“应用对象参数”。
3. 保存工程；需要仿真时点击“导出并预览”。
4. Ubuntu 启动独立 Gazebo 窗口；Windows 显示导出位置及 Ubuntu 启动命令。

| 操作 | 方法 |
| --- | --- |
| 添加组件 | 从组件库拖入画布，或双击组件在原点添加 |
| 平移与缩放视图 | 拖动画布空白处、滚动鼠标滚轮 |
| 旋转对象 | 使用 ±15° 按钮，或修改 `yaw` 弧度值 |
| 复制 / 删除 | `Ctrl+D` / `Delete` |
| 撤销 / 重做 | `Ctrl+Z` / `Ctrl+Shift+Z` |
| 保存 / 另存为 | `Ctrl+S` / `Ctrl+Shift+S` |
| 新建 / 打开 | `Ctrl+N` / `Ctrl+O` |

工程统一使用**米和弧度**。俯视图中 +X 向右、+Y 向上，世界 +Z 向上。箱体、圆柱和减速带的位姿位于几何中心；斜坡、台阶以底面为基准。修改高度后应检查 Z，避免物体悬空或穿入地面。调整场地尺寸会改变基础地面，不会自动缩放围栏和其他对象。

每次导出新建一个时间戳目录，不覆盖已有成果：

```text
generated/output_YYYYMMDD_HHMMSS/
├── world.sdf          # Gazebo 世界
├── scene.json         # 可再次编辑的工程
├── models/            # 按需生成的网格与导入模型
├── bridge.yaml        # 可选；需包含内置小车
├── arena_gui.config   # Fortress 预览配置
└── view.sh            # Ubuntu 启动脚本
```

将**整个导出目录**复制到 Ubuntu，在该目录运行 `bash view.sh` 即可预览，无需原智能救援工作区。安装了 GazeboArena 时，可用以下命令获得启动管理与本轮日志：

```bash
# 将路径替换为实际导出目录；包含空格时保留引号
gazeboarena validate "/path/to/output_directory/world.sdf"
gazeboarena validate "/path/to/output_directory/world.sdf" --native
gazeboarena view "/path/to/output_directory/world.sdf"

# 继续编辑导出后的工程
gazeboarena edit --scene "/path/to/output_directory/scene.json"
```

`validate` 检查基础结构和本地资源；`--native` 额外调用 Fortress 的 `ign sdf -k`。无界面加载可使用 `gazeboarena view world.sdf --headless --iterations 100`；包含相机时仍需要渲染环境。

## 地形库与本地模型

仓库内的 `terrain_library/` 提供三个可编辑预设，也可以指定自己的资源目录：

```bash
gazeboarena edit --library "/path/to/my library"
```

资源库发现目录的直接子项：

| 资源 | 双击后的行为 |
| --- | --- |
| 本项目 `.json` 工程 | 打开为可编辑场景 |
| 含 `model.sdf` 或 `model.config` 的目录 | 整体导入当前场景，调整其位姿 |
| 完整 `.sdf` / `.world` | 按原文件启动 Gazebo 预览，保留当前编辑内容 |

导入模型应自包含，使用相对路径或指向自身目录的 `model://` 引用。缺失资源、目录外依赖或不能打包的引用会明确报错，不自动下载外部模型。外部模型的系统插件需在仿真主机另行安装。

保存含导入模型的工程时，会生成相邻的 `<文件名>_assets/` 目录；移动工程应同时移动资源目录。导出包中的 `scene.json` 已引用包内资源，可在其他位置重新打开。导入规范与限制见 [资源指南](docs/resources.md)。

## 机器人与外部策略接入

内置 `rescue_bot` 保留双路 640 × 480 相机、IMU、里程计、夹爪关节和三个接触传感器。每个可编辑场景最多放置一台内置小车，支持修改出生位姿。

小车是原救援仿真中的**近似模型**，采用差速驱动；轮距 0.13 m、轮半径 0.038 m。部分尺寸、质量和摩擦为仿真假设，不是实物测量结论。

| 常用话题 | 用途 |
| --- | --- |
| `/cmd_vel` | 速度控制：`linear.x` 与 `angular.z` |
| `/fork/left/cmd`、`/fork/right/cmd` | 夹爪关节控制 |
| `/camera/image`、`/camera/gripper/image` | 双相机图像 |
| `/imu`、`/odom` | 惯性与里程计数据 |
| `/fork/contact_left`、`/fork/contact_right`、`/fork/contact_front` | 接触反馈 |
| `/clock` | 仿真时钟 |

使用 `--bridge` 导出，或在界面勾选桥接选项，生成 ROS 2 Humble 配置。启动预览后，在桥接终端使用本轮输出的 **同一个 `IGN_PARTITION`**：

```bash
export IGN_PARTITION=gazeboarena-实际分区值
source /opt/ros/humble/setup.bash
ros2 run ros_gz_bridge parameter_bridge --ros-args -p config_file:=/absolute/path/bridge.yaml
```

原生 Gazebo Transport 也可接入。完整话题类型、夹爪范围和控制命令见 [外部策略接入指南](docs/policy-integration.md)。

## Python API

命令行与编辑器共用场景和导出逻辑，可直接用 Python 构造环境：

```python
from gazeboarena import export_scene, make_preset, save_scene

scene = make_preset("blank")
ramp = scene.add("ramp", x=0.4, y=0.0)
ramp.params.update(length=0.6, width=0.4, height=0.1)
ramp.pose[5] = 0.5  # yaw，单位为弧度
scene.add("robot", x=-0.8, y=0.0)

save_scene(scene, "generated/my_scene.json")
directory = export_scene(scene, "generated", bridge=True)
print(directory / "world.sdf")
```

## 开发与验证

```bash
python -m pip install -e '.[gui,dev]'
python -m pytest -q
python -m build
```

| 模块 | 职责 |
| --- | --- |
| `scene.py` / `presets.py` | 工程数据、参数检查与内置预设 |
| `resources.py` | 本地模型检查、打包与资源库发现 |
| `exporter.py` | SDF、模型资源和桥接配置生成 |
| `editor.py` | PySide6 桌面编辑器 |
| `runtime.py` / `validation.py` | 预览启动、日志、进程清理与世界检查 |
| `cli.py` | 统一的 `gazeboarena` 命令入口 |

GitHub Actions 执行 Windows / Ubuntu 核心与无显示界面测试，以及 Fortress 场景加载检查。v0.1.0 还完成了真实 Ubuntu 桌面预览、导出迁移、传感器输出和地形接触检查，详情见 [验收记录](docs/validation.md)。参与开发请阅读 [贡献指南](CONTRIBUTING.md)。

## 当前范围与模型说明

- 首版不包含策略训练、ONNX 策略运行器、原救援任务控制器或自动评测。场景可加载、接触有效，不代表某个策略能够通过该地形。
- Gazebo 预览使用独立窗口；Windows 暂不提供远程一键启动。
- 本地模型仅编辑整体位姿；外部完整 SDF 不反向转换为可编辑工程。
- 原救援预设保留原几何与默认物理配置，其中安全区入口的薄坡面仍仅有视觉。越障测试应使用新增的实体斜坡组件。

启动管理使用独立 `IGN_PARTITION`，隔离 Qt 插件环境，记录世界目录下的 `runs/`，并仅清理自身启动的预览进程。更多运行细节见 [安装与诊断](docs/installation.md)。

## 许可与致谢

代码与获授权的自有程序化模型采用 [Apache-2.0](LICENSE)。素材来源、机器人近似与仿真假设见 [来源说明](docs/provenance.md)，第三方依赖见 [第三方许可说明](THIRD_PARTY_NOTICES.md)。

感谢 [ArenaX](https://github.com/Lain-Ego0/ArenaX) 提供的场景编辑思路。本项目未复制其代码、机器人资产或策略；原平台的官方资料、固件、YOLO 权重、凭据、历史日志和大型录像不包含在本仓库中。
