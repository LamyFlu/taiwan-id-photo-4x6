import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF, QMimeData, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtTest import QTest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from app import Window, load_photo, layout_photos, layout_mixed, make_sheet, apply_theme, save_sheet

def verify():
    with TemporaryDirectory() as tmp:
        original = Image.new('RGB', (900, 1200), '#b9d2e5')
        for ext in ['png', 'jpg', 'webp', 'avif']:
            path = Path(tmp)/('sample.'+ext)
            original.save(path)
            assert load_photo(path).size == original.size, ext
        for size, expected in [((35,45),8), ((25,25*45/35),18)]:
            positions = layout_photos(*size)
            assert len(positions) == expected, positions
            for gap, margin in [(0,0), (2,3), (10,15)]:
                positions = layout_photos(*size,gap,margin)
                for x,y,w,h,_ in positions:
                    assert x >= margin-1e-7 and y >= margin-1e-7
                    assert x+w <= 152.4-margin+1e-7 and y+h <= 101.6-margin+1e-7
                for i,a in enumerate(positions):
                    for b in positions[i+1:]:
                        assert a[0]+a[2] <= b[0]+1e-7 or b[0]+b[2] <= a[0]+1e-7 or a[1]+a[3] <= b[1]+1e-7 or b[1]+b[3] <= a[1]+1e-7
            sheet,_ = make_sheet(original,size,0,0,True)
            path = Path(tmp)/'sheet.png'; sheet.save(path,dpi=(300,300))
            with Image.open(path) as saved:
                assert saved.size == (1800,1200)
                assert abs(saved.info['dpi'][0]-300)<.01
        app = QApplication([])
        apply_theme(app)
        window = Window(); window.crop.photo = original
        assert not window.windowIcon().isNull()
        assert window.clear_button.width() == 119
        assert not hasattr(window, "gap") and not hasattr(window, "margin")
        window.zoom.setValue(50)
        assert window.crop.cropped().getpixel((0,0)) == (255,255,255)
        assert window.crop.cropped().getpixel((206,266)) == original.getpixel((450,600))
        positions = layout_mixed()
        assert len(positions) == 9
        assert all(p[2] == 25 for p in positions[:5])
        assert all(p[2] == 35 for p in positions[5:])
        for x,y,w,h,_ in positions:
            assert x >= 1.5 and y >= 1.5
            assert x+w <= 152.4-1.5 and y+h <= 101.6-1.5
        for i,a in enumerate(positions):
            for b in positions[i+1:]:
                assert a[0]+a[2]+2 <= b[0]+1e-7 or b[0]+b[2]+2 <= a[0]+1e-7 or a[1]+a[3]+2 <= b[1]+1e-7 or b[1]+b[3]+2 <= a[1]+1e-7
        window.preset.setCurrentIndex(2)
        positions = window.sheet()[1]
        assert sum(abs(min(p[2],p[3])-35)<.01 for p in positions) == 4
        assert any(abs(min(p[2],p[3])-25)<.01 for p in positions)
        window.preset.setCurrentIndex(0)
        window.refresh(); window.show(); app.processEvents()
        window.zoom.setValue(300); window.crop.cx = 0; window.crop.cy = 1
        box = window.crop.crop_box()
        assert box[0]<0 and box[3]>1200
        assert window.crop.cx == 0 and window.crop.cy == 1
        assert window.crop.cropped().getpixel((0,0)) == (255,255,255)
        window.crop.cx = -2; window.crop.cy = 3
        assert window.crop.cropped().getextrema() == ((255,255),)*3
        window.reset()
        assert window.rotation.minimum() == -300 and window.rotation.maximum() == 300
        QTest.keyClick(window.rotation, Qt.Key.Key_Right)
        assert window.crop.angle == .1
        window.rotation.setValue(300)
        assert window.crop.angle == 30
        window.rotation.setValue(-300)
        assert window.crop.angle == -30
        split = Image.new('RGB', original.size, 'red')
        split.paste('blue',(450,0,900,1200))
        window.crop.photo = split; window.reset()
        cropped = window.crop.cropped()
        point = (cropped.width//2+20,cropped.height//2-100)
        assert cropped.getpixel(point) == (0,0,255)
        window.rotation.setValue(300)
        assert window.crop.cropped().getpixel(point) == (255,0,0)
        window.crop.photo = original
        window.zoom.setValue(50)
        assert window.crop.cropped().getpixel((0,0)) == (255,255,255)
        # Dialog cancellation must preserve the photo; explicit confirmation
        # clears it. Inspect custom buttons without blocking automated checks.
        with patch('app.QMessageBox.exec'), patch('app.QMessageBox.clickedButton', return_value=None):
            window.clear_photo()
        assert window.crop.photo is original
        def clicked_clear(dialog):
            return next(b for b in dialog.buttons() if b.text() == '確認清除')
        with patch('app.QMessageBox.exec'), patch('app.QMessageBox.clickedButton', clicked_clear):
            window.clear_photo()
        assert window.crop.photo is None and not window.export_button.isEnabled()
        assert window.crop.angle == 0 and window.crop.zoom == 1
        choices = []
        window.crop.choose_photo = lambda: choices.append(True)
        QTest.mouseClick(window.crop, Qt.MouseButton.LeftButton)
        assert choices == [True]
        data = QMimeData(); data.setUrls([QUrl.fromLocalFile(str(Path(tmp)/'sample.png'))])
        event = QDropEvent(QPointF(10,10),Qt.DropAction.CopyAction,data,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        window.crop.dropEvent(event)
        assert window.crop.photo.size == original.size and event.isAccepted()
        for index,prefix in [(0,'4x6-2吋_'),(1,'4x6-1吋_'),(2,'4x6-混合_')]:
            window.preset.setCurrentIndex(index)
            assert Path(window.default_export_path()).name == prefix+'sample.png'
        window.reset()
        window.preset.setCurrentIndex(1); assert len(window.sheet()[1])==len(layout_photos(25,25*45/35,2,1.5))
        window.preset.setCurrentIndex(2)
        sheet,positions = window.sheet()
        x,y,w,h,_ = positions[0]
        px,py = round(x*300/25.4),round(y*300/25.4)
        assert sheet.getpixel((px,py)) == (147,197,253)
        assert sheet.getpixel((px+12,py)) == original.getpixel((0,0))
        path = Path(tmp)/'export.png'; save_sheet(sheet,path)
        with Image.open(path) as saved:
            assert saved.mode == 'RGB' and saved.size == (1800,1200)
            assert abs(saved.info['dpi'][0]-300)<.01
        window.grab().save(str(Path(__file__).resolve().parents[1]/'docs'/'preview.png'))
        window.close()
    print('PASS: formats, unlimited pan, white padding, rotation 0.1/30 degrees, click/drop/clear, dashed frames, PNG DPI, layouts')

if __name__ == '__main__': verify()
