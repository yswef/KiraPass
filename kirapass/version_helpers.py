"""Small helpers that keep the package importable from any location."""  # نص توثيقي (docstring) يشرح ما يليه

from __future__ import annotations  # استيراد annotations من الوحدة __future__

import os  # استيراد الوحدة os من المكتبة


def package_dir(*parts: str) -> str:  # تعريف الدالة package_dir(*parts) ترجع str
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)  # إرجاع os.path.join(os.path.dirname(os.path.abspath(__file__)), تفكيك قائمة)
