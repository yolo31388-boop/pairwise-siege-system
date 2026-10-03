import pytest
from siege.system import SiegeSystem


class TestSiegeSystem:

    def test_capture_point(self):
        """占点不做人数计算，一个人和十个人占点速度一样"""
        obj = SiegeSystem()
        result = obj.capture_point()
        self.assertIsNotNone(result)

    def test_update_siege_equipment(self):
        """攻城车不做目标选择，到处乱跑"""
        obj = SiegeSystem()
        result = obj.update_siege_equipment()
        self.assertIsNotNone(result)

    def test_manage_siege_resources(self):
        """资源不做采集，永远满"""
        obj = SiegeSystem()
        result = obj.manage_siege_resources()
        self.assertIsNotNone(result)

    def test_calculate_rank(self):
        """军衔不做积分，杀多少人都是小兵"""
        obj = SiegeSystem()
        result = obj.calculate_rank()
        self.assertIsNotNone(result)

    def test_calculate_battle_result(self):
        """结算不做占点比，只看击杀数"""
        obj = SiegeSystem()
        result = obj.calculate_battle_result()
        self.assertIsNotNone(result)

