# 自行編譯 HEIC／HEIF 版本

GitHub 的標準 1.0 原始碼與公開 EXE 不包含 HEIC／HEIF；AVIF、WebP 等格式仍受支援。作者另保留本機專用 HEIC 版本，該版本的 EXE、獨立原始碼與打包檔皆不在公開儲存庫內。

需要 HEIC 的使用者可自行修改與編譯，不必將照片傳到雲端。以下以 Windows x64、Python 3.12 為例。

## 1. 建立自己的專案副本與開發環境

下載本儲存庫原始碼，在專案資料夾開啟 PowerShell：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install pillow-heif==1.8.0
```

## 2. 啟用解碼與檔案選擇

在 `src/app.py` 的匯入區加入：

```python
import pillow_heif
pillow_heif.register_heif_opener()
```

在 `open_photo()` 的檔案篩選文字加入 `*.heic *.heif`。開發模式啟動：

```powershell
.venv\Scripts\python.exe src\app.py
```

## 3. 修改封裝設定

在 `packaging/ID-Photo-4x6.spec` 中：

1. 匯入 `from PyInstaller.utils.hooks import collect_all`。
2. 在 `Analysis(...)` 之前、`datas`、`binaries`、`hiddenimports` 初始化之後加入下列程式。
3. 將 `excludes=['pillow_heif']` 改成 `excludes=[]`。
4. 將 `EXE(...)` 的 `name='ID-Photo-4x6'` 改成 `name='ID-Photo-4x6-HEIC'`，以便區分產物。

```python
heif_data, heif_binaries, heif_imports = collect_all('pillow_heif')
datas += heif_data
binaries += heif_binaries
hiddenimports += heif_imports
```

打包：

```powershell
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --workpath .build --distpath release packaging\ID-Photo-4x6.spec
```

產物為 `release/ID-Photo-4x6-HEIC.exe`。選用範例 HEIC 照片，確認可點選、拖入、裁切及匯出 PNG；標準 `tests/verify.py` 檢查其餘功能，不會測 HEIC。

## 授權差異

`pillow-heif` Python 原始碼是 BSD-3-Clause，但官方 1.8.0 Windows wheel 的內附元件包含 GPL 授權的 x265。安裝套件不會改變本專案自有原始碼的 MIT 授權，然而散布帶有這些元件的封裝 EXE 時，必須另依其授權條款處理通知、對應原始碼與其他散布要求，不能只附本專案的 MIT 授權就宣稱完整。

請先閱讀安裝目錄中的 `pillow_heif-1.8.0.dist-info/licenses/LICENSES_bundled.txt`，以及[上游原始授權清單](https://github.com/bigcat88/pillow_heif/blob/v1.8.0/LICENSES_bundled.txt)。本專案不提供 HEIC 版公開下載或代為散布。
