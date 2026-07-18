from __future__ import annotations
import json
import os
from pathlib import Path


class EventLog:
    def __init__(self, path: Path, primitives_active: dict, state_transition_logging_mode: str = "full"):
        self.path = path
        self.primitives_active = primitives_active
        self.state_transition_logging_mode = state_transition_logging_mode
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(path, "w")

    def emit(self, event: dict) -> None:
        event["primitive_modules_active"] = self.primitives_active
        self._file.write(json.dumps(event) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def emit_transition(
        self,
        tick: int,
        node_id: str,
        claim_id: str,
        from_state: str,
        to_state: str,
        authority_invoked: str | None = None,
        confidence_score: float = 1.0,
        claim_difficulty: float = 0.5,
        claim_ambiguity: float = 0.5,
        influencing_nodes: list[str] | None = None,
        mediated_by: str | None = None,
        lineage_challenge: bool = False,
        trust_weights: dict | None = None,
    ) -> None:
        if self.state_transition_logging_mode == "off":
            return
        event = {
            "tick": tick,
            "event_type": "state_transition",
            "node_id": node_id,
            "claim_id": claim_id,
            "from_state": from_state,
            "to_state": to_state,
        }
        if self.state_transition_logging_mode == "full":
            event.update({
                "authority_invoked": authority_invoked,
                "confidence_score": confidence_score,
                "claim_difficulty": claim_difficulty,
                "claim_ambiguity": claim_ambiguity,
                "influencing_nodes": influencing_nodes or [],
                "mediated_by": mediated_by,
                "lineage_challenge": lineage_challenge,
                "trust_weights_at_tick": trust_weights or {},
            })
        self.emit(event)

    def emit_blocked(self, tick: int, node_id: str, claim_id: str, from_state: str, to_state: str, reason: str) -> None:
        self.emit({
            "tick": tick,
            "event_type": "transition_blocked",
            "node_id": node_id,
            "claim_id": claim_id,
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
        })

    def emit_snapshot(self, tick: int, claims: dict, nodes: dict, trust: dict) -> None:
        self.emit({
            "tick": tick,
            "event_type": "system_snapshot",
            "claims": {cid: c.state.value for cid, c in claims.items()},
            "authority_weights": {nid: n.authority_weight for nid, n in nodes.items()},
            "trust_weights": trust,
        })
