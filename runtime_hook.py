import os
import sys

if sys.platform == "win32":
    # Ensure extension modules can resolve the conda Qt DLLs in onedir mode.
    _internal = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    try:
        _dll_directory_handle = os.add_dll_directory(_internal)
    except (AttributeError, OSError):
        pass
    os.environ["PATH"] = _internal + os.pathsep + os.environ.get("PATH", "")
    if '--mark-worker' in sys.argv or '--vision-self-test' in sys.argv:
        # PyInstaller's Qt hook imports QtCore before main.py. Qt's older
        # bundled MSVC runtime prevents ONNX 1.23 from initializing afterward.
        # Load ONNX first only in isolated inference workers.
        import onnxruntime
