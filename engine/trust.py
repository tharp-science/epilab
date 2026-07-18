from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class TrustNetwork:
    node_ids: list[str]
    dynamic: bool = False
    update_rule: str | None = None
    initial_weights: str = "uniform"
    weights: dict[tuple[str, str], float] = field(default_factory=dict)

    def __post_init__(self):
        self._initialize_weights()

    def _initialize_weights(self):
        n = len(self.node_ids)
        for i in self.node_ids:
            for j in self.node_ids:
                if i != j:
                    if self.initial_weights == "uniform":
                        self.weights[(i, j)] = 1.0 / max(n - 1, 1)
                    elif self.initial_weights == "random":
                        import random
                        self.weights[(i, j)] = random.random()
                    else:
                        self.weights[(i, j)] = 1.0 / max(n - 1, 1)

    def get_weight(self, from_node: str, to_node: str) -> float:
        return self.weights.get((from_node, to_node), 0.0)

    def update(self, node_id: str, success: bool) -> list[dict]:
        """Update trust weights after a transition. Returns trust_update events."""
        if not self.dynamic or self.update_rule != "successful_transition":
            return []
        events = []
        if success:
            for other_id in self.node_ids:
                if other_id != node_id:
                    key = (other_id, node_id)
                    old = self.weights.get(key, 0.0)
                    self.weights[key] = min(1.0, old * 1.05)
                    events.append({
                        "event_type": "trust_update",
                        "from_node": other_id,
                        "to_node": node_id,
                        "old_weight": old,
                        "new_weight": self.weights[key],
                    })
        return events

    def snapshot(self) -> dict:
        return {f"{k[0]}->{k[1]}": v for k, v in self.weights.items()}
