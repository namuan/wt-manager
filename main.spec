import sys
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Collect data files for the application
datas = []

# Add any configuration templates or resources if needed
# datas += collect_data_files('wt_manager')

a = Analysis(['src/wt_manager/__main__.py'],
             pathex=['.', 'src'],
             binaries=None,
             datas=datas,
             hiddenimports=[
                 'wt_manager.controllers',
                 'wt_manager.services',
                 'wt_manager.ui',
                 'wt_manager.models',
                 'wt_manager.utils',
                 'PyQt6.QtCore',
                 'PyQt6.QtWidgets',
                 'PyQt6.QtGui',
             ],
             hookspath=None,
             runtime_hooks=None,
             excludes=[
                 'tkinter',
                 'matplotlib',
                 'numpy',
                 'scipy',
                 'pandas',
             ],
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='wt-manager',
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
               name='GitWorktreeManager')

app = BUNDLE(coll,
             name='GitWorktreeManager.app',
             icon='assets/icon.icns',
             bundle_identifier='com.github.gitworktreemanager',
             info_plist={
                'CFBundleName': 'Git Worktree Manager',
                'CFBundleDisplayName': 'Git Worktree Manager',
                'CFBundleVersion': '0.1.0',
                'CFBundleShortVersionString': '0.1.0',
                'NSPrincipalClass': 'NSApplication',
                'NSHighResolutionCapable': True,
                'LSMinimumSystemVersion': '10.14.0',
                'CFBundleDocumentTypes': [],
                'NSRequiresAquaSystemAppearance': False,
                }
             )
