"""Local Torch DLL initialization; no credentials, model, solver or network."""
import ctypes,os
from pathlib import Path
LIB=Path('C:/Users/HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin')
DLL_DIRECTORY=os.add_dll_directory(str(LIB))
DLL=ctypes.WinDLL(str(LIB/'msvcp140.dll'))
