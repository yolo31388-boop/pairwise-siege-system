"""pairwise-siege-system - SiegeSystem

Siege-battle domain logic: point capture, siege equipment, resources,
ranks and battle-result calculation.
"""

CAPTURE_RATE_PER_SOLDIER = 5.0
GATHER_RATE_PER_WORKER = 10
TRANSPORT_RATE = 50
WALL_DEFENSE_DAMAGE = 5

EQUIPMENT_COSTS = {"ram": 100, "catapult": 150, "siege_tower": 200}
EQUIPMENT_DEFAULTS = {
    "position": 0.0,
    "speed": 10.0,
    "range": 5.0,
    "attack": 20.0,
    "durability": 100.0,
}

# rank -> (min_score, reward_multiplier, can_command)
RANK_TABLE = [
    ("general", 5000, 3.0, True),
    ("captain", 2000, 2.0, True),
    ("lieutenant", 800, 1.5, True),
    ("sergeant", 300, 1.25, False),
    ("corporal", 100, 1.1, False),
    ("soldier", 0, 1.0, False),
]

SCORE_PER_KILL = 10
SCORE_PER_CAPTURE = 50
SCORE_PER_ASSIST = 5
PRIZE_POOL = 1000.0


class SiegeSystem:
    def __init__(self):
        self.state = {
            "points": {},
            "equipment": {},
            "walls": {},
            "resources": {
                "attackers": {"rear": 500, "front": 0},
                "defenders": {"rear": 500, "front": 0},
            },
            "players": {},
        }

    # ---- capture points ----

    @staticmethod
    def _progress_bar(progress, width=10):
        filled = int(round(progress / 100.0 * width))
        return "[" + "#" * filled + "-" * (width - filled) + "] {:.0f}%".format(progress)

    def capture_point(self, point_id="gate", faction="attackers",
                      soldiers=1, defenders=0, ticks=1):
        point = self.state["points"].setdefault(
            point_id, {"owner": "defenders", "progress": 0.0, "capturing": None}
        )
        result = {
            "point_id": point_id,
            "faction": faction,
            "captured": False,
            "contested": False,
            "reason": None,
        }

        if faction == point["owner"]:
            result["reason"] = "own_point"
        else:
            net_attackers = soldiers - defenders
            if net_attackers <= 0:
                result["contested"] = True
                result["reason"] = "contested"
            else:
                if point["capturing"] not in (None, faction):
                    point["progress"] = 0.0
                point["capturing"] = faction
                point["progress"] = min(
                    100.0,
                    point["progress"] + CAPTURE_RATE_PER_SOLDIER * net_attackers * ticks,
                )
                if point["progress"] >= 100.0:
                    point["owner"] = faction
                    point["progress"] = 0.0
                    point["capturing"] = None
                    result["captured"] = True

        result["owner"] = point["owner"]
        result["progress"] = 100.0 if result["captured"] else point["progress"]
        result["progress_bar"] = self._progress_bar(result["progress"])
        return result

    # ---- siege equipment ----

    def update_siege_equipment(self, equipment=None, walls=None, dt=1.0):
        if walls:
            for wall_id, wall in walls.items():
                self.state["walls"].setdefault(wall_id, dict(wall))
        if equipment:
            units = equipment if isinstance(equipment, list) else [equipment]
            for unit in units:
                entry = dict(EQUIPMENT_DEFAULTS)
                entry.update(unit)
                self.state["equipment"].setdefault(entry["id"], entry)
        if not self.state["walls"]:
            self.state["walls"]["wall-1"] = {"position": 100.0, "hp": 500.0}
        if not self.state["equipment"]:
            self.state["equipment"]["ram-1"] = dict(EQUIPMENT_DEFAULTS, id="ram-1")

        reports = []
        for unit_id, unit in self.state["equipment"].items():
            report = {"equipment_id": unit_id, "destroyed": False}
            if unit["durability"] <= 0:
                report.update(action="destroyed", destroyed=True,
                              durability=0.0, target_id=None)
                reports.append(report)
                continue

            targets = {wid: w for wid, w in self.state["walls"].items() if w["hp"] > 0}
            if not targets:
                report.update(action="no_target", target_id=None,
                              durability=unit["durability"])
                reports.append(report)
                continue

            target_id = min(
                targets,
                key=lambda wid: abs(targets[wid]["position"] - unit["position"]),
            )
            target = targets[target_id]
            distance = abs(target["position"] - unit["position"])

            action = "idle"
            if distance > unit["range"]:
                step = min(unit["speed"] * dt, distance - unit["range"])
                direction = 1 if target["position"] > unit["position"] else -1
                unit["position"] += step * direction
                distance = abs(target["position"] - unit["position"])
                action = "move"
            if distance <= unit["range"]:
                target["hp"] = max(0.0, target["hp"] - unit["attack"] * dt)
                action = "attack"

            unit["durability"] = max(0.0, unit["durability"] - WALL_DEFENSE_DAMAGE * dt)

            report.update(
                action=action,
                target_id=target_id,
                position=unit["position"],
                durability=unit["durability"],
                destroyed=unit["durability"] <= 0,
                wall_hp=target["hp"],
            )
            reports.append(report)
        return {"reports": reports}

    # ---- resources ----

    def manage_siege_resources(self, faction="attackers", workers=0,
                               build=None, ticks=1):
        res = self.state["resources"].setdefault(faction, {"rear": 0, "front": 0})

        gathered = workers * GATHER_RATE_PER_WORKER * ticks
        res["rear"] += gathered

        transported = min(res["rear"], TRANSPORT_RATE * ticks)
        res["rear"] -= transported
        res["front"] += transported

        built = None
        reason = None
        if build is not None:
            cost = EQUIPMENT_COSTS.get(build)
            if cost is None:
                reason = "unknown_equipment"
            elif res["front"] >= cost:
                res["front"] -= cost
                built = build
            else:
                reason = "insufficient_resources"

        return {
            "faction": faction,
            "gathered": gathered,
            "transported": transported,
            "rear": res["rear"],
            "front": res["front"],
            "built": built,
            "reason": reason,
        }

    # ---- ranks ----

    def calculate_rank(self, player_id="player", kills=0, captures=0, assists=0):
        player = self.state["players"].setdefault(
            player_id, {"score": 0, "kills": 0, "captures": 0, "assists": 0}
        )
        player["kills"] += kills
        player["captures"] += captures
        player["assists"] += assists
        player["score"] += (
            kills * SCORE_PER_KILL
            + captures * SCORE_PER_CAPTURE
            + assists * SCORE_PER_ASSIST
        )
        score = player["score"]

        rank, _, multiplier, can_command = max(
            (entry for entry in RANK_TABLE if score >= entry[1]),
            key=lambda entry: entry[1],
        )
        permissions = ["fight"]
        if can_command:
            permissions += ["command", "rally"]

        return {
            "player_id": player_id,
            "score": score,
            "rank": rank,
            "permissions": permissions,
            "can_command": can_command,
            "reward_multiplier": multiplier,
        }

    # ---- battle result ----

    def calculate_battle_result(self, factions=("attackers", "defenders"),
                                players=None):
        points = self.state["points"]
        total_points = max(len(points), 1)

        summary = {}
        for faction in factions:
            owned = sum(1 for p in points.values() if p["owner"] == faction)
            res = self.state["resources"].get(faction, {"rear": 0, "front": 0})
            summary[faction] = {
                "owned_points": owned,
                "capture_ratio": owned / total_points,
                "remaining_resources": res["rear"] + res["front"],
            }

        total_resources = sum(s["remaining_resources"] for s in summary.values()) or 1
        for faction, stats in summary.items():
            stats["score"] = (
                0.7 * stats["capture_ratio"]
                + 0.3 * stats["remaining_resources"] / total_resources
            )
        winner = max(summary, key=lambda f: summary[f]["score"])

        players = list(players) if players is not None else list(self.state["players"])
        contributions = {}
        for pid in players:
            p = self.state["players"].get(
                pid, {"kills": 0, "captures": 0, "assists": 0}
            )
            contributions[pid] = (
                p["kills"] * SCORE_PER_KILL
                + p["captures"] * SCORE_PER_CAPTURE
                + p["assists"] * SCORE_PER_ASSIST
            )
        total_contribution = sum(contributions.values()) or 1

        rewards = {}
        for pid in players:
            share = contributions[pid] / total_contribution
            multiplier = self.calculate_rank(pid)["reward_multiplier"]
            rewards[pid] = {
                "contribution": contributions[pid],
                "share": share,
                "reward": PRIZE_POOL * share * multiplier,
            }

        return {"winner": winner, "factions": summary, "rewards": rewards}
