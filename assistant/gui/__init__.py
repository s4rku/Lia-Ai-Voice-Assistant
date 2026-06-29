try:
    from .app import run_gui
    from .window import LiaWindow
    from .orb import OrbWidget
    __all__ = ["run_gui", "LiaWindow", "OrbWidget"]
except (ImportError, OSError, SyntaxError, Exception):
    # PySide6 blocked or unavailable – expose stubs so headless mode still imports cleanly
    def run_gui(*a, **kw): pass  # type: ignore[misc]
    class LiaWindow:  # type: ignore[no-redef]
        def __init__(self, *a, **kw): pass
        def show(self): pass
    class OrbWidget:  # type: ignore[no-redef]
        def __init__(self, *a, **kw): pass
        def set_state(self, s): pass
    __all__ = ["run_gui", "LiaWindow", "OrbWidget"]
