# بداية نص متعدد الأسطر — الأسطر التالية نصّ حرفي لا كود، فلا يقبل تعليقاً
"""KiraPass - authorized captive-portal / hotspot security testing tool.

Public API (small on purpose):

    from kirapass import engine, store
    cal = engine.calibrate(profile, known_card="0201242548")
    eng = engine.Engine(store.Store())
    eng.start(profile, attempts=500, threads=8)
"""  # نهاية النص متعدد الأسطر

from .config import APP_NAME, VERSION  # استيراد APP_NAME, VERSION من الوحدة config

__all__ = ["APP_NAME", "VERSION"]  # إسناد قائمة إلى __all__
__version__ = VERSION  # إسناد VERSION إلى __version__
