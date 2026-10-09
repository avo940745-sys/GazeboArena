"""Capture only this application's widget, not the user's desktop."""
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from gazeboarena import make_preset
from gazeboarena.editor import MainWindow

app = QApplication([])
window = MainWindow(make_preset("rescue"))
window.show()

def capture():
    window.fit_canvas()
    path = Path("docs/images/editor.png")
    path.parent.mkdir(parents=True,exist_ok=True)
    window.grab().save(str(path))
    window.undo_stack.setClean()
    window.close()
    app.quit()

QTimer.singleShot(1500,capture)
app.exec()
