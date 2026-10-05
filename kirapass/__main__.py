"""Allow `python -m kirapass ...` as an alternative to `python KiraPass.py`."""  # نص توثيقي (docstring) يشرح ما يليه

from .cli import main  # استيراد main من الوحدة cli

if __name__ == "__main__":  # شرط: __name__ يساوي '__main__'
    raise SystemExit(main())  # رفع SystemExit(main())
