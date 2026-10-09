"""Exercise the real Ubuntu desktop editor and its own Gazebo GUI windows."""
from pathlib import Path
import json
import os
import re
import subprocess
import time
from PySide6.QtWidgets import QApplication

from gazeboarena import make_preset,export_scene
from gazeboarena.editor import MainWindow
from verify_fortress import ready


app=QApplication([])
window=MainWindow(make_preset("rescue"))
window.show()
root=Path('generated/desktop-verification');root.mkdir(parents=True,exist_ok=True)
images=Path('docs/images');images.mkdir(parents=True,exist_ok=True)
report={"display":os.environ.get("DISPLAY"),"previews":[]}


def own_gui_window(session):
    pids=set(session._owned_pids())
    tree=subprocess.check_output(['xwininfo','-root','-tree'],text=True)
    for line in tree.splitlines():
        match=re.search(r'(0x[0-9a-f]+) "(Gazebo|Ignition)[^"]*"',line,re.I)
        if match:
            prop=subprocess.check_output(['xprop','-id',match.group(1),'_NET_WM_PID'],text=True)
            pid=re.search(r'=\s*(\d+)',prop)
            if pid and int(pid.group(1)) in pids:return int(match.group(1),16)
    return None


try:
    for preset in ('rescue','obstacles'):
        scene=make_preset(preset)
        window.apply_scene(scene);window.fit_canvas();app.processEvents()
        if preset=='rescue': window.grab().save(str(images/'editor-ubuntu.png'))
        path=export_scene(scene,root/preset)
        window.start_preview(path/'world.sdf')
        session=window.session
        assert session is not None
        ready(session,scene.name)
        deadline=time.monotonic()+35
        xid=None
        while time.monotonic()<deadline:
            app.processEvents()
            if session.poll() is not None: raise RuntimeError(session.log_tail())
            xid=own_gui_window(session)
            if xid:
                # Allow first render frames; observe the owned window only.
                end=time.monotonic()+4
                while time.monotonic()<end: app.processEvents();time.sleep(.1)
                break
            time.sleep(.2)
        if not xid:raise RuntimeError('Owned Gazebo GUI window not found')
        image=app.primaryScreen().grabWindow(xid)
        if image.isNull():raise RuntimeError('Gazebo window screenshot is empty')
        image.save(str(images/f'gazebo-{preset}.png'))
        report['previews'].append({'preset':preset,'gui':'passed','partition':session.partition,'window_size':[image.width(),image.height()]})
        window.stop_preview()
        assert session.poll() is not None
        print(f'Real GUI {preset}: start/render/stop passed',flush=True)
    window.undo_stack.setClean()
    window.close();app.processEvents()
    report['passed']=True
    (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
finally:
    window.stop_preview()
    window.undo_stack.setClean();window.close()
