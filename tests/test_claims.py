import pytest
from engine.claims import EpistemicState, validate_transition, Claim, TRANSITIONS

VALID_TRANSITIONS = [
    (EpistemicState.UNKNOWN, EpistemicState.HYPOTHESISED),
    (EpistemicState.HYPOTHESISED, EpistemicState.CONTESTED),
    (EpistemicState.CONTESTED, EpistemicState.PROVISIONALLY_ACCEPTED),
    (EpistemicState.PROVISIONALLY_ACCEPTED, EpistemicState.OPERATIONALISED),
    (EpistemicState.OPERATIONALISED, EpistemicState.REVISABLE),
    (EpistemicState.OPERATIONALISED, EpistemicState.ARCHIVED),
    (EpistemicState.REVISABLE, EpistemicState.CONTESTED),
]

INVALID_TRANSITIONS = [
    (EpistemicState.UNKNOWN, EpistemicState.OPERATIONALISED),
    (EpistemicState.UNKNOWN, EpistemicState.CONTESTED),
    (EpistemicState.HYPOTHESISED, EpistemicState.OPERATIONALISED),
    (EpistemicState.HYPOTHESISED, EpistemicState.UNKNOWN),
    (EpistemicState.ARCHIVED, EpistemicState.OPERATIONALISED),
    (EpistemicState.OPERATIONALISED, EpistemicState.UNKNOWN),
    (EpistemicState.CONTESTED, EpistemicState.OPERATIONALISED),  # skip
    (EpistemicState.PROVISIONALLY_ACCEPTED, EpistemicState.CONTESTED),
]

@pytest.mark.parametrize("from_s,to_s", VALID_TRANSITIONS)
def test_valid_transition(from_s, to_s):
    assert validate_transition(from_s, to_s) is True

@pytest.mark.parametrize("from_s,to_s", INVALID_TRANSITIONS)
def test_invalid_transition(from_s, to_s):
    assert validate_transition(from_s, to_s) is False

def test_claim_defaults():
    c = Claim(id="c1", state=EpistemicState.UNKNOWN)
    assert c.ground_truth is None
    assert c.domain is None
    assert c.difficulty == 0.5
    assert c.ambiguity == 0.5
    assert c.ticks_in_state == 0
