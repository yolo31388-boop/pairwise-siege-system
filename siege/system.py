"""pairwise-siege-system - SiegeSystem

MMO 攻城战系统：占点、攻城器械、资源、军衔与战场结算。
"""

# 占点：每名士兵每秒贡献的占领进度（百分比）
CAPTURE_RATE_PER_SOLDIER = 5.0
# 攻城器械
EQUIPMENT_MOVE_SPEED = 10.0
EQUIPMENT_ATTACK_RANGE = 10.0
EQUIPMENT_ATTACK_DAMAGE = 20.0
WALL_COUNTER_DAMAGE = 5.0
# 资源
GATHER_RATE_PER_WORKER = 10.0
RESOURCE_MAX = 500.0
TRANSPORT_CAPACITY = 50.0
EQUIPMENT_COST = {"wood": 30.0, "stone": 20.0}
# 军衔：(名称, 所需积分, 是否可指挥, 奖励倍率)
RANKS = [
    ("元帅", 1000, True, 2.0),
    ("将军", 500, True, 1.6),
    ("校尉", 200, True, 1.3),
    ("老兵", 50, False, 1.1),
    ("小兵", 0, False, 1.0),
]
SCORE_PER_KILL = 10
SCORE_PER_CAPTURE = 100
BASE_REWARD = 100

DEFAULT_RESOURCE_STOCK = {"wood": 100.0, "stone": 100.0, "iron": 50.0}


