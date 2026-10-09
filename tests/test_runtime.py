from pathlib import Path
import os
import platform
import shutil
import subprocess
import sys

import pytest
from gazeboarena import make_preset,export_scene
from gazeboarena.cli import main
from gazeboarena.runtime import gazebo_environment,GazeboSession


def test_runtime_isolates_partition_and_qt(monkeypatch,tmp_path):
    monkeypatch.setenv("IGN_PARTITION","original-rescue")
    monkeypatch.setenv("QT_PLUGIN_PATH","private-qt")
    path=export_scene(make_preset("blank"),tmp_path)/"world.sdf"
    a,b=gazebo_environment(path),gazebo_environment(path)
    assert a["IGN_PARTITION"]!=b["IGN_PARTITION"]
    assert a["IGN_PARTITION"]!="original-rescue"
    assert "QT_PLUGIN_PATH" not in a
    assert os.environ["QT_PLUGIN_PATH"]=="private-qt"


def test_cli_export_and_validation(tmp_path,capsys):
    assert main(["export","--preset","blank","--output",str(tmp_path)])==0
    path=Path(capsys.readouterr().out.strip())
    assert main(["validate",str(path/"world.sdf")])==0
    assert '"native": "not_run"' in capsys.readouterr().out
    assert main(["view",str(path/"world.sdf"),"--iterations","0"])==2


def test_missing_gazebo_fails_cleanly(monkeypatch,tmp_path):
    path=export_scene(make_preset("blank"),tmp_path)/"world.sdf"
    monkeypatch.setattr(shutil,"which",lambda command: None)
    with pytest.raises(ValueError,match="Fortress"): GazeboSession(path).start()


@pytest.mark.skipif(platform.system()!="Linux",reason="POSIX process groups")
def test_session_cleanup_leaves_unrelated_process(monkeypatch,tmp_path):
    # Use a fake launcher that spawns a child; assert owned group is terminated.
    bin_dir=tmp_path/"bin"; bin_dir.mkdir()
    ign=bin_dir/"ign"
    import shlex
    child_file=tmp_path/"child.pid"
    ign.write_text('#!/bin/sh\nsetsid sleep 120 &\necho $! > '+shlex.quote(str(child_file))+'\nwait\n'); ign.chmod(0o755)
    monkeypatch.setenv("PATH",str(bin_dir)+os.pathsep+os.environ["PATH"])
    unrelated=subprocess.Popen(["sleep","120"])
    try:
        path=export_scene(make_preset("blank"),tmp_path/"exports")/"world.sdf"
        session=GazeboSession(path,True).start()
        import time
        deadline=time.monotonic()+3
        while not child_file.exists() and time.monotonic()<deadline:time.sleep(.01)
        assert child_file.exists()
        child_pid=int(child_file.read_text().strip())
        session.stop()
        assert session.poll() is not None
        assert unrelated.poll() is None
        assert session.log_file.closed
        state=Path(f"/proc/{child_pid}/stat")
        assert not state.exists() or state.read_text().rsplit(')',1)[1].strip().split()[0]=='Z'
    finally:
        unrelated.terminate(); unrelated.wait()
