"""Public command line, keeping Qt an optional dependency."""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from .exporter import export_scene
from .presets import make_preset
from .scene import load_scene
from .validation import validate_world


def parser():
    p = argparse.ArgumentParser(prog="gazeboarena", description="GazeboArena 场景与地形工具")
    p.add_argument("--version", action="version", version="GazeboArena 0.1.0")
    sub = p.add_subparsers(dest="command", required=True)
    for command in ("edit", "export"):
        s = sub.add_parser(command)
        group = s.add_mutually_exclusive_group()
        group.add_argument("--scene", type=Path)
        group.add_argument("--preset", choices=("rescue", "blank", "obstacles"), default="rescue")
        s.add_argument("--output", type=Path, default=Path("generated"))
        if command == "export": s.add_argument("--bridge", action="store_true")
        else: s.add_argument("--library", type=Path)
    s = sub.add_parser("validate")
    s.add_argument("world", type=Path)
    s.add_argument("--native", action="store_true")
    s = sub.add_parser("view")
    s.add_argument("world", type=Path)
    s.add_argument("--headless", action="store_true")
    s.add_argument("--iterations", type=int)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command in ("edit", "export"):
            scene = load_scene(args.scene) if args.scene else make_preset(args.preset)
            if args.command == "export":
                print(export_scene(scene, args.output, args.bridge))
                return 0
            from .editor import run_editor
            return run_editor(scene, args.output, args.scene, args.library)
        if args.command == "validate":
            print(json.dumps(validate_world(args.world, args.native), ensure_ascii=False, indent=2))
            return 0
        if args.iterations is not None and args.iterations <= 0:
            raise ValueError("iterations 必须大于 0")
        from .runtime import GazeboSession
        session = GazeboSession(args.world, args.headless, args.iterations).start()
        print("IGN_PARTITION=" + session.partition, flush=True)
        print("logs=" + str(session.directory), flush=True)
        try:
            return session.wait()
        except KeyboardInterrupt:
            session.stop()
            return 130
    except ImportError as error:
        print(f"缺少依赖: {error}. 图形界面请安装 pip install 'gazeboarena[gui]'", file=sys.stderr)
        return 2
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError) as error:
        print(f"错误: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