class SiegeSystem:
    def __init__(self):
        self.state = {
            "points": {},
            "equipment": {},
            "walls": {},
            "factions": {},
            "players": {},
        }

    # ---- 内部辅助 ----

    def _faction(self, name):
        return self.state["factions"].setdefault(name, {
            "name": name,
            "rear": dict(DEFAULT_RESOURCE_STOCK),
            "frontline": {"wood": 0.0, "stone": 0.0, "iron": 0.0},
            "score": 0,
        })

    def _player(self, player_id, faction="attackers"):
        return self.state["players"].setdefault(player_id, {
            "id": player_id,
            "faction": faction,
            "kills": 0,
            "score": 0,
        })

    @staticmethod
    def _rank_for_score(score):
        for name, threshold, can_command, multiplier in RANKS:
            if score >= threshold:
                return name, can_command, multiplier
        return RANKS[-1][0], RANKS[-1][2], RANKS[-1][3]

    # ---- 占点 ----

    def capture_point(self, point_id="gate", faction="attackers",
                      soldier_count=1, elapsed=1.0):
        """占领据点。

        - 人数计算：占领速度与参战人数成正比
        - 阵营检查：己方已占领的点不会重复占领、不给敌方加分
        - 进度显示：返回当前占领进度百分比
        """
        point = self.state["points"].setdefault(point_id, {
            "id": point_id,
            "owner": "defenders",
            "progress": 100.0,
            "capturing": None,
        })
        fac = self._faction(faction)
        gain = CAPTURE_RATE_PER_SOLDIER * max(1, soldier_count) * elapsed

        # 阵营检查：点已属于己方，无需也无法重复占领
        if point["owner"] == faction:
            return {
                "point_id": point_id,
                "status": "already_owned",
                "owner": point["owner"],
                "progress": 100.0,
                "progress_display": "100%",
                "captured": False,
                "soldier_count": soldier_count,
            }

        if point["owner"] is not None and point["capturing"] is None:
            # 据点被敌方稳固控制：先削弱其控制度，归零后变为中立
            point["progress"] = max(0.0, point["progress"] - gain)
            if point["progress"] == 0.0:
                point["owner"] = None
        elif point["capturing"] not in (None, faction):
            # 第三方正在占领：先抵消对方进度
            point["progress"] = max(0.0, point["progress"] - gain)
            if point["progress"] == 0.0:
                point["capturing"] = None
        else:
            # 人数计算：占领速度与士兵数量成正比
            point["capturing"] = faction
            point["progress"] = min(100.0, point["progress"] + gain)

        captured = point["capturing"] == faction and point["progress"] >= 100.0
        if captured:
            point["owner"] = faction
            point["capturing"] = None
            fac["score"] += SCORE_PER_CAPTURE

        progress = round(point["progress"], 2)
        return {
            "point_id": point_id,
            "status": "captured" if captured else "capturing",
            "owner": point["owner"],
            "capturing": point["capturing"],
            "progress": progress,
            "progress_display": f"{progress:.0f}%",
            "captured": captured,
            "soldier_count": soldier_count,
        }

    # ---- 攻城器械 ----

    def update_siege_equipment(self, equipment_id="ram_1", walls=None,
                               elapsed=1.0):
        """更新攻城器械。

        - 目标选择：自动选择最近的未摧毁城墙
        - 攻击：进入射程后攻击城墙并削减其耐久
        - 耐久：器械有耐久度，会被守军反击打坏
        """
        if walls is not None:
            # 传入的城墙只在首次注册，伤害在持久状态上累积
            for wall in walls:
                self.state["walls"].setdefault(wall["id"], dict(wall))
        walls = self.state["walls"]
        if not walls:
            walls["wall_1"] = {"id": "wall_1", "position": 100.0, "hp": 200.0}

        equip = self.state["equipment"].setdefault(equipment_id, {
            "id": equipment_id,
            "position": 0.0,
            "durability": 100.0,
            "max_durability": 100.0,
            "target": None,
            "state": "idle",
        })
        if equip["state"] == "destroyed":
            return dict(equip)

        # 目标选择：当前目标无效时，选取最近的存活城墙
        alive = {wid: w for wid, w in walls.items() if w.get("hp", 0) > 0}
        if equip["target"] not in alive:
            if not alive:
                equip["target"] = None
                equip["state"] = "idle"
                return dict(equip)
            equip["target"] = min(
                alive, key=lambda wid: abs(alive[wid]["position"] - equip["position"])
            )

        target = alive[equip["target"]]
        distance = abs(target["position"] - equip["position"])

        if distance <= EQUIPMENT_ATTACK_RANGE:
            # 攻击：在射程内对城墙造成伤害
            equip["state"] = "attacking"
            target["hp"] = max(0.0, target["hp"] - EQUIPMENT_ATTACK_DAMAGE * elapsed)
            if target["hp"] == 0.0:
                equip["target"] = None
        else:
            # 向目标移动
            equip["state"] = "moving"
            step = min(EQUIPMENT_MOVE_SPEED * elapsed, distance)
            direction = 1 if target["position"] > equip["position"] else -1
            equip["position"] += direction * step

        # 耐久：守军反击消耗器械耐久，归零即被摧毁
        equip["durability"] = max(
            0.0, equip["durability"] - WALL_COUNTER_DAMAGE * elapsed
        )
        if equip["durability"] == 0.0:
            equip["state"] = "destroyed"

        result = dict(equip)
        result["target_hp"] = target["hp"]
        return result

    # ---- 资源 ----

    def manage_siege_resources(self, faction="attackers", workers=1,
                               elapsed=1.0, build=False, transport=None):
        """管理攻城资源。

        - 采集：资源随时间与工人数量增长，有上限，不是永远满
        - 消耗：建造器械要消耗前线资源，不足则失败
        - 运输：资源需从后方运输到前线才能使用，有运力上限
        """
        fac = self._faction(faction)
        rear, frontline = fac["rear"], fac["frontline"]

        # 采集：按工人数与时间增加后方库存，封顶 RESOURCE_MAX
        gathered = GATHER_RATE_PER_WORKER * max(0, workers) * elapsed
        for res in rear:
            rear[res] = min(RESOURCE_MAX, rear[res] + gathered)

        # 运输：后方 -> 前线，受运力限制
        capacity = TRANSPORT_CAPACITY * elapsed if transport is None else transport
        transported = {}
        for res in rear:
            amount = min(capacity, rear[res])
            rear[res] -= amount
            frontline[res] += amount
            transported[res] = amount

        # 消耗：建造器械从前线资源中扣费
        built = False
        if build:
            if all(frontline.get(res, 0.0) >= cost
                   for res, cost in EQUIPMENT_COST.items()):
                for res, cost in EQUIPMENT_COST.items():
                    frontline[res] -= cost
                built = True

        return {
            "faction": faction,
            "rear": dict(rear),
            "frontline": dict(frontline),
            "gathered": gathered,
            "transported": transported,
            "built": built,
            "equipment_cost": dict(EQUIPMENT_COST),
        }

    # ---- 军衔 ----

    def calculate_rank(self, player_id="player_1", kills=0, score=0,
                       faction="attackers"):
        """计算军衔。

        - 积分：击杀与贡献累积为积分，积分决定军衔
        - 权限：高军衔才有指挥权限
        - 奖励：军衔越高，奖励倍率越高
        """
        player = self._player(player_id, faction)
        player["kills"] += max(0, kills)
        player["score"] += max(0, kills) * SCORE_PER_KILL + max(0, score)

        rank, can_command, multiplier = self._rank_for_score(player["score"])
        return {
            "player_id": player_id,
            "kills": player["kills"],
            "score": player["score"],
            "rank": rank,
            "permissions": {
                "can_command": can_command,
                "can_build": player["score"] >= 50,
                "can_kick": rank in ("元帅", "将军"),
            },
            "reward_multiplier": multiplier,
        }

    # ---- 战场结算 ----

    def calculate_battle_result(self, factions=("attackers", "defenders")):
        """战场结算。

        - 占点比：按各阵营占领的据点比例计分
        - 资源剩余：剩余资源计入总分
        - 个人贡献：按个人积分与军衔倍率发放奖励
        """
        for name in factions:
            self._faction(name)
        points = self.state["points"]
        total_points = len(points)

        control, resources_left, scores = {}, {}, {}
        for name, fac in self.state["factions"].items():
            owned = sum(1 for p in points.values() if p["owner"] == name)
            ratio = owned / total_points if total_points else 0.0
            remaining = sum(fac["rear"].values()) + sum(fac["frontline"].values())
            control[name] = round(ratio, 4)
            resources_left[name] = round(remaining, 2)
            # 总分 = 战场得分 + 占点比加成 + 资源剩余加成
            scores[name] = round(
                fac["score"] + ratio * 500 + remaining * 0.1, 2
            )

        winner = max(scores, key=scores.get) if scores else None

        # 个人贡献：基础奖励 × 军衔倍率，胜方额外加成
        player_rewards = {}
        for pid, player in self.state["players"].items():
            _, _, multiplier = self._rank_for_score(player["score"])
            reward = BASE_REWARD * multiplier + player["score"] * 0.5
            if player["faction"] == winner:
                reward *= 1.5
            player_rewards[pid] = {
                "faction": player["faction"],
                "contribution": player["score"],
                "reward": round(reward, 2),
            }

        return {
            "winner": winner,
            "control_ratio": control,
            "resources_remaining": resources_left,
            "scores": scores,
            "player_rewards": player_rewards,
        }
