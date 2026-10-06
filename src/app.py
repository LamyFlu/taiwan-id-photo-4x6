import sys
import math
from pathlib import Path
from functools import lru_cache
from PIL import Image, ImageOps, ImageDraw
from PySide6.QtCore import Qt, QRectF, QSizeF
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QPageSize, QPageLayout, QFontDatabase, QFont, QPalette, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QComboBox, QCheckBox, QSlider, QFileDialog, QMessageBox,
    QHBoxLayout, QVBoxLayout, QGroupBox)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog

SIZES = {'兩吋／戶政 35 × 45 mm': (35, 45), '一吋／同戶政比例 25 × 32.14 mm': (25, 25*45/35), '混合：上排一吋 5 張／下排兩吋 4 張': (35,45)}
DPI = 300
VERSION = '1.0'
GAP_MM = 2
MARGIN_MM = 1.5

def qimage(im):
    im = im.convert('RGB')
    return QImage(im.tobytes(), im.width, im.height, im.width * 3, QImage.Format.Format_RGB888).copy()

def load_photo(path):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ('RGBA', 'LA') or 'transparency' in im.info:
            rgba = im.convert('RGBA')
            bg = Image.new('RGBA', im.size, 'white')
            im = Image.alpha_composite(bg, rgba)
        return im.convert('RGB')

def layout_photos(w, h, gap=0, margin=0):
    # Row packing with both orientations; optimize over 0.01 mm units.
    pw, ph = 152.4 - 2 * margin, 101.6 - 2 * margin
    options = []
    for tw, th, rotate in [(w, h, False), (h, w, True)]:
        n = math.floor((pw + gap + 1e-8) / (tw + gap))
        if n:
            options.append((n, tw, th, rotate))
    @lru_cache(None)
    def solve(remaining):
        best = (0, [])
        for row in options:
            cost = round((row[2] + gap) * 100)
            if cost <= remaining:
                count, rows = solve(remaining - cost)
                if count + row[0] > best[0]:
                    best = count + row[0], [row] + rows
        return best
    _, rows = solve(round((ph + gap) * 100))
    used_h = sum(r[2] for r in rows) + max(0, len(rows)-1) * gap
    y = margin + (ph - used_h)/2
    positions = []
    for n, tw, th, rotate in rows:
        x = margin + (pw - (n*tw + (n-1)*gap))/2
        for i in range(n):
            positions.append((x+i*(tw+gap), y, tw, th, rotate))
        y += th + gap
    return positions

def layout_mixed():
    small_h = 25*45/35
    y = (101.6-(small_h+GAP_MM+45))/2
    positions = []
    for n,w,h in [(5,25,small_h),(4,35,45)]:
        x = (152.4-(n*w+(n-1)*GAP_MM))/2
        for i in range(n):
            positions.append((x+i*(w+GAP_MM),y,w,h,False))
        y += h+GAP_MM
    return positions

def dashed_frame(draw, box):
    left, top, right, bottom = box
    right -= 1; bottom -= 1
    color = '#93c5fd'
    for x in range(left, right+1, 16):
        draw.line((x,top,min(x+9,right),top), fill=color, width=2)
        draw.line((x,bottom,min(x+9,right),bottom), fill=color, width=2)
    for y in range(top, bottom+1, 16):
        draw.line((left,y,left,min(y+9,bottom)), fill=color, width=2)
        draw.line((right,y,right,min(y+9,bottom)), fill=color, width=2)

def save_sheet(sheet, path):
    sheet.save(path, format='PNG', dpi=(DPI,DPI))

def make_sheet(photo, size, gap, margin, marks=True, positions=None):
    scale = DPI / 25.4
    sheet = Image.new('RGB', (1800, 1200), 'white')
    draw = ImageDraw.Draw(sheet)
    if positions is None: positions = layout_photos(*size, gap, margin)
    for x, y, w, h, rotate in positions:
        tile = photo.transpose(Image.Transpose.ROTATE_90) if rotate else photo
        box = tuple(round(v*scale) for v in (x, y, x+w, y+h))
        sheet.paste(tile.resize((box[2]-box[0], box[3]-box[1]), Image.Resampling.LANCZOS), box[:2])
        if marks:
            dashed_frame(draw, box)
    return sheet, positions

