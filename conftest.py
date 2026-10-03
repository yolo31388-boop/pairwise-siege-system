"""测试类未继承 unittest.TestCase 却使用其断言方法，这里在收集时统一补齐。"""
import unittest


def pytest_collection_modifyitems(items):
    patched = set()
    for item in items:
        cls = getattr(item, "cls", None)
        if cls is None or id(cls) in patched:
            continue
        patched.add(id(cls))
        if not hasattr(cls, "assertIsNotNone"):
            cls.assertIsNotNone = unittest.TestCase.assertIsNotNone
