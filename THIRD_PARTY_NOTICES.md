# 第三方元件、授權與重建

本專案自有 Python 原始碼、文件與 LamyFlu 提供的 AI 生成圖示採 MIT 授權（見 LICENSE）。外部元件保留各自授權，MIT 不覆蓋它們。

## 標準 1.0 版

| 元件 | 版本 | 授權與原始碼 |
|---|---|---|
| PySide6／Shiboken | 6.11.2 | LGPLv3 等選項；[Qt for Python 原始碼](https://code.qt.io/cgit/pyside/pyside-setup.git/?h=6.11.2) |
| Qt 動態函式庫 | 6.11.2 | 依元件為 LGPLv3 等；[Qt 6.11.2 原始碼](https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/) |
| Pillow | 12.3.0 | MIT-CMU 與其內附函式庫授權；[原始碼](https://github.com/python-pillow/Pillow/tree/12.3.0) |
| Python | 3.12.10 | PSF 等授權；[原始碼](https://www.python.org/downloads/release/python-31210/) |
| PyInstaller bootloader | 6.22.3 | GPLv2-or-later 與打包例外；[原始碼](https://github.com/pyinstaller/pyinstaller/tree/v6.22.3) |

標準 1.0 不安裝或封裝 pillow-heif、libheif、libde265、x265。未使用的 Qt PDF 與虛擬鍵盤插件亦不封裝。

完整授權文字副本位於 docs/licensing/；Pillow 的 LICENSE 包含其隨附圖像函式庫聲明。授權文件亦內附於 EXE 解壓後的 licenses/，發布 ZIP 提供直接可讀的副本。Qt 的官方說明見 [Qt 授權](https://doc.qt.io/qt-6/licensing.html)與 [LGPL 要求](https://www.qt.io/development/open-source-lgpl-obligations)。

## 替換或修改 Qt／PySide6

本程式以 Qt／PySide6 動態函式庫執行，不限制為除錯第三方修改而進行的逆向分析。單一 EXE 是 PyInstaller 封裝，不代表 Qt 靜態連結。

1. 使用本專案 v1.0 原始碼與 requirements.txt 建立 Python 3.12 開發環境。
2. 依上游對應版本原始碼建立自己的 Qt／PySide6，或在環境中安裝其相容的替代套件。須保持 Windows x64、Python 與 Qt API／ABI 相容。
3. 在開發環境以 `python src/app.py` 與 `python tests/verify.py` 驗證。
4. 執行 build.bat，將環境中的第三方函式庫重新封装至自己的 EXE。

打包規則完整公開於 packaging/ID-Photo-4x6.spec；沒有自有加密、啟動金鑰或阻止替換函式庫的限制。修改套件版本後應自行更新 requirements.txt 與第三方聲明。重新發布時須保留其適用授權與對應原始碼取得資料。

## 選用 HEIC

公開原始碼文件提供自行加入 HEIC 的步驟，但本次標準 EXE 不含 HEIC 元件。pillow-heif 1.8.0 Python 原始碼為 BSD-3-Clause；上游聲明 Windows wheel 內附元件為 GPLv2，含 libheif 1.23.4、libde265 1.1.3、x265 4.2、MinGW runtime。完整來源見[上游授權清單](https://github.com/bigcat88/pillow_heif/blob/v1.8.0/LICENSES_bundled.txt)。

本機 HEIC EXE 與獨立專案保留在 `.local/heic/`，整個目錄排除 Git。任何人自行編譯再散布 HEIC 版本時，須另行處理這些元件的授權、通知與對應原始碼要求，不能只附本專案的 MIT 授權。