class CropCanvas(QWidget):
    def __init__(self, changed, choose_photo, import_photo):
        super().__init__()
        font_path = Path('C:/Windows/Fonts/msjh.ttc')
        if font_path.exists():
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families: QApplication.instance().setFont(QFont(families[0], 10))
        self.changed = changed
        self.choose_photo = choose_photo
        self.import_photo = import_photo
        self.setAcceptDrops(True)
        self.photo = None
        self.size_mm = (35, 45)
        self.zoom = 1.0
        self.angle = 0.0
        self.cx = self.cy = .5
        self.guides = True
        self.drag = None
        self.setMinimumSize(320, 390)
    def frame(self):
        w, h = self.size_mm
        scale = min((self.width()-50)/w, (self.height()-50)/h)
        return QRectF((self.width()-w*scale)/2, (self.height()-h*scale)/2, w*scale, h*scale)
    def crop_box(self):
        w, h = self.photo.size
        aspect = self.size_mm[0]/self.size_mm[1]
        cw = min(w, h*aspect)/self.zoom
        ch = cw/aspect
        cx, cy = self.cx*w, self.cy*h
        return (cx-cw/2, cy-ch/2, cx+cw/2, cy+ch/2)
    def cropped(self):
        w, h = self.size_mm
        ow, oh = round(w*DPI/25.4), round(h*DPI/25.4)
        box = self.crop_box()
        cw, ch = box[2]-box[0], box[3]-box[1]
        cx, cy = self.cx*self.photo.width, self.cy*self.photo.height
        theta = math.radians(self.angle)
        c, s = math.cos(theta), math.sin(theta)
        # One inverse affine transform: rotate, scale and translate without
        # repeated resampling. Outside the source is always pure white.
        matrix = (c*cw/ow, s*ch/oh, cx-c*cw/2-s*ch/2,
                  -s*cw/ow, c*ch/oh, cy+s*cw/2-c*ch/2)
        return self.photo.transform((ow,oh), Image.Transform.AFFINE,
            matrix, Image.Resampling.BICUBIC, fillcolor='white')
    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor('#172236'))
        rect = self.frame()
        if self.photo:
            p.drawImage(rect, qimage(self.cropped()))
        else:
            p.setPen(QColor('#aebdd4'))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, '點選此區選擇照片\n或將照片檔案拖曳到這裡')
        p.setPen(QPen(QColor('#60d5fa'), 2))
        p.drawRect(rect)
        if self.guides and self.photo:
            p.setPen(QPen(QColor('#60d5fa'), 1, Qt.PenStyle.DashLine))
            p.drawLine(rect.center().x(), rect.top(), rect.center().x(), rect.bottom())
            # Top at 8%, chin at top + 32/45 and 36/45 for the official preset.
            ratios = [.08, .08+32/45, .08+36/45]
            for ratio in ratios:
                y = rect.top()+ratio*rect.height()
                p.drawLine(rect.left(), y, rect.right(), y)
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton: return
        if self.photo:
            self.drag = event.position()
        else:
            self.choose_photo()
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()
    def dropEvent(self, event):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.import_photo(url.toLocalFile())
                event.acceptProposedAction()
                break
    def mouseMoveEvent(self, event):
        if self.drag is not None:
            delta = event.position()-self.drag
            box = self.crop_box()
            dx = delta.x()/self.frame().width()*(box[2]-box[0])
            dy = delta.y()/self.frame().height()*(box[3]-box[1])
            c, s = math.cos(math.radians(self.angle)), math.sin(math.radians(self.angle))
            self.cx -= (c*dx+s*dy)/self.photo.width
            self.cy -= (-s*dx+c*dy)/self.photo.height
            self.drag = event.position()
            self.update()
            self.changed()
    def mouseReleaseEvent(self, event):
        self.drag = None

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'證件照排版 v{VERSION} · 4×6 相紙')
        resource_root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
        icon = QIcon(str(resource_root/'assets'/'Anima_00333_.ico'))
        self.setWindowIcon(icon)
        QApplication.instance().setWindowIcon(icon)
        self.source_path = None
        self.resize(1100, 780)
        root = QWidget(); self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        title = QLabel('證件照排版  /  4 × 6'); title.setObjectName('title'); outer.addWidget(title)
        tools = QHBoxLayout(); outer.addLayout(tools)
        self.preset = QComboBox(); self.preset.addItems(SIZES); self.preset.setMinimumWidth(340); tools.addWidget(self.preset)
        self.reset_button = self.add_button(tools, '重設裁切', self.reset)
        self.reset_button.setFixedWidth(356)
        tools.addStretch(1)
        self.clear_button = self.add_button(tools, '清除', self.clear_photo)
        self.clear_button.setFixedWidth(119)
        body = QHBoxLayout(); outer.addLayout(body, 1)
        left = QGroupBox('1  調整裁切'); ll = QVBoxLayout(left)
        self.crop = CropCanvas(self.refresh, self.open_photo, self.import_photo); ll.addWidget(self.crop, 1)
        self.zoom = QSlider(Qt.Orientation.Horizontal); self.zoom.setRange(25, 500); self.zoom.setValue(100)
        self.zoom_label = QLabel('縮小／放大  0.25× → 5×  ｜目前 1.00×')
        ll.addWidget(self.zoom_label); ll.addWidget(self.zoom)
        self.rotation_label = QLabel('旋轉  0.0°  ｜方向鍵每次微調 0.1°')
        ll.addWidget(self.rotation_label)
        self.rotation = QSlider(Qt.Orientation.Horizontal)
        self.rotation.setRange(-300,300); self.rotation.setSingleStep(1); self.rotation.setPageStep(10)
        self.rotation.setValue(0); ll.addWidget(self.rotation)
        self.guides = QCheckBox('顯示中心、頭頂及下顎輔助線'); self.guides.setChecked(True); ll.addWidget(self.guides)
        ll.addWidget(QLabel('拖曳照片移動人物。頭頂對齊上線，\n下顎置於下方兩線之間；一吋沿用相同比例。'))
        body.addWidget(left, 1)
        right = QGroupBox('2  相紙排版預覽'); rl = QVBoxLayout(right)
        self.preview = QLabel('匯入照片後自動排滿'); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter); rl.addWidget(self.preview, 1)
        rl.addWidget(QLabel('固定間距 2 mm ／留邊 1.5 mm'))
        rl.addWidget(QLabel('PNG 輸出附淺藍色虛線裁切框。'))
        self.status = QLabel(); self.status.setWordWrap(True); rl.addWidget(self.status)
        actions = QHBoxLayout(); rl.addLayout(actions)
        self.export_button = self.add_button(actions, '匯出 PNG', self.export)
        self.print_button = self.add_button(actions, '列印…', self.print_sheet)
        body.addWidget(right, 1)
        note = QLabel('兩吋 35×45 mm；一吋等比例縮小，皆為 7:9，頭部輔助線同步縮放。\n4×6 相紙為 152.4×101.6 mm，輸出 1800×1200 px / 300 DPI；列印請使用 4×6 相紙及原尺寸。')
        note.setWordWrap(True); outer.addWidget(note)
        self.preset.currentTextChanged.connect(self.change_size)
        self.zoom.valueChanged.connect(self.change_zoom)
        self.rotation.valueChanged.connect(self.change_rotation)
        self.guides.toggled.connect(self.toggle_guides)
        self.refresh()
    def add_button(self, layout, text, callback):
        b = QPushButton(text); b.clicked.connect(callback); layout.addWidget(b); return b
    def open_photo(self):
        path, _ = QFileDialog.getOpenFileName(self, '選擇照片', '', '照片 (*.jpg *.jpeg *.png *.avif *.webp *.bmp *.tif *.tiff);;所有檔案 (*)')
        if path:
            self.import_photo(path)
    def import_photo(self, path):
        try:
            photo = load_photo(path)
            self.source_path = Path(path)
            self.crop.photo = photo; self.reset()
        except Exception as e: QMessageBox.warning(self, '無法開啟照片', str(e))
    def clear_photo(self):
        if self.crop.photo is not None:
            confirm = QMessageBox(self)
            confirm.setWindowTitle('確認清除')
            confirm.setText('確定要清除目前照片與裁切設定嗎？')
            confirm.setIcon(QMessageBox.Icon.Question)
            remove = confirm.addButton('確認清除', QMessageBox.ButtonRole.DestructiveRole)
            cancel = confirm.addButton('取消', QMessageBox.ButtonRole.RejectRole)
            confirm.setDefaultButton(cancel)
            confirm.setEscapeButton(cancel)
            confirm.exec()
            if confirm.clickedButton() != remove: return
        self._clear_photo()
    def _clear_photo(self):
        self.source_path = None
        self.crop.photo = None; self.crop.drag = None; self.reset()
        self.preview.clear(); self.preview.setText('點選左側空格或拖入照片開始')
        self.status.clear()
    def reset(self):
        self.crop.cx = self.crop.cy = .5
        self.zoom.blockSignals(True); self.rotation.blockSignals(True)
        self.zoom.setValue(100); self.rotation.setValue(0)
        self.zoom.blockSignals(False); self.rotation.blockSignals(False)
        self.crop.zoom = 1; self.crop.angle = 0
        self.zoom_label.setText('縮小／放大  0.25× → 5×  ｜目前 1.00×')
        self.rotation_label.setText('旋轉  0.0°  ｜方向鍵每次微調 0.1°')
        self.refresh()
    def change_size(self): self.crop.size_mm = SIZES[self.preset.currentText()]; self.refresh()
    def change_zoom(self, value):
        self.crop.zoom = value/100
        self.zoom_label.setText(f'縮小／放大  0.25× → 5×  ｜目前 {value/100:.2f}×')
        self.refresh()
    def toggle_guides(self, value): self.crop.guides = value; self.crop.update()
    def change_rotation(self, value):
        self.crop.angle = value/10
        self.rotation_label.setText(f'旋轉  {value/10:.1f}°  ｜方向鍵每次微調 0.1°')
        self.refresh()
    def sheet(self):
        positions = layout_mixed() if self.preset.currentIndex() == 2 else None
        return make_sheet(self.crop.cropped(), self.crop.size_mm, GAP_MM, MARGIN_MM, True, positions)
    def refresh(self, *args):
        self.crop.update()
        ready = self.crop.photo is not None
        self.export_button.setEnabled(ready); self.print_button.setEnabled(ready)
        if ready:
            sheet, positions = self.sheet()
            self.preview.setPixmap(QPixmap.fromImage(qimage(sheet)).scaled(480, 320, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            if self.preset.currentIndex() == 2:
                self.status.setText('固定混合版面：上排一吋 5 張／下排兩吋 4 張')
            else: self.status.setText(f'共 {len(positions)} 張 · 保持實際尺寸 · 自動混合方向排列')
    def default_export_path(self):
        prefix = ('4x6-2吋_', '4x6-1吋_', '4x6-混合_')[self.preset.currentIndex()]
        source = self.source_path or Path('證件照.png')
        return str(source.with_name(prefix+source.stem+'.png'))
    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, '匯出 4×6 相紙', self.default_export_path(), 'PNG (*.png)')
        if path:
            try:
                if not path.lower().endswith('.png'): path += '.png'
                save_sheet(self.sheet()[0], path)
                QMessageBox.information(self, '完成', f'已儲存：\n{path}')
            except Exception as e: QMessageBox.warning(self, '匯出失敗', str(e))
    def print_sheet(self):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize(QSizeF(152.4,101.6), QPageSize.Unit.Millimeter, '4x6'))
        printer.setFullPage(True)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted: return
        page = printer.pageLayout().fullRect(QPageLayout.Unit.Millimeter)
        if abs(page.width()-152.4)>2 or abs(page.height()-101.6)>2:
            QMessageBox.warning(self, '請選擇 4×6 橫向相紙', '印表機回報的紙張尺寸不符。請於列印內容設定 4×6 相紙、橫向，再重新列印。'); return
        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.warning(self, '列印失敗', '無法啟動印表機。'); return
        try:
            scale = printer.resolution()/25.4
            painter.drawImage(QRectF(0,0,152.4*scale,101.6*scale), qimage(self.sheet()[0]))
        finally: painter.end()

