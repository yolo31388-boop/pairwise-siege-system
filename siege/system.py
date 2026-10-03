"""
pairwise-siege-system - SiegeSystem

This module contains a deliberately broken implementation.
Fix all bugs so that tests pass.
"""


class SiegeSystem:
    def __init__(self):
        self.state = {}

    def capture_point(self, *args, **kwargs):
        """BUG: 占点不做人数计算，一个人和十个人占点速度一样"""
        return None

    def update_siege_equipment(self, *args, **kwargs):
        """BUG: 攻城车不做目标选择，到处乱跑"""
        return None

    def manage_siege_resources(self, *args, **kwargs):
        """BUG: 资源不做采集，永远满"""
        return None

    def calculate_rank(self, *args, **kwargs):
        """BUG: 军衔不做积分，杀多少人都是小兵"""
        return None

    def calculate_battle_result(self, *args, **kwargs):
        """BUG: 结算不做占点比，只看击杀数"""
        return None

