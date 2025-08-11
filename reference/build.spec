# file: build.spec

# -*- mode: python ; coding: utf-8 -*-

# a - это объект анализа, который находит все зависимости
a = Analysis(
    ['main.py'],  # Главный файл вашего приложения
    pathex=[],
    binaries=[],
    datas=[
        # --- ВОТ КЛЮЧЕВАЯ ЧАСТЬ ---
        # Мы говорим PyInstaller: "Возьми папку 'icons' из корня проекта
        # и положи ее под таким же именем 'icons' в финальную сборку."
        ('icons', 'icons') 
    ],
    hiddenimports=[], # Сюда можно добавлять "скрытые" импорты, если будут ошибки
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    # --- ОПЦИИ ДЛЯ ОКНА ---
    # 'CONCEAL' скрывает исходный код
    # ' Maintenant' используется для работы с библиотекой matplotlib
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher_block_size=16,
    noarchive=False
)

# pyz - это архив со всеми Python-модулями
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# exe - это главный исполняемый файл
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ThermoGrid_Server', # Имя вашего .exe файла
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True, # Используем UPX для сжатия, если он установлен
    console=False, # <-- ВАЖНО: False, чтобы не было черного окна консоли
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # --- ИКОНКА ДЛЯ .EXE ФАЙЛА ---
    # Замените 'app_icon.ico' на имя вашего файла иконки
    # Иконка должна быть в формате .ico
    icon='app_icon.ico'
)

# coll - это папка со всеми зависимостями
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ThermoGrid_Server' # Имя финальной папки
)