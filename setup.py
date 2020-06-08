import sys

from cx_Freeze import setup, Executable

build_exe_options = dict(
    packages = ['pygments'],
    excludes = [],
    include_files = 'resources'
)

bdist_mac_options = dict(
    custom_info_plist = 'assets/macos/Info.plist',
    iconfile = 'assets/macos/icon.icns'
)

executables = [
    Executable(
        'main.py',
        base='Win32GUI' if sys.platform=='win32' else None,
        targetName='PyChart'
    )
]

setup(
    name='PyChart',
    version = '0.1.0',
    description = '',
    options = dict(
        build_exe = build_exe_options, 
        bdist_mac = bdist_mac_options
    ),
    executables = executables
)
