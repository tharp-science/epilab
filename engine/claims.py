from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EpistemicState(str, Enum):
    UNKNOWN = "unknown"
    HYPOTHESISED = "hypothesised"
    CONTESTED = "contested"
    PROVISIONALLY_ACCEPTED = "provisionally_accepted"
    OPERATIONALISED = "operationalised"
    ARCHIVED = "archived"
    REVISABLE = "revisable"


# Allowed transitions
TRANSITIONS: dict[EpistemicState, set[EpistemicState]] = {
    EpistemicState.UNKNOWN: {EpistemicState.HYPOTHESISED},
    EpistemicState.HYPOTHESISED: {EpistemicState.CONTESTED},
    EpistemicState.CONTESTED: {EpistemicState.PROVISIONALLY_ACCEPTED},
    EpistemicState.PROVISIONALLY_ACCEPTED: {EpistemicState.OPERATIONALISED},
    EpistemicState.OPERATIONALISED: {EpistemicState.REVISABLE, EpistemicState.ARCHIVED},
    EpistemicState.REVISABLE: {EpistemicState.CONTESTED},
    EpistemicState.ARCHIVED: set(),
}


def validate_transition(from_state: EpistemicState, to_state: EpistemicState) -> bool:
    return to_state in TRANSITIONS.get(from_state, set())


@dataclass
class Claim:
    id: str
    state: EpistemicState
    ground_truth: Optional[bool] = None
    domain: Optional[str] = None
    difficulty: float = 0.5
    ambiguity: float = 0.5
    ticks_in_state: int = 0  # how many ticks at current state
    operationalised_at: Optional[int] = None  # tick when first operationalised
    last_reversion_tick: Optional[int] = None
