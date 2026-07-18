import pytest
from engine.primitives import Proposal
from engine.primitives.null import NullPrimitive
from engine.primitives.boundary import BoundaryPrimitive
from engine.primitives.authority import AuthorityPrimitive
from engine.primitives.confidence import ConfidencePrimitive
from engine.primitives.mediation import MediationPrimitive
from engine.primitives.reversibility import ReversibilityPrimitive
from engine.agents import Node
from engine.claims import Claim, EpistemicState


def make_node(nid, authority_types=None, authority_weight=1.0, confidence_threshold=0.5, reversibility_tolerance=0.5, visible_claims=None):
    n = Node(
        id=nid,
        authority_types=authority_types or ["signal"],
        authority_weight=authority_weight,
        confidence_threshold=confidence_threshold,
        reversibility_tolerance=reversibility_tolerance,
        temporal_position=0.5,
        compounding_rate=0.0,
    )
    n.visible_claims = visible_claims or []
    return n


def make_claim(cid, state="unknown"):
    return Claim(id=cid, state=EpistemicState(state), difficulty=0.5, ambiguity=0.5)


def make_proposal(nid, cid, from_s, to_s, score=1.0):
    return Proposal(node_id=nid, claim_id=cid, from_state=from_s, to_state=to_s, confidence_score=score)


def test_null_passes_all():
    null = NullPrimitive()
    proposals = [make_proposal("n1", "c1", "unknown", "hypothesised")]
    nodes = {"n1": make_node("n1", visible_claims=["c1"])}
    claims = {"c1": make_claim("c1")}
    filtered = null.filter_proposals(proposals, nodes, claims, 0)
    assert len(filtered) == 1
    accepted, blocked = null.check_threshold(proposals, nodes, claims)
    assert len(accepted) == 1
    assert len(blocked) == 0


def test_boundary_filters_by_visible_claims():
    boundary = BoundaryPrimitive()
    # Node can see c1 but not c2
    nodes = {
        "n1": make_node("n1", visible_claims=["c1"])
    }
    claims = {"c1": make_claim("c1"), "c2": make_claim("c2")}
    proposals = [
        make_proposal("n1", "c1", "unknown", "hypothesised"),
        make_proposal("n1", "c2", "unknown", "hypothesised"),
    ]
    result = boundary.filter_proposals(proposals, nodes, claims, 0)
    assert len(result) == 1
    assert result[0].claim_id == "c1"


def test_authority_drops_unauthorized():
    auth = AuthorityPrimitive()
    # Node with only "signal" authority proposing a control-required transition
    nodes = {"n1": make_node("n1", authority_types=["signal"], authority_weight=1.0)}
    claims = {"c1": make_claim("c1", state="contested")}
    proposals = [make_proposal("n1", "c1", "contested", "provisionally_accepted")]
    result = auth.weight_proposals(proposals, nodes, claims)
    # "contested" -> "provisionally_accepted" requires control or temporal
    assert len(result) == 0


def test_authority_allows_authorized():
    auth = AuthorityPrimitive()
    nodes = {"n1": make_node("n1", authority_types=["control"], authority_weight=1.0)}
    claims = {"c1": make_claim("c1", state="contested")}
    proposals = [make_proposal("n1", "c1", "contested", "provisionally_accepted")]
    result = auth.weight_proposals(proposals, nodes, claims)
    assert len(result) == 1


def test_confidence_blocks_low_score():
    conf = ConfidencePrimitive(threshold_mean=0.8)
    nodes = {"n1": make_node("n1", confidence_threshold=0.8)}
    claims = {"c1": make_claim("c1")}
    proposals = [make_proposal("n1", "c1", "unknown", "hypothesised", score=0.1)]
    accepted, blocked = conf.check_threshold(proposals, nodes, claims)
    assert len(blocked) >= 1


def test_mediation_requires_control_for_contested():
    med = MediationPrimitive(mode="structured")
    # No control authority node
    nodes = {
        "n1": make_node("n1", authority_types=["signal"]),
    }
    claims = {"c1": make_claim("c1", state="contested")}
    proposals = [make_proposal("n1", "c1", "contested", "provisionally_accepted")]
    surviving, _ = med.mediate(proposals, nodes, claims, 0)
    assert len(surviving) == 0  # no mediator, blocked


def test_mediation_allows_with_control():
    med = MediationPrimitive(mode="structured")
    nodes = {
        "n1": make_node("n1", authority_types=["control"]),
    }
    claims = {"c1": make_claim("c1", state="contested")}
    proposals = [make_proposal("n1", "c1", "contested", "provisionally_accepted")]
    surviving, _ = med.mediate(proposals, nodes, claims, 0)
    assert len(surviving) == 1


def test_reversibility_blocks_low_tolerance():
    rev = ReversibilityPrimitive()
    nodes = {"n1": make_node("n1", reversibility_tolerance=0.1)}  # low tolerance
    claims = {"c1": make_claim("c1", state="operationalised")}
    proposals = [make_proposal("n1", "c1", "operationalised", "revisable")]
    allowed, _ = rev.check_reversibility(proposals, nodes, claims, 0)
    assert len(allowed) == 0


def test_reversibility_allows_high_tolerance():
    rev = ReversibilityPrimitive()
    nodes = {"n1": make_node("n1", reversibility_tolerance=0.7)}  # high tolerance
    claims = {"c1": make_claim("c1", state="operationalised")}
    proposals = [make_proposal("n1", "c1", "operationalised", "revisable")]
    allowed, _ = rev.check_reversibility(proposals, nodes, claims, 0)
    assert len(allowed) == 1