def apply_theme(app):
    app.setStyle('Fusion')
    palette = QPalette()
    for role, color in {
        QPalette.ColorRole.Window: '#f3f6fa',
        QPalette.ColorRole.WindowText: '#1e293b',
        QPalette.ColorRole.Base: '#ffffff',
        QPalette.ColorRole.AlternateBase: '#edf2f7',
        QPalette.ColorRole.Text: '#1e293b',
        QPalette.ColorRole.Button: '#e8eff8',
        QPalette.ColorRole.ButtonText: '#1e293b',
        QPalette.ColorRole.Highlight: '#2563eb',
        QPalette.ColorRole.HighlightedText: '#ffffff',
        QPalette.ColorRole.ToolTipBase: '#ffffff',
        QPalette.ColorRole.ToolTipText: '#1e293b',
    }.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor('#64748b'))
    app.setPalette(palette)
    app.setStyleSheet('''
        QWidget {font-family: "Microsoft JhengHei UI"; font-size:14px; color:#1e293b;}
        QMainWindow {background:#f3f6fa;}
        QPushButton {background:#e8eff8; color:#1e293b; border:1px solid #94a3b8;
            border-radius:5px; padding:10px 16px;}
        QPushButton:hover {background:#dbeafe; border-color:#2563eb;}
        QPushButton:pressed {background:#bfdbfe;}
        QPushButton:disabled {background:#edf2f7; color:#64748b; border-color:#cbd5e1;}
        QComboBox, QSpinBox {background:white; color:#1e293b;
            border:1px solid #94a3b8; border-radius:4px; padding:5px;}
        QComboBox QAbstractItemView {background:white; color:#1e293b;
            selection-background-color:#2563eb; selection-color:white;}
        QGroupBox {font-weight:bold; margin-top:12px; padding-top:18px;
            border:1px solid #cbd5e1; border-radius:5px;}
        QGroupBox::title {subcontrol-origin:margin; left:8px; padding:0 5px;}
        QLabel#title {font-size:26px; font-weight:bold; padding:12px; color:#0f172a;}
        QSlider::groove:horizontal {height:6px; background:#cbd5e1; border-radius:3px;}
        QSlider::handle:horizontal {width:18px; margin:-6px 0; background:#2563eb;
            border:1px solid #1d4ed8; border-radius:8px;}
    ''')

