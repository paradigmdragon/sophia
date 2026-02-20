import pytest

from core.forest_logic import (
    ChangeRequest,
    ForestNode,
    NodeState,
    ProjectConstitution,
    RequestStatus,
    StateManager,
    StateTransitionError,
)


def _constitution() -> ProjectConstitution:
    return ProjectConstitution(
        l1_anchor="소피아 프로젝트 집중 보조 운영체계 완성",
        l2_rules=["WIP=1 유지", "DONE 변경은 승인 필요"],
        l3_knowledge_index=[],
    )


def test_preflight_blocks_when_wip_reached():
    manager = StateManager(wip_limit=1)
    constitution = _constitution()
    nodes = [ForestNode(id="n1", title="A", state=NodeState.ACTIVE)]

    decision = manager.preflight(intent="activate n2", constitution=constitution, nodes=nodes)
    assert decision.allowed is False
    assert decision.code == "WIP_LIMIT_REACHED"


def test_transition_rules_and_wip_limit():
    manager = StateManager(wip_limit=1)
    n1 = ForestNode(id="n1", title="A", state=NodeState.DRAFT)
    n2 = ForestNode(id="n2", title="B", state=NodeState.DRAFT)
    nodes = [n1, n2]

    manager.transition(nodes=nodes, node_id="n1", to_state=NodeState.ACTIVE)
    assert n1.state == NodeState.ACTIVE

    with pytest.raises(StateTransitionError):
        manager.transition(nodes=nodes, node_id="n2", to_state=NodeState.ACTIVE)

    with pytest.raises(StateTransitionError):
        manager.transition(nodes=nodes, node_id="n1", to_state=NodeState.DONE, validation_passed=False)

    manager.transition(nodes=nodes, node_id="n1", to_state=NodeState.DONE, validation_passed=True)
    assert n1.state == NodeState.DONE


def test_done_to_active_requires_change_request():
    manager = StateManager(wip_limit=1)
    n1 = ForestNode(id="n1", title="A", state=NodeState.DONE)
    nodes = [n1]

    with pytest.raises(StateTransitionError):
        manager.transition(nodes=nodes, node_id="n1", to_state=NodeState.ACTIVE, change_request_approved=False)

    manager.transition(nodes=nodes, node_id="n1", to_state=NodeState.ACTIVE, change_request_approved=True)
    assert n1.state == NodeState.ACTIVE


def test_change_request_model():
    req = ChangeRequest(target_node_id="node-1", reason="hotfix", status=RequestStatus.PENDING)
    assert req.target_node_id == "node-1"
    assert req.status == RequestStatus.PENDING
