# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
project = Path(SPECPATH).parent

datas = []
binaries = []
hiddenimports = []
datas.append((str(project / 'assets' / 'Anima_00333_.ico'), 'assets'))
datas.append((str(project / 'docs' / 'licensing'), 'licenses'))
datas.append((str(project / 'THIRD_PARTY_NOTICES.md'), 'licenses'))
datas.append((str(project / 'LICENSE'), 'licenses'))


a = Analysis(
    [str(project / 'src' / 'app.py')],
    pathex=[str(project / 'src')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pillow_heif'],
    noarchive=False,
    optimize=0,
)
# Qt uses the Windows ICU API. Do not bundle similarly named third-party ICU
# libraries discovered on PATH (for example Poppler's incompatible build).
a.binaries = [entry for entry in a.binaries if entry[0].lower() not in ('icuuc.dll', 'icudt78.dll')]
# No PDF or virtual-keyboard feature is used by this application. Remove those
# optional Qt plugins and their otherwise unused runtime dependencies.
a.binaries = [entry for entry in a.binaries if not any(part in entry[0].lower()
    for part in ('qpdf.dll', 'qt6pdf.dll', 'virtualkeyboard', 'qt6qml', 'qt6quick'))]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ID-Photo-4x6',
    icon=str(project / 'assets' / 'Anima_00333_.ico'),
    version=str(project / 'packaging' / 'version_info.txt'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
