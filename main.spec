import sys
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(['run_app.py'],
             pathex=['.'],
             binaries=None,
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None,
             excludes=None,
             cipher=block_cipher)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='whiteboard',
          debug=False,
          strip=False,
          upx=True,
          console=False,
          icon='assets/icon.ico')

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='Whiteboard')

app = BUNDLE(coll,
             name='Whiteboard.app',
             icon='assets/icon.icns',
             bundle_identifier='com.github.namuan.whiteboard',
             info_plist={
                'CFBundleName': 'Digital Whiteboard',
                'CFBundleVersion': '0.1.0',
                'CFBundleShortVersionString': '0.1.0',
                'NSPrincipalClass': 'NSApplication',
                'NSHighResolutionCapable': True,
                }
             )
