from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

MAX_ANCHOR_CHARS = 200
DEFAULT_WIP_LIMIT = 1


class NodeState(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DONE = "DONE"
    FROZEN = "FROZEN"
    BLOCKED = "BLOCKED"


class NodePriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class ValidationStatus(str, Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RequestStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ProjectConstitution(BaseModel):
    l1_anchor: str = Field(min_length=1, max_length=MAX_ANCHOR_CHARS)
    l2_rules: list[str] = Field(default_factory=list)
    l3_knowledge_index: list[str] = Field(default_factory=list)

    @field_validator("l2_rules")
    @classmethod
    def _trim_rules(cls, value: list[str]) -> list[str]:
        return [str(row).strip() for row in value if str(row).strip()]

    @field_validator("l3_knowledge_index")
    @classmethod
    def _trim_index(cls, value: list[str]) -> list[str]:
        return [str(row).strip() for row in value if str(row).strip()]


class ForestNode(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    state: NodeState = NodeState.DRAFT
    priority: NodePriority = NodePriority.P1
    validation_status: ValidationStatus = ValidationStatus.PENDING
    owner_agent_id: str = ""
    goal: str = ""
    constraints: str = ""
    next_action: str = ""

    @field_validator("owner_agent_id", "goal", "constraints", "next_action")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        return str(value or "").strip()


class ChangeRequest(BaseModel):
    target_node_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    status: RequestStatus = RequestStatus.PENDING


class HandshakeDecision(BaseModel):
    allowed: bool
    code: str
    message: str
    snapshot: dict[str, Any] = Field(default_factory=dict)


class StateTransitionError(ValueError):
    pass


class StateManager:
    def __init__(self, *, wip_limit: int = DEFAULT_WIP_LIMIT):
        self.wip_limit = max(1, int(wip_limit or DEFAULT_WIP_LIMIT))

    def active_nodes(self, nodes: list[ForestNode]) -> list[ForestNode]:
        return [row for row in nodes if row.state == NodeState.ACTIVE]

    def active_count(self, nodes: list[ForestNode]) -> int:
        return len(self.active_nodes(nodes))

    def can_activate(self, nodes: list[ForestNode], *, override: bool = False) -> bool:
        if override:
            return True
        return self.active_count(nodes) < self.wip_limit

    def snapshot(self, *, constitution: ProjectConstitution, nodes: list[ForestNode]) -> dict[str, Any]:
        active = self.active_nodes(nodes)
        current = active[0] if active else None
        return {
            "anchor": constitution.l1_anchor,
            "rules": constitution.l2_rules,
            "wip_limit": self.wip_limit,
            "active_count": len(active),
            "current_mission_id": current.id if current else None,
            "current_mission_title": current.title if current else None,
        }

    def preflight(
        self,
        *,
        intent: str,
        constitution: ProjectConstitution,
        nodes: list[ForestNode],
        override: bool = False,
        l2_violation: str = "",
    ) -> HandshakeDecision:
        if str(l2_violation).strip():
            return HandshakeDecision(
                allowed=False,
                code="L2_RULE_VIOLATION",
                message=str(l2_violation).strip(),
                snapshot=self.snapshot(constitution=constitution, nodes=nodes),
            )
        if not self.can_activate(nodes, override=override):
            active = self.active_nodes(nodes)
            first = active[0] if active else None
            msg = "WIP limit reached."
            if first is not None:
                msg = f"WIP limit reached. Finish '{first.title}' first."
            return HandshakeDecision(
                allowed=False,
                code="WIP_LIMIT_REACHED",
                message=msg,
                snapshot=self.snapshot(constitution=constitution, nodes=nodes),
            )
        return HandshakeDecision(
            allowed=True,
            code="OK",
            message=str(intent or "").strip() or "preflight ok",
            snapshot=self.snapshot(constitution=constitution, nodes=nodes),
        )

    def transition(
        self,
        *,
        nodes: list[ForestNode],
        node_id: str,
        to_state: NodeState,
        override: bool = False,
        validation_passed: bool = False,
        change_request_approved: bool = False,
    ) -> ForestNode:
        current = next((row for row in nodes if row.id == node_id), None)
        if current is None:
            raise StateTransitionError(f"node_not_found:{node_id}")

        from_state = current.state
        if from_state == to_state:
            return current

        if from_state == NodeState.DRAFT and to_state == NodeState.ACTIVE:
            if not self.can_activate(nodes, override=override):
                raise StateTransitionError("wip_limit_reached")
        elif from_state == NodeState.DRAFT and to_state == NodeState.FROZEN:
            pass
        elif from_state == NodeState.ACTIVE and to_state == NodeState.DONE:
            if not validation_passed:
                raise StateTransitionError("validation_not_passed")
            current.validation_status = ValidationStatus.PASSED
        elif from_state == NodeState.ACTIVE and to_state == NodeState.BLOCKED:
            current.validation_status = ValidationStatus.FAILED
        elif from_state == NodeState.DONE and to_state == NodeState.ACTIVE:
            if not change_request_approved:
                raise StateTransitionError("change_request_required")
            if not self.can_activate(nodes, override=override):
                raise StateTransitionError("wip_limit_reached")
        else:
            raise StateTransitionError(f"invalid_transition:{from_state}->{to_state}")

        current.state = to_state
        return current


def map_work_status_to_node_state(status: str) -> NodeState:
    normalized = str(status or "").strip().upper()
    if normalized == "IN_PROGRESS":
        return NodeState.ACTIVE
    if normalized == "DONE":
        return NodeState.DONE
    if normalized in {"BLOCKED", "FAILED"}:
        return NodeState.BLOCKED
    if normalized == "READY":
        return NodeState.DRAFT
    return NodeState.DRAFT


def build_nodes_from_work_items(work_items: list[dict[str, Any]]) -> list[ForestNode]:
    nodes: list[ForestNode] = []
    for row in work_items:
        node_id = str(row.get("id", "")).strip()
        if not node_id:
            continue
        title = str(row.get("title", "")).strip() or str(row.get("label", "")).strip() or node_id
        priority_score = int(row.get("priority_score", 50) or 50)
        if priority_score >= 90:
            priority = NodePriority.P0
        elif priority_score >= 60:
            priority = NodePriority.P1
        else:
            priority = NodePriority.P2
        nodes.append(
            ForestNode(
                id=node_id,
                title=title,
                state=map_work_status_to_node_state(str(row.get("status", ""))),
                priority=priority,
                validation_status=ValidationStatus.PENDING,
                owner_agent_id=str(row.get("owner_agent_id", "")).strip(),
                goal=str(row.get("issue", "")).strip(),
                constraints="",
                next_action=str(row.get("next_action", "")).strip(),
            )
        )
    return nodes