def main():
    app = QApplication(sys.argv)
    apply_theme(app)
    window = Window()
    if '--verify' in sys.argv:
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            sample = Image.new('RGB', (600, 800), 'white')
            for ext in ('png', 'jpg', 'webp', 'avif'):
                path = Path(folder)/('test.' + ext)
                sample.save(path)
                assert load_photo(path).size == sample.size
            window.crop.photo = sample
            window.refresh()
            assert len(window.sheet()[1]) == 8
            window.zoom.setValue(50)
            assert window.crop.cropped().getpixel((0,0)) == (255,255,255)
            window.preset.setCurrentIndex(2)
            assert any(abs(min(p[2],p[3])-25)<.01 for p in window.sheet()[1])
            window.preset.setCurrentIndex(0)
            window.preset.setCurrentIndex(1)
            assert len(window.sheet()[1]) == len(layout_photos(25,25*45/35,GAP_MM,MARGIN_MM))
            window.rotation.setValue(1)
            assert window.crop.angle == .1
            window.crop.cx = -2; window.crop.cy = 3
            assert window.crop.cropped().getextrema() == ((255,255),)*3
            window._clear_photo()
            assert window.crop.photo is None and not window.export_button.isEnabled()
            window.import_photo(str(Path(folder)/'test.png'))
            window.preset.setCurrentIndex(2)
            output = Path(folder)/'export.png'
            save_sheet(window.sheet()[0], output)
            with Image.open(output) as check:
                assert check.mode == 'RGB' and check.size == (1800,1200)
        Path(sys.executable).with_name('verification.txt').write_text('PASS: formats, white padding, unlimited pan, 0.1 degree rotation, clear/reimport, mixed layout, PNG', encoding='utf-8')
        window.show()
        app.processEvents()
        window.grab().save(str(Path(sys.executable).with_name('preview.png')))
        return
    window.show(); sys.exit(app.exec())

if __name__ == '__main__': main()
