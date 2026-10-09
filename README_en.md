# GazeboArena

[简体中文](README.md) · [Installation](docs/installation.md) · [Resources](docs/resources.md)

**A Gazebo terrain and scene tool for robot policy validation.** Build arenas in a desktop editor, export portable SDF bundles, and run your own controller in Gazebo Fortress.

![GazeboArena editor](docs/images/editor.png)

- Top-down desktop editor with drag-and-drop, object properties, copy/delete, zoom, snapping and undo/redo. The initial UI is Simplified Chinese.
- Rescue, blank and basic obstacle presets; flat surfaces, solid ramps, stairs, bumps, boxes and cylinders.
- Authorized rescue robot approximation with two cameras, IMU, odometry, fork joints and contact sensors.
- Local model-folder import and complete external SDF preview; no reverse conversion of arbitrary worlds.
- Versioned editable JSON projects and portable SDF/resource export bundles.
- Isolated Fortress preview processes, session logs and optional ROS 2 Humble bridge generation.

![Gazebo Fortress obstacle preview](docs/images/gazebo-obstacles.png)

## Quick start

The core requires Python 3.10+. The pinned PySide6 editor supports Python 3.10–3.13; Python 3.10 is recommended. Windows supports editing/export; simulation targets Ubuntu 22.04 and Gazebo Fortress. The installers select Python 3.10 when `uv` is available.

```bash
git clone https://github.com/avo940745-sys/GazeboArena.git
cd GazeboArena
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e '.[gui]'
gazeboarena edit
gazeboarena export --preset rescue --bridge --output generated
gazeboarena edit --preset obstacles
gazeboarena validate /path/to/world.sdf
gazeboarena validate /path/to/world.sdf --native  # Fortress only
gazeboarena view /path/to/world.sdf               # Ubuntu only
```

Each export creates a new directory containing `world.sdf`, `scene.json`, resource folders, `view.sh`, and optionally `bridge.yaml`. Copy the **whole bundle** to Ubuntu and run `bash view.sh`, or install GazeboArena and run `gazeboarena view world.sdf` for managed preview and logs.

The initial release does not train policies or include rescue task logic, YOLO weights, automatic scoring, or remote Windows-to-Ubuntu launch. Connect your controller over Gazebo Transport or ROS 2. One built-in rescue robot is allowed per editable scene.

The rescue model is a geometric approximation, not an exported original CAD assembly. Its default collisions and simulation parameters are preserved. Legacy rescue entrance decorations remain visual-only; the new ramp component is a closed solid mesh with matching visual and collision geometry. Valid scene loading does not prove controller success on a terrain.

## Development and license

```bash
python -m pip install -e '.[gui,dev]'
python -m pytest -q
python -m build
```

Apache-2.0 for project code and authorized procedural assets. See [provenance](docs/provenance.md) and [third-party notices](THIRD_PARTY_NOTICES.md). [ArenaX](https://github.com/Lain-Ego0/ArenaX) inspired the workflow; its code, assets and policies are not included.
