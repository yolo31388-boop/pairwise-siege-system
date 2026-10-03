import pytest
from siege.system import SiegeSystem


class TestCapturePoint:
    def test_headcount_scales_capture_speed(self):
        solo = SiegeSystem().capture_point("p", "attackers", soldiers=1)
        squad = SiegeSystem().capture_point("p", "attackers", soldiers=10)
        assert squad["progress"] > solo["progress"] > 0

    def test_faction_check_prevents_own_and_contested_points(self):
        obj = SiegeSystem()
        own = obj.capture_point("p", "defenders", soldiers=10)
        assert own["captured"] is False
        assert own["reason"] == "own_point"

        enemy = obj.capture_point("p", "attackers", soldiers=10)
        assert enemy["progress"] > 0

        contested = obj.capture_point("q", "attackers", soldiers=2, defenders=5)
        assert contested["contested"] is True
        assert contested["progress"] == 0

    def test_progress_display(self):
        result = SiegeSystem().capture_point("p", "attackers", soldiers=5)
        assert 0 < result["progress"] < 100
        assert isinstance(result["progress_bar"], str)
        assert "%" in result["progress_bar"]


class TestSiegeEquipment:
    def test_target_selection_picks_nearest_wall(self):
        obj = SiegeSystem()
        result = obj.update_siege_equipment(
            equipment={"id": "ram", "position": 20},
            walls={"near": {"position": 30, "hp": 500},
                   "far": {"position": 90, "hp": 500}},
        )
        assert result["reports"][0]["target_id"] == "near"

    def test_equipment_attacks_wall_in_range(self):
        obj = SiegeSystem()
        result = obj.update_siege_equipment(
            equipment={"id": "ram", "position": 98},
            walls={"wall": {"position": 100, "hp": 500}},
        )
        report = result["reports"][0]
        assert report["action"] == "attack"
        assert report["wall_hp"] < 500

    def test_equipment_has_durability_and_can_be_destroyed(self):
        obj = SiegeSystem()
        result = obj.update_siege_equipment(
            equipment={"id": "ram", "position": 0},
            walls={"wall": {"position": 100, "hp": 500}},
        )
        assert 0 < result["reports"][0]["durability"] < 100

        for _ in range(25):
            result = obj.update_siege_equipment()
        assert result["reports"][0]["destroyed"] is True


class TestSiegeResources:
    def test_resources_gathered_by_workers(self):
        result = SiegeSystem().manage_siege_resources("attackers", workers=5, ticks=2)
        assert result["gathered"] == 100

    def test_building_equipment_consumes_resources(self):
        obj = SiegeSystem()
        early = obj.manage_siege_resources("attackers", build="ram")
        assert early["built"] is None
        assert early["reason"] == "insufficient_resources"

        for _ in range(3):
            obj.manage_siege_resources("attackers")
        built = obj.manage_siege_resources("attackers", build="ram")
        assert built["built"] == "ram"
        assert built["front"] < 250

    def test_resources_transported_from_rear_to_front(self):
        result = SiegeSystem().manage_siege_resources(
            "attackers", workers=10, ticks=1
        )
        assert result["transported"] == 50
        assert result["front"] == 50
        assert result["rear"] == 550


class TestRank:
    def test_rank_from_score(self):
        obj = SiegeSystem()
        assert obj.calculate_rank("a", kills=0)["rank"] == "soldier"
        assert obj.calculate_rank("b", kills=50)["rank"] == "sergeant"
        assert obj.calculate_rank("c", kills=300)["rank"] == "captain"

    def test_rank_permissions(self):
        obj = SiegeSystem()
        private = obj.calculate_rank("a")
        officer = obj.calculate_rank("b", kills=100)
        assert private["can_command"] is False
        assert "command" not in private["permissions"]
        assert officer["can_command"] is True
        assert "command" in officer["permissions"]

    def test_rank_reward_bonus(self):
        obj = SiegeSystem()
        private = obj.calculate_rank("a")
        officer = obj.calculate_rank("b", kills=100)
        assert officer["reward_multiplier"] > private["reward_multiplier"]


class TestBattleResult:
    def _obj_with_two_points(self):
        obj = SiegeSystem()
        obj.capture_point("p1", "attackers", soldiers=100)
        obj.capture_point("p2", "attackers", soldiers=100)
        obj.capture_point("p3", "defenders", soldiers=1)
        return obj

    def test_winner_decided_by_capture_ratio(self):
        obj = self._obj_with_two_points()
        result = obj.calculate_battle_result()
        assert result["winner"] == "attackers"
        stats = result["factions"]
        assert stats["attackers"]["capture_ratio"] > stats["defenders"]["capture_ratio"]

    def test_remaining_resources_break_ties(self):
        obj = SiegeSystem()
        obj.capture_point("p1", "attackers", soldiers=100)
        obj.capture_point("p2", "defenders")
        obj.manage_siege_resources("attackers", workers=50, ticks=5)
        result = obj.calculate_battle_result()
        stats = result["factions"]
        assert stats["attackers"]["capture_ratio"] == stats["defenders"]["capture_ratio"]
        assert (
            stats["attackers"]["remaining_resources"]
            > stats["defenders"]["remaining_resources"]
        )
        assert result["winner"] == "attackers"

    def test_rewards_scale_with_personal_contribution(self):
        obj = SiegeSystem()
        obj.calculate_rank("hero", kills=50, captures=2)
        obj.calculate_rank("recruit", kills=1)
        result = obj.calculate_battle_result(players=["hero", "recruit"])
        rewards = result["rewards"]
        assert rewards["hero"]["contribution"] > rewards["recruit"]["contribution"]
        assert rewards["hero"]["reward"] > rewards["recruit"]["reward"]
