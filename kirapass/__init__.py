"""KiraPass - authorized captive-portal / hotspot security testing tool.

Public API (small on purpose):

    from kirapass import engine, store
    cal = engine.calibrate(profile, known_card="0201242548")
    eng = engine.Engine(store.Store())
    eng.start(profile, attempts=500, threads=8)
"""

from .config import APP_NAME, VERSION

__all__ = ["APP_NAME", "VERSION"]
__version__ = VERSION
