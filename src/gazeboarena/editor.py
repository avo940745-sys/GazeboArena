"""Qt desktop editor. The scene/export core never imports this module."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import math
import platform
import re

from PySide6.QtCore import Qt, QPointF, QRectF, QMimeData, QTimer
from PySide6.QtGui import (QAction, QColor, QDrag, QKeySequence, QPainter, QPen,
                          QPolygonF, QUndoCommand, QUndoStack)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGraphicsItem, QGraphicsPolygonItem, QGraphicsScene,
    QGraphicsView, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSplitter, QToolBar, QVBoxLayout, QWidget)

from .exporter import export_scene
from .presets import make_preset
from .resources import check_model_resources, discover_library
from .runtime import GazeboSession
from .scene import DEFAULTS, LABELS, Scene, SceneObject, load_scene, save_scene

SCALE = 200.
MIME = "application/x-gazeboarena-component"


class Change(QUndoCommand):
    def __init__(self, window, before, after, label):
        super().__init__(label)
        self.window, self.before, self.after = window, deepcopy(before), deepcopy(after)

    def undo(self): self.window.apply_scene(self.before)
    def redo(self): self.window.apply_scene(self.after)


class Palette(QListWidget):
    def startDrag(self, actions):
        if not self.currentItem(): return
        mime = QMimeData()
        mime.setData(MIME, self.currentItem().data(Qt.ItemDataRole.UserRole).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class ObjectItem(QGraphicsPolygonItem):
    def __init__(self, obj, editor):
        self.obj_name, self.editor = obj.name, editor
        p = obj.params
        length, width = p.get("length", .25), p.get("width", .20)
        if obj.kind == "robot": length, width = .281, .15
        if obj.kind == "core": length = width = .047*p["scale"]
        if obj.kind == "cylinder": length = width = p["radius"]*2
        if obj.kind == "cylinder":
            points = [QPointF(math.cos(i*math.pi/16)*length*SCALE/2,
                             math.sin(i*math.pi/16)*width*SCALE/2) for i in range(32)]
        elif obj.kind == "core":
            points = [QPointF(length*SCALE/2, 0), QPointF(-length*SCALE/2, -width*SCALE/2),
                      QPointF(-length*SCALE/2, width*SCALE/2)]
        else:
            points = [QPointF(x*length*SCALE/2, y*width*SCALE/2) for x,y in ((-1,-1),(1,-1),(1,1),(-1,1))]
        super().__init__(QPolygonF(points))
        rgba = [float(v) for v in obj.color.split()]
        color = QColor.fromRgbF(*rgba)
        if obj.kind == "robot": color = QColor("#263c54")
        if obj.kind == "imported": color = QColor("#af94db")
        self.setBrush(color)
        self.setPen(QPen(QColor("#457596"), 1))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setPos(obj.pose[0]*SCALE, -obj.pose[1]*SCALE)
        self.setRotation(-math.degrees(obj.pose[5]))
        self.setZValue(-10 if obj.name == "floor" else (3 if obj.kind == "robot" else 1))
        self.setToolTip(f"{obj.label or obj.name}\n{obj.name} · {obj.kind}\nx={obj.pose[0]:.3f}, y={obj.pose[1]:.3f} m")

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        x, y = self.pos().x()/SCALE, -self.pos().y()/SCALE
        if self.editor.snap.isChecked():
            x, y = round(x/.05)*.05, round(y/.05)*.05
        obj = next(o for o in self.editor.scene_data.objects if o.name == self.obj_name)
        if abs(x-obj.pose[0]) + abs(y-obj.pose[1]) > 1e-8:
            before = deepcopy(self.editor.scene_data)
            obj.pose[:2] = [x,y]
            self.editor.commit(before, "移动对象")

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        painter.setPen(QPen(QColor("#234562"), 1))
        if self.editor.object_kind(self.obj_name) in ("ramp", "stairs", "robot"):
            r = self.boundingRect()
            painter.drawLine(QPointF(-r.width()/4,0), QPointF(r.width()/4,0))
            painter.drawLine(QPointF(r.width()/4,0), QPointF(r.width()/8,-r.height()/5))
            painter.drawLine(QPointF(r.width()/4,0), QPointF(r.width()/8,r.height()/5))


class Canvas(QGraphicsView):
    def __init__(self, editor):
        self.editor = editor
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setAcceptDrops(True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#f3f8fc"))

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        painter.setPen(QPen(QColor("#dce8f2"), 0))
        grid = SCALE*.1
        for x in range(math.floor(rect.left()/grid), math.ceil(rect.right()/grid)+1):
            painter.drawLine(QPointF(x*grid, rect.top()), QPointF(x*grid, rect.bottom()))
        for y in range(math.floor(rect.top()/grid), math.ceil(rect.bottom()/grid)+1):
            painter.drawLine(QPointF(rect.left(), y*grid), QPointF(rect.right(), y*grid))
        painter.setPen(QPen(QColor("#97b7d0"), 0))
        painter.drawLine(QPointF(rect.left(),0), QPointF(rect.right(),0))
        painter.drawLine(QPointF(0,rect.top()), QPointF(0,rect.bottom()))

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15
        if .15 < self.transform().m11()*factor < 12: self.scale(factor, factor)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME): event.acceptProposedAction()
        else: super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME): event.acceptProposedAction()
        else: super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat(MIME):
            kind = bytes(event.mimeData().data(MIME)).decode()
            p = self.mapToScene(event.position().toPoint())
            self.editor.add_object(kind, p.x()/SCALE, -p.y()/SCALE)
            event.acceptProposedAction()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.editor.palette.currentItem():
            p = self.mapToScene(event.position().toPoint())
            self.editor.add_object(self.editor.palette.currentItem().data(Qt.ItemDataRole.UserRole), p.x()/SCALE, -p.y()/SCALE)
        else: super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, scene: Scene, output=Path("generated"), scene_path=None, library=None):
        super().__init__()
        self.scene_data, self.output = deepcopy(scene), Path(output)
        self.scene_path = Path(scene_path) if scene_path else None
        self.session = None
        self.selected_name = None
        self._rendering = False
        self.setMinimumSize(1120, 720)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1440,screen.width()-40),min(900,screen.height()-60))
        self.undo_stack = QUndoStack(self)
        self.undo_stack.cleanChanged.connect(self.title_changed)
        self.setStyleSheet("""
            QMainWindow, QWidget {background:#f6f9fd;color:#24415b;font-family:'Microsoft YaHei','Noto Sans CJK SC',sans-serif;font-size:13px;}
            QToolBar {background:white;border-bottom:1px solid #d5e4f1;padding:8px;spacing:7px;}
            QPushButton {background:white;border:1px solid #bfd3e6;border-radius:5px;padding:7px 10px;}
            QPushButton:hover {background:#e7f1ff;border-color:#438fe9;}
            QLineEdit,QDoubleSpinBox,QComboBox,QListWidget {background:white;border:1px solid #cfdfed;border-radius:4px;padding:4px;}
            QListWidget::item {padding:5px;} QListWidget::item:selected {background:#dcecff;color:#1463ad;}
            QGroupBox {font-weight:bold;border:1px solid #d6e3ef;border-radius:6px;margin-top:15px;padding:12px 7px;}
            QGroupBox::title {subcontrol-origin:margin;left:10px;}
            QStatusBar {background:#e8f2fc;} QSplitter::handle {background:#dfeaf4;width:3px;}
        """)
        self.create_toolbar()
        splitter = QSplitter()
        self.setCentralWidget(splitter)
        left = QWidget(); ll = QVBoxLayout(left)
        heading = QLabel("GAZEBO ARENA"); heading.setStyleSheet("font-size:23px;font-weight:700;color:#226bb0;padding:8px 0")
        ll.addWidget(heading); ll.addWidget(QLabel("地形与场景 · 机器人策略验证"))
        ll.addWidget(QLabel("组件库  · 拖入画布 / 双击添加"))
        self.palette = Palette(); self.palette.setDragEnabled(True)
        for kind in ("box", "ramp", "stairs", "bump", "cylinder", "flat", "core", "robot"):
            item = QListWidgetItem(LABELS[kind]); item.setData(Qt.ItemDataRole.UserRole, kind); self.palette.addItem(item)
        self.palette.itemDoubleClicked.connect(lambda item: self.add_object(item.data(Qt.ItemDataRole.UserRole)))
        ll.addWidget(self.palette, 2)
        ll.addWidget(QLabel("场景对象")); self.object_list = QListWidget()
        self.object_list.currentItemChanged.connect(self.list_selected)
        ll.addWidget(self.object_list, 3)
        row = QHBoxLayout()
        for text, fn in (("复制", self.duplicate), ("删除", self.delete_selected)):
            b = QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        ll.addLayout(row)
        self.library_path = QLineEdit(str(library or "terrain_library"))
        ll.addWidget(QLabel("本地地形 / 模型库")); ll.addWidget(self.library_path)
        row = QHBoxLayout()
        b = QPushButton("选择目录"); b.clicked.connect(self.choose_library); row.addWidget(b)
        b = QPushButton("刷新"); b.clicked.connect(self.refresh_library); row.addWidget(b)
        ll.addLayout(row)
        self.library_list = QListWidget(); self.library_list.itemDoubleClicked.connect(self.open_library)
        ll.addWidget(self.library_list, 2)
        splitter.addWidget(left)
        center = QWidget(); cl = QVBoxLayout(center)
        top = QHBoxLayout(); top.addWidget(QLabel("俯视布局   +X →  +Y ↑")); top.addStretch()
        self.snap = QCheckBox("吸附 5 cm"); self.snap.setChecked(True); top.addWidget(self.snap)
        b = QPushButton("适应场地"); b.clicked.connect(self.fit_canvas); top.addWidget(b)
        cl.addLayout(top)
        self.canvas = Canvas(self); self.canvas.scene().selectionChanged.connect(self.canvas_selected)
        cl.addWidget(self.canvas)
        self.summary = QLabel(); cl.addWidget(self.summary)
        cl.addWidget(QLabel("拖动对象移动 · 滚轮缩放 · 拖动空白处平移 · 双击放置组件"))
        splitter.addWidget(center)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        right = QWidget(); rl = QVBoxLayout(right)
        group = QGroupBox("场地设置"); f = QFormLayout(group)
        self.world_name = QLineEdit(); f.addRow("世界名称", self.world_name)
        self.field_length = self.spin(.1, 1000., 3); f.addRow("长度 (m)", self.field_length)
        self.field_width = self.spin(.1, 1000., 3); f.addRow("宽度 (m)", self.field_width)
        self.step = self.spin(.00001, .1, 5); f.addRow("物理步长 (s)", self.step)
        b = QPushButton("应用场地设置"); b.clicked.connect(self.apply_field); f.addRow(b)
        rl.addWidget(group)
        self.properties = QGroupBox("对象属性"); self.prop_layout = QVBoxLayout(self.properties)
        rl.addWidget(self.properties)
        export_group = QGroupBox("SDF 导出与预览"); el = QVBoxLayout(export_group)
        self.output_edit = QLineEdit(str(self.output)); el.addWidget(self.output_edit)
        b = QPushButton("选择导出目录"); b.clicked.connect(self.choose_output); el.addWidget(b)
        self.bridge = QCheckBox("生成内置小车 ROS 2 桥接配置"); el.addWidget(self.bridge)
        b = QPushButton("导出 SDF"); b.clicked.connect(lambda: self.export(False)); el.addWidget(b)
        b = QPushButton("导出并预览 →"); b.setStyleSheet("background:#2479cd;color:white;font-weight:bold")
        b.clicked.connect(lambda: self.export(True)); el.addWidget(b)
        b = QPushButton("加载外部 SDF 预览"); b.clicked.connect(self.open_world); el.addWidget(b)
        b = QPushButton("停止本轮预览"); b.clicked.connect(self.stop_preview); el.addWidget(b)
        rl.addWidget(export_group)
        note = QLabel("内置小车为近似模型。\n本工具构建测试环境，\n控制策略由使用者自行接入。"); note.setWordWrap(True)
        note.setStyleSheet("color:#68849d;padding:8px"); rl.addWidget(note); rl.addStretch()
        scroll.setWidget(right); splitter.addWidget(scroll)
        splitter.setSizes([250,850,320])
        self.timer = QTimer(self); self.timer.timeout.connect(self.check_preview); self.timer.start(500)
        self.apply_scene(self.scene_data)
        self.refresh_library()
        QTimer.singleShot(0, self.fit_canvas)

    @staticmethod
    def spin(low=-1000., high=1000., decimals=4):
        s = QDoubleSpinBox(); s.setRange(low,high); s.setDecimals(decimals)
        s.setSingleStep(.01); s.setKeyboardTracking(False); return s

    def create_toolbar(self):
        bar = QToolBar(); bar.setMovable(False); self.addToolBar(bar)
        for text, fn, shortcut in (("新建", self.new_scene, "Ctrl+N"), ("打开", self.open_scene, "Ctrl+O"),
                                    ("保存", self.save, "Ctrl+S"), ("另存为", self.save_as, "Ctrl+Shift+S")):
            a = QAction(text,self); a.triggered.connect(fn); a.setShortcut(QKeySequence(shortcut)); bar.addAction(a)
        bar.addSeparator()
        bar.addAction(self.undo_stack.createUndoAction(self,"撤销")); bar.actions()[-1].setShortcut(QKeySequence("Ctrl+Z"))
        bar.addAction(self.undo_stack.createRedoAction(self,"重做")); bar.actions()[-1].setShortcut(QKeySequence("Ctrl+Shift+Z"))
        bar.addSeparator(); bar.addWidget(QLabel(" 预设 "))
        self.preset = QComboBox()
        for text, key in (("智能救援", "rescue"), ("空白场地", "blank"), ("基础越障", "obstacles")):
            self.preset.addItem(text,key)
        bar.addWidget(self.preset)
        b = QPushButton("加载预设"); b.clicked.connect(self.new_scene); bar.addWidget(b)
        b = QPushButton("导入本地模型"); b.clicked.connect(self.import_model); bar.addWidget(b)
        for shortcut, fn in (("Delete", self.delete_selected), ("Ctrl+D", self.duplicate)):
            action = QAction(self); action.setShortcut(QKeySequence(shortcut)); action.triggered.connect(fn); self.addAction(action)

    def title_changed(self):
        self.setWindowTitle("GazeboArena · " + (self.scene_path.name if self.scene_path else "未保存场景") +
                            (" *" if not self.undo_stack.isClean() else ""))

    def object_kind(self, name):
        return next(o.kind for o in self.scene_data.objects if o.name == name)

    def commit(self, before, label):
        try:
            self.scene_data.validate()
            after = deepcopy(self.scene_data)
            self.undo_stack.push(Change(self, before, after, label))
        except (ValueError, TypeError, KeyError) as error:
            self.apply_scene(before); self.error(error)

    def apply_scene(self, scene):
        self._rendering = True
        self.scene_data = deepcopy(scene)
        self.object_list.clear(); self.canvas.scene().clear()
        for obj in self.scene_data.objects:
            item = QListWidgetItem(f"{obj.label or obj.name}  · {obj.name}")
            item.setData(Qt.ItemDataRole.UserRole, obj.name); self.object_list.addItem(item)
            graphic = ObjectItem(obj,self); self.canvas.scene().addItem(graphic)
            if obj.name == self.selected_name:
                graphic.setSelected(True); self.object_list.setCurrentItem(item)
        rect = QRectF(-scene.length*SCALE/2, -scene.width*SCALE/2, scene.length*SCALE, scene.width*SCALE)
        border = self.canvas.scene().addRect(rect, QPen(QColor("#277fc5"),2))
        border.setZValue(10)
        self.canvas.scene().setSceneRect(self.canvas.scene().itemsBoundingRect().united(rect).adjusted(-70,-70,70,70))
        self.world_name.setText(scene.name); self.field_length.setValue(scene.length)
        self.field_width.setValue(scene.width); self.step.setValue(scene.physics_step)
        self.summary.setText(f"{scene.length:g} × {scene.width:g} m   |   {len(scene.objects)} 个对象   |   Fortress · SDF 1.8")
        self._rendering = False
        self.show_properties(); self.title_changed()

    def fit_canvas(self):
        self.canvas.fitInView(self.canvas.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def selected(self): return next((o for o in self.scene_data.objects if o.name == self.selected_name), None)

    def list_selected(self, item, old):
        if self._rendering: return
        self.selected_name = item.data(Qt.ItemDataRole.UserRole) if item else None
        self._rendering = True
        for graphic in self.canvas.scene().items():
            if isinstance(graphic,ObjectItem): graphic.setSelected(graphic.obj_name == self.selected_name)
        self._rendering = False; self.show_properties()

    def canvas_selected(self):
        if self._rendering: return
        items = [i for i in self.canvas.scene().selectedItems() if isinstance(i,ObjectItem)]
        self.selected_name = items[0].obj_name if items else None
        self._rendering = True
        self.object_list.setCurrentRow(-1)
        for i in range(self.object_list.count()):
            if self.object_list.item(i).data(Qt.ItemDataRole.UserRole) == self.selected_name:
                self.object_list.setCurrentRow(i); break
        self._rendering = False; self.show_properties()

    def show_properties(self):
        while self.prop_layout.count():
            item = self.prop_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        obj = self.selected(); self.controls = {}
        if not obj:
            self.prop_layout.addWidget(QLabel("点击对象，编辑位置、尺寸与朝向。")); return
        panel = QWidget(); form = QFormLayout(panel); self.prop_layout.addWidget(panel)
        form.addRow(QLabel(f"{LABELS.get(obj.kind,obj.kind)} · {obj.name}"))
        self.label_edit = QLineEdit(obj.label); form.addRow("显示名称",self.label_edit)
        for i, label in enumerate(("X (m)", "Y (m)", "Z (m)", "Roll (rad)", "Pitch (rad)", "Yaw (rad)")):
            s = self.spin(); s.setValue(obj.pose[i]); self.controls[f"pose_{i}"] = s; form.addRow(label,s)
        for key,value in obj.params.items():
            s = self.spin(.0001,1000.,0 if key == "count" else 4)
            if key == "count": s.setRange(1,100); s.setSingleStep(1)
            s.setValue(value); self.controls[key] = s
            label = {"length":"长度 (m)","width":"宽度 (m)","height":"单级高度 (m)" if obj.kind == "stairs" else "高度 (m)",
                     "radius":"半径 (m)","count":"台阶数","scale":"缩放"}.get(key,key)
            form.addRow(label,s)
        if obj.kind not in ("robot","imported"):
            self.color_edit = QLineEdit(obj.color); form.addRow("RGBA",self.color_edit)
            self.static_edit = QCheckBox("静态"); self.static_edit.setChecked(obj.static)
            self.static_edit.setEnabled(obj.kind not in ("flat","ramp","stairs","bump")); form.addRow(self.static_edit)
            self.collision_edit = QCheckBox("实体碰撞"); self.collision_edit.setChecked(obj.collision)
            # A legacy visual-only marker should be replaced by a real component.
            self.collision_edit.setEnabled(not (obj.template and not obj.collision)); form.addRow(self.collision_edit)
            self.mass_edit = self.spin(.0001,1000.); self.mass_edit.setValue(obj.mass); form.addRow("质量 (kg)",self.mass_edit)
            self.friction_enabled = QCheckBox("覆盖摩擦系数"); self.friction_enabled.setChecked(obj.friction is not None)
            self.friction_edit = self.spin(0.,100.); self.friction_edit.setValue(obj.friction if obj.friction is not None else .35)
            form.addRow(self.friction_enabled); form.addRow("μ",self.friction_edit)
        if obj.kind == "imported":
            note = QLabel("整体模型，仅编辑位姿。\n资源: " + obj.source); note.setWordWrap(True); form.addRow(note)
        row = QHBoxLayout()
        for text, angle in (("↶ 15°", math.pi/12), ("↷ 15°", -math.pi/12)):
            b = QPushButton(text); b.clicked.connect(lambda checked=False,a=angle: self.rotate(a)); row.addWidget(b)
        form.addRow(row)
        b = QPushButton("应用对象参数"); b.clicked.connect(self.apply_properties); form.addRow(b)

    def rotate(self, angle):
        if self.selected():
            before = deepcopy(self.scene_data); self.selected().pose[5] += angle; self.commit(before,"旋转对象")

    def apply_properties(self):
        obj = self.selected()
        if not obj: return
        before = deepcopy(self.scene_data)
        obj.label = self.label_edit.text()
        obj.pose = [self.controls[f"pose_{i}"].value() for i in range(6)]
        for key in obj.params:
            value = self.controls[key].value(); obj.params[key] = int(value) if key == "count" else value
        if obj.kind not in ("robot","imported"):
            obj.color = self.color_edit.text(); obj.static = self.static_edit.isChecked()
            obj.collision = self.collision_edit.isChecked(); obj.mass = self.mass_edit.value()
            obj.friction = self.friction_edit.value() if self.friction_enabled.isChecked() else None
        self.commit(before,"修改对象参数")

    def apply_field(self):
        before = deepcopy(self.scene_data)
        self.scene_data.name = self.world_name.text().strip()
        self.scene_data.length, self.scene_data.width = self.field_length.value(), self.field_width.value()
        self.scene_data.physics_step = self.step.value()
        floor = next((o for o in self.scene_data.objects if o.name == "floor" and o.kind in ("box","flat")),None)
        if floor: floor.params.update(length=self.scene_data.length,width=self.scene_data.width)
        self.commit(before,"修改场地设置")

    def add_object(self, kind, x=0., y=0.):
        before = deepcopy(self.scene_data)
        if self.snap.isChecked(): x,y = round(x/.05)*.05, round(y/.05)*.05
        try:
            obj = self.scene_data.add(kind,x,y); self.selected_name = obj.name; self.commit(before,"添加对象")
        except ValueError as error: self.error(error)

    def duplicate(self):
        obj = self.selected()
        if not obj: return
        if obj.kind == "robot": self.error("首版仅允许一台内置救援小车"); return
        before = deepcopy(self.scene_data); clone = deepcopy(obj)
        i = 1
        while any(o.name == f"{obj.name}_copy{i}" for o in self.scene_data.objects): i += 1
        clone.name = f"{obj.name}_copy{i}"; clone.pose[0] += .1; clone.pose[1] += .1
        self.scene_data.objects.append(clone); self.selected_name = clone.name; self.commit(before,"复制对象")

    def delete_selected(self):
        obj = self.selected()
        if not obj: return
        before = deepcopy(self.scene_data)
        self.scene_data.objects.remove(obj); self.selected_name = None; self.commit(before,"删除对象")

    def confirm_discard(self):
        if self.undo_stack.isClean(): return True
        answer = QMessageBox.question(self,"未保存场景","保存当前修改？",QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Save: return self.save()
        return answer == QMessageBox.StandardButton.Discard

    def new_scene(self):
        if not self.confirm_discard(): return
        self.selected_name = None; self.scene_path = None
        self.undo_stack.clear(); self.apply_scene(make_preset(self.preset.currentData())); self.fit_canvas()

    def open_scene(self):
        path,_ = QFileDialog.getOpenFileName(self,"打开可编辑场景","","GazeboArena (*.json)")
        if path: self.load_project(Path(path))

    def load_project(self,path):
        if not self.confirm_discard(): return
        try:
            scene = load_scene(path)
            self.scene_path = path; self.selected_name = None; self.undo_stack.clear()
            self.apply_scene(scene); self.fit_canvas()
        except Exception as error: self.error(error)

    def save(self):
        if not self.scene_path: return self.save_as()
        try:
            save_scene(self.scene_data,self.scene_path); self.undo_stack.setClean(); self.title_changed()
            self.statusBar().showMessage(f"已保存: {self.scene_path}",8000); return True
        except Exception as error: self.error(error); return False

    def save_as(self):
        path,_ = QFileDialog.getSaveFileName(self,"保存场景",str(self.scene_path or "scene.json"),"GazeboArena (*.json)")
        if not path: return False
        old = self.scene_path
        self.scene_path = Path(path if path.lower().endswith(".json") else path+".json")
        if self.save(): return True
        self.scene_path = old; return False

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self,"导出目录",self.output_edit.text())
        if path: self.output_edit.setText(path)

    def export(self,preview=False):
        try:
            path = export_scene(self.scene_data, self.output_edit.text() or "generated", self.bridge.isChecked())
            self.statusBar().showMessage(f"已导出: {path}",15000)
            if preview: self.start_preview(path/"world.sdf")
            else: QMessageBox.information(self,"导出完成",f"完整场景目录:\n{path}\n\nUbuntu 中运行: bash view.sh")
            return path
        except Exception as error: self.error(error)

    def open_world(self):
        path,_ = QFileDialog.getOpenFileName(self,"外部完整 SDF 预览","","Gazebo worlds (*.sdf *.world)")
        if path: self.start_preview(Path(path))

    def start_preview(self,path):
        if platform.system() != "Linux":
            QMessageBox.information(self,"在 Ubuntu 中预览",f"场景: {path}\n\n将场景及资源复制到 Ubuntu 后运行:\ngazeboarena view world.sdf\n\n工具导出目录也可运行: bash view.sh")
            return
        try:
            self.stop_preview(); self.session = GazeboSession(path).start()
            self.statusBar().showMessage(f"预览启动中 · 日志: {self.session.directory}")
        except Exception as error: self.error(error)

    def stop_preview(self):
        if self.session:
            self.session.stop(); self.session = None
            self.statusBar().showMessage("本轮 Gazebo 预览已停止",6000)

    def check_preview(self):
        if self.session and self.session.poll() is not None:
            code = self.session.poll(); tail = self.session.log_tail(); directory = self.session.directory
            self.session.stop(); self.session = None
            if code: self.error(f"Gazebo 退出码 {code}\n日志: {directory}\n{tail}")
            else: self.statusBar().showMessage("Gazebo 预览已关闭",6000)

    def choose_library(self):
        path = QFileDialog.getExistingDirectory(self,"本地资源库目录",self.library_path.text())
        if path: self.library_path.setText(path); self.refresh_library()

    def refresh_library(self):
        self.library_list.clear()
        for kind,path in discover_library(self.library_path.text()):
            item = QListWidgetItem({"world":"SDF","scene":"场景","model":"模型"}[kind]+" · "+path.name)
            item.setData(Qt.ItemDataRole.UserRole,(kind,str(path.resolve()))); self.library_list.addItem(item)

    def open_library(self,item):
        kind,path = item.data(Qt.ItemDataRole.UserRole)
        if kind == "scene": self.load_project(Path(path))
        elif kind == "world": self.start_preview(Path(path))
        else: self.import_directory(Path(path))

    def import_model(self):
        path = QFileDialog.getExistingDirectory(self,"选择含 model.sdf / model.config 的模型目录")
        if path: self.import_directory(Path(path))

    def import_directory(self,path):
        try:
            check_model_resources(path)
            before = deepcopy(self.scene_data)
            stem = re.sub(r"[^A-Za-z0-9_]","_",path.name)
            if not stem or stem[0].isdigit(): stem = "model_"+stem
            name = stem; i = 1
            while any(o.name == name for o in self.scene_data.objects): name = f"{stem}_{i}"; i += 1
            obj = SceneObject(name,"imported",path.name,source=str(path.resolve()))
            self.scene_data.objects.append(obj); self.selected_name = name; self.commit(before,"导入本地模型")
        except Exception as error: self.error(error)

    def error(self,error): QMessageBox.warning(self,"GazeboArena",str(error))

    def closeEvent(self,event):
        if self.confirm_discard(): self.stop_preview(); event.accept()
        else: event.ignore()


def run_editor(scene,output,scene_path=None,library=None):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(scene,output,scene_path,library)
    window.show()
    return app.exec()
