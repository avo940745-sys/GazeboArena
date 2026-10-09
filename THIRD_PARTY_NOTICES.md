# Third-party notices

GazeboArena code and authorized procedural rescue assets: Apache License 2.0. See LICENSE and docs/provenance.md.

Runtime dependencies are installed separately and retain their licenses:

- PySide6 / Qt for Python: LGPLv3 / GPLv3 / commercial options. The editor uses the separately installed, unmodified Python wheels. See https://doc.qt.io/qtforpython-6/licenses.html and the installed wheel's license files. Qt libraries are not copied into this repository or its source release.
- Gazebo Fortress and SDFormat: separately installed system packages; see their respective upstream license files at https://github.com/gazebosim/gz-sim and https://github.com/gazebosim/sdformat.
- Optional ROS 2 / ros_gz: separately installed; see https://github.com/gazebosim/ros_gz.

Development dependencies such as pytest and build retain their own licenses. No ArenaX code, assets or policies are included; its workflow is acknowledged in docs/provenance.md.
