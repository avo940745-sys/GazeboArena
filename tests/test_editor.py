import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from copy import deepcopy
from pathlib import Path

import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from gazeboarena import make_preset
from gazeboarena.editor import MainWindow, ObjectItem, SCALE


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app,tmp_path):
    w=MainWindow(make_preset("blank"),tmp_path)
    w.error=lambda error: (_ for _ in ()).throw(AssertionError(str(error)))
    w.show(); app.processEvents()
    yield w
    w.undo_stack.setClean(); w.close(); app.processEvents()


def test_add_duplicate_delete_undo_redo(window):
    window.add_object("ramp",.4,.6)
    assert window.selected().pose[:2] == pytest.approx([.4,.6])
    window.duplicate(); assert len(window.scene_data.objects)==3
    window.delete_selected(); assert len(window.scene_data.objects)==2
    window.undo_stack.undo(); assert len(window.scene_data.objects)==3
    window.undo_stack.undo(); assert len(window.scene_data.objects)==2
    window.undo_stack.undo(); assert len(window.scene_data.objects)==1
    window.undo_stack.redo(); assert window.scene_data.objects[-1].kind=="ramp"


def test_rotation_and_coordinate_projection(window):
    window.add_object("box",.4,.6)
    window.rotate(.7)
    item=next(i for i in window.canvas.scene().items() if isinstance(i,ObjectItem) and i.obj_name==window.selected_name)
    assert item.pos()==QPointF(.4*SCALE,-.6*SCALE)
    assert item.rotation()==pytest.approx(-.7*180/3.141592653589793)
    window.undo_stack.undo(); assert window.selected().pose[5]==0


def test_properties_and_field_are_undoable(window):
    window.add_object("stairs")
    window.controls["height"].setValue(.04)
    window.controls["count"].setValue(6)
    window.apply_properties()
    assert window.selected().params["count"]==6
    window.undo_stack.undo(); assert window.selected().params["count"]==4
    window.field_length.setValue(5)
    window.apply_field(); assert window.scene_data.length==5
    assert window.scene_data.objects[0].params["length"]==5
    window.undo_stack.undo(); assert window.scene_data.length==3


def test_save_and_dirty_tracking(window,tmp_path):
    window.add_object("cylinder")
    assert not window.undo_stack.isClean()
    window.scene_path=tmp_path/"中文 场景.json"
    assert window.save()
    assert window.undo_stack.isClean()
    window.rotate(.2)
    assert not window.undo_stack.isClean()


def test_mouse_drag_commits_position_and_undo(window,app):
    window.add_object("box",0,0)
    window.fit_canvas();app.processEvents()
    start=window.canvas.mapFromScene(QPointF(0,0))
    end=window.canvas.mapFromScene(QPointF(.2*SCALE,-.1*SCALE))
    QTest.mousePress(window.canvas.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start)
    QTest.mouseMove(window.canvas.viewport(),end,50)
    QTest.mouseRelease(window.canvas.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,end)
    app.processEvents()
    assert window.selected().pose[:2] == pytest.approx([.2,.1],abs=.03)
    window.undo_stack.undo()
    assert window.selected().pose[:2] == [0,0]
