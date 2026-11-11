"""Boundary tests for Work Order 9-state machine transitions and invalid state rollbacks.

Covers:
1. Structural consistency between ``apps.workorders.workflow.WORK_ORDER_STATUS``
   (9 lifecycle states + CANCELLED), ``services.TRANSITIONS``, and ``ui_views.WORKFLOW_STEPS``.
2. Exhaustive 10x10 state-to-state matrix on ``services.transition_work_order`` and
   10x11 state-by-action matrix on ``workflow.WORK_ORDER_STATUS``:
   - Only approved forward edges, hold/resume, supervisor rework, and pre-execution cancel pass.
   - All invalid forward skips, invalid backward rollbacks, self-transitions, and terminal
     exits raise ``InvalidTransition`` without mutating DB state, version, events, or audits.
3. Dedicated service functions (plan, assign, dispatch, start, hold, resume, complete,
   submit_for_review, close, return_for_rework, review, cancel, reassign, reschedule, update)
   called from invalid/rollback states and terminal states.
4. Direct ORM ``WorkOrder.save()`` status-rollback guard.
5. REST API (``WorkOrderViewSet`` endpoints, ``/transition/``, ``PATCH``) and Workspace API
   (``/api/v1/workspace/jobs/{id}/start|pause|resume|complete/``) boundary rejections.
6. Multi-cycle hold/resume & supervisor return-for-rework loops with SLA/Incident sync.
7. Optimistic concurrency (``expected_version``), guard input length boundaries, and
   atomic cross-module transaction rollbacks when downstream hooks fail.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.core.exceptions import Conflict, InvalidTransition, ValidationFailed
from apps.incidents import services as incident_services
from apps.incidents.models import ServiceRequest
from apps.inventory import services as inventory_services
from apps.inventory.models import WorkOrderPart
from apps.sla import services as sla_services
from apps.sla.models import SLATracking
from apps.workorders import services, ui_views, workflow
from apps.workorders.models import (
    ClosureApproval,
    WorkOrder,
    WorkOrderAssignment,
    WorkOrderEvent,
    WorkOrderSignoff,
)
from apps.workspace import services as workspace_services
from tests.phase3_support import finish_work, new_wo, step

pytestmark = pytest.mark.django_db

NINE_LIFECYCLE_STATES = (
    WorkOrder.Status.DRAFT,
    WorkOrder.Status.PLANNED,
    WorkOrder.Status.ASSIGNED,
    WorkOrder.Status.DISPATCHED,
    WorkOrder.Status.IN_PROGRESS,
    WorkOrder.Status.ON_HOLD,
    WorkOrder.Status.COMPLETED,
    WorkOrder.Status.SUPERVISOR_REVIEW,
    WorkOrder.Status.CLOSED,
)

ALL_TEN_STATES = NINE_LIFECYCLE_STATES + (WorkOrder.Status.CANCELLED,)


_SLOT_COUNTER = 0


def _next_window():
    global _SLOT_COUNTER
    _SLOT_COUNTER += 1
    start = timezone.now() + timedelta(days=2, hours=3 * _SLOT_COUNTER)
    return start, start + timedelta(hours=2)


def _mark_checklist_valid(wo):
    from apps.workorders.checklist_adapter import record_external_validation

    wo.checklist_instance_ref = f"boundary-m08:{wo.pk}"
    record_external_validation(wo, status="COMPLETED", validation_state="VALID", completed_at=timezone.now())
    wo.save(
        update_fields=[
            "checklist_instance_ref",
            "checklist_status",
            "checklist_validation_state",
            "checklist_completed_at",
            "checklist_validated_at",
            "updated_at",
        ]
    )
    return wo


def _advance_to_state(p3, target_state, *, work_type="PREVENTIVE"):
    """Create a WorkOrder and advance it legitimately through services to target_state."""
    wo = new_wo(p3, work_type=work_type, title=f"Boundary {target_state}")
    if target_state == WorkOrder.Status.DRAFT:
        return wo
    if target_state == WorkOrder.Status.CANCELLED:
        return step(wo, "cancel", p3, "planner", reason="Cancelled in boundary setup")

    t0, t1 = _next_window()
    wo = step(wo, "plan", p3, "planner", planned_start=t0, planned_end=t1)
    if target_state == WorkOrder.Status.PLANNED:
        return wo

    wo = step(wo, "assign", p3, "planner", technician=p3["tech"])
    if target_state == WorkOrder.Status.ASSIGNED:
        return wo

    wo = step(wo, "dispatch", p3, "planner")
    if target_state == WorkOrder.Status.DISPATCHED:
        return wo

    wo = step(wo, "start", p3, "tech")
    if target_state == WorkOrder.Status.IN_PROGRESS:
        return wo

    if target_state == WorkOrder.Status.ON_HOLD:
        return step(wo, "hold", p3, "tech", reason="Waiting on isolation permit")

    wo = finish_work(wo, p3, tech="tech")
    if target_state == WorkOrder.Status.COMPLETED:
        return wo

    wo = step(wo, "submit_for_review", p3, "tech")
    if target_state == WorkOrder.Status.SUPERVISOR_REVIEW:
        return wo

    if target_state == WorkOrder.Status.CLOSED:
        return step(wo, "close", p3, "sup", comment="Approved during setup")

    raise ValueError(f"Unsupported target_state: {target_state}")


def _make_linked_review_wo(p3):
    """Create an approved ServiceRequest linked to a WorkOrder in SUPERVISOR_REVIEW."""
    sr = incident_services.create_request(
        p3["org"],
        asset=p3["asset"],
        reporter=p3["tech"],
        title="Linked valve fault",
        description="Valve sticking during cycle",
        severity="HIGH",
        service_impact=ServiceRequest.Impact.PARTIAL,
        actor=p3["tech"].user,
    )
    sr = incident_services.transition(sr, action="triage", actor=p3["ops"].user)
    sr = incident_services.transition(sr, action="approve", actor=p3["ops"].user)
    wo = incident_services.create_work_order_for_request(
        sr, actor=p3["planner"].user, membership=p3["planner"]
    )
    t0, t1 = _next_window()
    wo = step(
        wo,
        "plan",
        p3,
        "planner",
        planned_start=t0,
        planned_end=t1,
        work_type=WorkOrder.WorkType.PREVENTIVE,
    )
    wo = step(wo, "assign", p3, "planner", technician=p3["tech"])
    wo = step(wo, "dispatch", p3, "planner")
    wo = step(wo, "start", p3, "tech")
    wo = finish_work(wo, p3, tech="tech")
    wo = step(wo, "submit_for_review", p3, "tech")
    sr.refresh_from_db()
    return wo, sr


# -------------------------------------------------------------------------------------------------
# 1. Structural consistency & exhaustive state-machine matrices
# -------------------------------------------------------------------------------------------------


def test_nine_state_definitions_and_workflow_consistency():
    assert tuple(code for code, _ in ui_views.WORKFLOW_STEPS) == NINE_LIFECYCLE_STATES
    assert len(NINE_LIFECYCLE_STATES) == 9
    assert workflow.STATES == ALL_TEN_STATES
    assert set(workflow.TERMINAL_STATES) == {WorkOrder.Status.CLOSED, WorkOrder.Status.CANCELLED}

    sm_edges = {}
    for state in ALL_TEN_STATES:
        sm_edges[state] = {t.target for t in workflow.WORK_ORDER_STATUS.available(state)}

    svc_edges = {}
    for state in ALL_TEN_STATES:
        targets = set(services.TRANSITIONS.get(state, set()))
        if state in services.CANCELLABLE_STATUSES:
            targets.add(WorkOrder.Status.CANCELLED)
        svc_edges[state] = targets

    assert sm_edges == svc_edges
    assert sm_edges[WorkOrder.Status.CLOSED] == set()
    assert sm_edges[WorkOrder.Status.CANCELLED] == set()


def test_workflow_state_machine_exhaustive_action_matrix():
    all_actions = sorted({t.action for t in workflow.WORK_ORDER_STATUS.transitions} | {"unknown_action"})
    allowed_map = {
        (src, t.action): t.target
        for t in workflow.WORK_ORDER_STATUS.transitions
        for src in t.sources
    }

    for state in ALL_TEN_STATES:
        for action in all_actions:
            dummy = WorkOrder(status=state)
            expected = allowed_map.get((state, action))
            if expected is not None:
                prev, nxt = workflow.WORK_ORDER_STATUS.apply(dummy, action)
                assert prev == state
                assert nxt == expected
                assert dummy.status == expected
            else:
                with pytest.raises(InvalidTransition):
                    workflow.WORK_ORDER_STATUS.apply(dummy, action)
                assert dummy.status == state


def test_service_transition_work_order_exhaustive_10x10_matrix(p3):
    """Every invalid forward skip, backward rollback, self-move, and terminal exit fails atomically."""
    allowed_targets = {
        state: set(services.TRANSITIONS.get(state, set()))
        | ({WorkOrder.Status.CANCELLED} if state in services.CANCELLABLE_STATUSES else set())
        for state in ALL_TEN_STATES
    }

    actor = p3["ops"].user
    membership = p3["ops"]

    for from_state in ALL_TEN_STATES:
        for to_state in ALL_TEN_STATES:
            wo = _advance_to_state(p3, from_state)
            before_version = wo.version
            before_events = WorkOrderEvent.objects.filter(work_order=wo).count()
            before_audits = AuditLog.objects.filter(organization=p3["org"], target_id=str(wo.pk)).count()

            if to_state in allowed_targets[from_state]:
                moved = services.transition_work_order(
                    wo,
                    to_state,
                    membership=membership,
                    actor=actor,
                    permission="work_order.view",
                    action=f"test_to_{to_state.lower()}",
                )
                assert moved.status == to_state
                assert moved.version == before_version + 1
                assert WorkOrderEvent.objects.filter(work_order=wo).count() == before_events + 1
            else:
                with pytest.raises(InvalidTransition) as exc_info:
                    services.transition_work_order(
                        wo,
                        to_state,
                        membership=membership,
                        actor=actor,
                        permission="work_order.view",
                        action=f"invalid_to_{to_state.lower()}",
                    )
                assert exc_info.value.code == "invalid_work_order_transition"
                wo.refresh_from_db()
                assert wo.status == from_state
                assert wo.version == before_version
                assert WorkOrderEvent.objects.filter(work_order=wo).count() == before_events
                assert AuditLog.objects.filter(organization=p3["org"], target_id=str(wo.pk)).count() == before_audits


# -------------------------------------------------------------------------------------------------
# 2. Dedicated service methods: invalid rollbacks, skips, terminal states & operations
# -------------------------------------------------------------------------------------------------


def test_dedicated_services_reject_invalid_rollbacks_and_terminal_transitions(p3):
    t0 = timezone.now() + timedelta(days=5)

    def _call_plan(wo):
        return services.plan_work_order(
            wo,
            membership=p3["planner"],
            actor=p3["planner"].user,
            planned_start=t0,
            planned_end=t0 + timedelta(hours=2),
            due_at=t0 + timedelta(days=1),
            estimated_hours=Decimal("1.00"),
            work_type=WorkOrder.WorkType.PREVENTIVE,
            priority=WorkOrder.Priority.MEDIUM,
        )

    def _call_assign(wo):
        return services.assign_work_order(
            wo,
            membership=p3["planner"],
            actor=p3["planner"].user,
            assignee_id=p3["tech2"].pk,
            scheduled_start=t0,
            scheduled_end=t0 + timedelta(hours=2),
        )

    def _call_dispatch(wo):
        return services.dispatch_work_order(wo, membership=p3["planner"], actor=p3["planner"].user)

    def _call_start(wo):
        return services.start_work_order(wo, membership=p3["tech"], actor=p3["tech"].user)

    def _call_hold(wo):
        return services.hold_work_order(wo, membership=p3["tech"], actor=p3["tech"].user, reason="Hold boundary test")

    def _call_resume(wo):
        return services.resume_work_order(wo, membership=p3["tech"], actor=p3["tech"].user)

    def _call_complete(wo):
        return services.complete_work_order(
            wo,
            membership=p3["tech"],
            actor=p3["tech"].user,
            resolution_notes="Completed boundary verification.",
        )

    def _call_submit(wo):
        return services.submit_for_review(wo, membership=p3["tech"], actor=p3["tech"].user)

    def _call_rework(wo):
        return services.return_for_rework(
            wo,
            membership=p3["sup"],
            actor=p3["sup"].user,
            comment="Returning for rework boundary test.",
        )

    def _call_close(wo):
        return services.close_work_order(
            wo,
            membership=p3["sup"],
            actor=p3["sup"].user,
            comment="Closing boundary test.",
        )

    def _call_cancel(wo):
        return services.cancel_work_order(
            wo,
            membership=p3["planner"],
            actor=p3["planner"].user,
            reason="Cancelling boundary test.",
        )

    service_valid_sources = [
        (_call_plan, {WorkOrder.Status.DRAFT}),
        (_call_assign, {WorkOrder.Status.PLANNED}),
        (_call_dispatch, {WorkOrder.Status.ASSIGNED}),
        (_call_start, {WorkOrder.Status.DISPATCHED}),
        (_call_hold, {WorkOrder.Status.IN_PROGRESS}),
        (_call_resume, {WorkOrder.Status.ON_HOLD}),
        (_call_complete, {WorkOrder.Status.IN_PROGRESS}),
        (_call_submit, {WorkOrder.Status.COMPLETED}),
        (_call_rework, {WorkOrder.Status.SUPERVISOR_REVIEW}),
        (_call_close, {WorkOrder.Status.SUPERVISOR_REVIEW, WorkOrder.Status.CLOSED}),
        (_call_cancel, set(services.CANCELLABLE_STATUSES)),
    ]

    for state in ALL_TEN_STATES:
        wo = _advance_to_state(p3, state)
        for fn, valid_sources in service_valid_sources:
            if state in valid_sources:
                continue
            version_before = wo.version
            events_before = wo.events.count()
            with pytest.raises(InvalidTransition):
                fn(wo)
            wo.refresh_from_db()
            assert wo.status == state
            assert wo.version == version_before
            assert wo.events.count() == events_before


def test_closed_without_approval_record_rejects_idempotent_close_and_rejects_rework(p3):
    wo = _advance_to_state(p3, WorkOrder.Status.SUPERVISOR_REVIEW)
    # Force CLOSED without creating ClosureApproval(APPROVED) to test guard boundary
    WorkOrder.objects.filter(pk=wo.pk).update(status=WorkOrder.Status.CLOSED)
    wo.refresh_from_db()

    with pytest.raises(InvalidTransition):
        services.close_work_order(wo, membership=p3["sup"], actor=p3["sup"].user, comment="Retry close")
    with pytest.raises(InvalidTransition):
        services.return_for_rework(wo, membership=p3["sup"], actor=p3["sup"].user, comment="Illegal rollback")
    with pytest.raises(InvalidTransition):
        services.review_work_order(wo, membership=p3["sup"], actor=p3["sup"].user, approved=False, notes="Rollback")

    # Legitimately closed order allows idempotent close only (no version bump or extra event)
    wo2 = _advance_to_state(p3, WorkOrder.Status.CLOSED)
    ver_before = wo2.version
    events_before = wo2.events.count()
    approvals_before = wo2.closure_approvals.count()
    res = services.close_work_order(wo2, membership=p3["sup"], actor=p3["sup"].user, comment="Idempotent retry")
    assert res.status == WorkOrder.Status.CLOSED
    res.refresh_from_db()
    assert res.version == ver_before
    assert res.events.count() == events_before
    assert res.closure_approvals.count() == approvals_before
    with pytest.raises(InvalidTransition):
        services.return_for_rework(wo2, membership=p3["sup"], actor=p3["sup"].user, comment="Cannot reopen closed")


def test_reassign_reschedule_and_update_boundaries_across_all_ten_states(p3):
    t_future = timezone.now() + timedelta(days=4)
    for state in ALL_TEN_STATES:
        wo = _advance_to_state(p3, state)

        # update_work_order only allowed in DRAFT and PLANNED
        if state not in (WorkOrder.Status.DRAFT, WorkOrder.Status.PLANNED):
            with pytest.raises(Conflict) as exc_upd:
                services.update_work_order(wo, membership=p3["planner"], actor=p3["planner"].user, priority="HIGH")
            assert exc_upd.value.code == "work_order_locked"

        # reschedule_assigned_work_order only allowed in ASSIGNED
        if state != WorkOrder.Status.ASSIGNED:
            with pytest.raises(Conflict) as exc_resch:
                services.reschedule_assigned_work_order(
                    wo,
                    membership=p3["planner"],
                    actor=p3["planner"].user,
                    scheduled_start=t_future,
                    scheduled_end=t_future + timedelta(hours=2),
                )
            assert exc_resch.value.code == "work_order_not_reschedulable"

        # reassign_work_order only allowed in ASSIGNED, DISPATCHED, ON_HOLD
        if state not in (WorkOrder.Status.ASSIGNED, WorkOrder.Status.DISPATCHED, WorkOrder.Status.ON_HOLD):
            with pytest.raises(Conflict) as exc_reasgn:
                services.reassign_work_order(
                    wo,
                    membership=p3["planner"],
                    actor=p3["planner"].user,
                    assignee_id=p3["tech2"].pk,
                    reason="Invalid state reassign",
                )
            assert exc_reasgn.value.code == "invalid_reassign_status"


# -------------------------------------------------------------------------------------------------
# 3. Direct ORM save() guard against status rollbacks
# -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "from_state,rollback_target",
    [
        (WorkOrder.Status.PLANNED, WorkOrder.Status.DRAFT),
        (WorkOrder.Status.ASSIGNED, WorkOrder.Status.PLANNED),
        (WorkOrder.Status.DISPATCHED, WorkOrder.Status.ASSIGNED),
        (WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.DISPATCHED),
        (WorkOrder.Status.ON_HOLD, WorkOrder.Status.PLANNED),
        (WorkOrder.Status.COMPLETED, WorkOrder.Status.IN_PROGRESS),
        (WorkOrder.Status.SUPERVISOR_REVIEW, WorkOrder.Status.COMPLETED),
        (WorkOrder.Status.CLOSED, WorkOrder.Status.SUPERVISOR_REVIEW),
        (WorkOrder.Status.CLOSED, WorkOrder.Status.DRAFT),
        (WorkOrder.Status.CANCELLED, WorkOrder.Status.DRAFT),
    ],
)
def test_direct_model_save_blocks_status_rollback(p3, from_state, rollback_target):
    wo = _advance_to_state(p3, from_state)
    wo.status = rollback_target
    with pytest.raises(ValidationError, match="workflow transition service"):
        wo.save()
    with pytest.raises(ValidationError, match="workflow transition service"):
        wo.save(update_fields=["status"])
    wo.refresh_from_db()
    assert wo.status == from_state


# -------------------------------------------------------------------------------------------------
# 4. API & Workspace API invalid state / rollback boundary matrix
# -------------------------------------------------------------------------------------------------


def test_api_endpoints_reject_invalid_transitions_and_rollbacks(p3, owner_a, as_user):
    t0 = timezone.now() + timedelta(days=20)
    c_owner = as_user(owner_a, p3["org"])
    c_tech = as_user(p3["tech"].user, p3["org"])

    plan_payload = {
        "work_type": "PREVENTIVE",
        "priority": "MEDIUM",
        "planned_start": t0.isoformat(),
        "planned_end": (t0 + timedelta(hours=2)).isoformat(),
        "due_at": (t0 + timedelta(days=1)).isoformat(),
        "estimated_hours": "1.00",
    }

    endpoints = [
        ("plan", c_owner, plan_payload, {WorkOrder.Status.DRAFT}),
        ("assign", c_owner, {"assigned_to": str(p3["tech2"].pk)}, {WorkOrder.Status.PLANNED}),
        ("dispatch", c_owner, {}, {WorkOrder.Status.ASSIGNED}),
        ("start", c_owner, {}, {WorkOrder.Status.DISPATCHED}),
        ("hold", c_owner, {"reason": "Waiting on tool"}, {WorkOrder.Status.IN_PROGRESS}),
        ("resume", c_owner, {}, {WorkOrder.Status.ON_HOLD}),
        ("complete", c_owner, {"resolution_notes": "Completed API boundary test."}, {WorkOrder.Status.IN_PROGRESS}),
        ("submit-for-review", c_owner, {}, {WorkOrder.Status.COMPLETED}),
        ("return-for-rework", c_owner, {"comment": "Rework needed"}, {WorkOrder.Status.SUPERVISOR_REVIEW}),
        ("close", c_owner, {"comment": "Close approved"}, {WorkOrder.Status.SUPERVISOR_REVIEW, WorkOrder.Status.CLOSED}),
    ]

    for state in ALL_TEN_STATES:
        wo = _advance_to_state(p3, state)
        # PATCH direct status mutation / rollback is always blocked
        r_patch_status = c_owner.patch(
            f"/api/v1/work-orders/{wo.pk}/", {"status": WorkOrder.Status.DRAFT}, format="json"
        )
        assert r_patch_status.status_code == 400
        wo.refresh_from_db()
        assert wo.status == state

        # PATCH non-planning field in PLANNED returns 409; any PATCH after PLANNED returns 409
        if state == WorkOrder.Status.PLANNED:
            r_locked = c_owner.patch(f"/api/v1/work-orders/{wo.pk}/", {"title": "Locked title"}, format="json")
            assert r_locked.status_code == 409
            assert r_locked.json()["error"]["code"] == "planned_fields_locked"
        elif state != WorkOrder.Status.DRAFT:
            r_locked = c_owner.patch(f"/api/v1/work-orders/{wo.pk}/", {"priority": "CRITICAL"}, format="json")
            assert r_locked.status_code == 409
            assert r_locked.json()["error"]["code"] == "work_order_locked"

        # Assigned technician sees 409 on invalid transitions when assigned, 404 when unassigned
        if state in (WorkOrder.Status.ASSIGNED, WorkOrder.Status.DISPATCHED, WorkOrder.Status.ON_HOLD, WorkOrder.Status.SUPERVISOR_REVIEW):
            assert c_tech.post(f"/api/v1/work-orders/{wo.pk}/resume/", {}, format="json").status_code == (
                200 if state == WorkOrder.Status.ON_HOLD else 409
            )
            if state == WorkOrder.Status.ON_HOLD:
                # Re-hold so state stays ON_HOLD for remaining checks below
                wo = services.hold_work_order(wo, membership=p3["tech"], actor=p3["tech"].user, reason="Re-hold")
        elif state in (WorkOrder.Status.DRAFT, WorkOrder.Status.PLANNED, WorkOrder.Status.CANCELLED):
            assert c_tech.post(f"/api/v1/work-orders/{wo.pk}/start/", {}, format="json").status_code == 404

        for slug, client, payload, valid_states in endpoints:
            if state in valid_states:
                continue
            req_payload = dict(payload)
            if slug == "assign":
                req_payload["expected_version"] = wo.version
            ver_before = wo.version
            resp = client.post(f"/api/v1/work-orders/{wo.pk}/{slug}/", req_payload, format="json")
            assert resp.status_code == 409, f"Expected 409 for {slug} from {state}, got {resp.status_code}: {resp.content}"
            wo.refresh_from_db()
            assert wo.status == state
            assert wo.version == ver_before


def test_api_generic_transition_endpoint_rejects_unsupported_and_unauthorized_actions(p3, as_user):
    wo = _advance_to_state(p3, WorkOrder.Status.DISPATCHED)
    c_tech = as_user(p3["tech"].user, p3["org"])
    c_sup = as_user(p3["sup"].user, p3["org"])

    # Unsupported transition names (cancel, rollback, reopen) -> 400
    for bad_action in ("cancel", "rollback", "reopen", "reject_review", ""):
        r = c_sup.post(f"/api/v1/work-orders/{wo.pk}/transition/", {"action": bad_action}, format="json")
        assert r.status_code == 400

    # Technician lacks work_order.assign -> transition?action=reassign must still return 403
    r_unauth = c_tech.post(
        f"/api/v1/work-orders/{wo.pk}/transition/",
        {"action": "reassign", "assigned_to": str(p3["tech2"].pk), "reason": "No perm"},
        format="json",
    )
    assert r_unauth.status_code == 403

    # Invalid state via /transition/ (e.g. close from DISPATCHED) -> 409
    r_inv = c_sup.post(
        f"/api/v1/work-orders/{wo.pk}/transition/",
        {"action": "close", "comment": "Cannot skip states"},
        format="json",
    )
    assert r_inv.status_code == 409
    wo.refresh_from_db()
    assert wo.status == WorkOrder.Status.DISPATCHED


def test_workspace_api_rejects_invalid_state_transitions(p3, as_user):
    c_tech = as_user(p3["tech"].user, p3["org"])

    wo_in_prog = _advance_to_state(p3, WorkOrder.Status.IN_PROGRESS)
    assert c_tech.post(f"/api/v1/workspace/jobs/{wo_in_prog.pk}/start/", {}, format="json").status_code == 409
    assert c_tech.post(f"/api/v1/workspace/jobs/{wo_in_prog.pk}/resume/", {}, format="json").status_code == 409

    wo_hold = _advance_to_state(p3, WorkOrder.Status.ON_HOLD)
    assert c_tech.post(f"/api/v1/workspace/jobs/{wo_hold.pk}/start/", {}, format="json").status_code == 409
    assert c_tech.post(f"/api/v1/workspace/jobs/{wo_hold.pk}/pause/", {"reason": "Already held"}, format="json").status_code == 409
    assert c_tech.post(
        f"/api/v1/workspace/jobs/{wo_hold.pk}/complete/",
        {"resolution_notes": "Cannot complete directly from ON_HOLD"},
        format="json",
    ).status_code == 409

    wo_review = _advance_to_state(p3, WorkOrder.Status.SUPERVISOR_REVIEW)
    for ep, body in (
        ("start", {}),
        ("pause", {"reason": "In review"}),
        ("resume", {}),
        ("complete", {"resolution_notes": "Already submitted for review"}),
    ):
        assert c_tech.post(f"/api/v1/workspace/jobs/{wo_review.pk}/{ep}/", body, format="json").status_code == 409
    wo_review.refresh_from_db()
    assert wo_review.status == WorkOrder.Status.SUPERVISOR_REVIEW

    wo_closed = _advance_to_state(p3, WorkOrder.Status.CLOSED)
    for ep, body in (
        ("start", {}),
        ("pause", {"reason": "Closed"}),
        ("resume", {}),
        ("complete", {"resolution_notes": "Cannot complete closed order"}),
    ):
        assert c_tech.post(f"/api/v1/workspace/jobs/{wo_closed.pk}/{ep}/", body, format="json").status_code == 409


# -------------------------------------------------------------------------------------------------
# 5. Valid bounded loops: multi-hold & supervisor rework -> re-completion -> closure
# -------------------------------------------------------------------------------------------------


def test_bounded_hold_and_supervisor_rework_cycles_preserve_state_and_sync(sla_):
    wo, sr = _make_linked_review_wo(sla_)
    assert wo.status == WorkOrder.Status.SUPERVISOR_REVIEW
    assert sr.status == "RESOLVED"

    # Supervisor returns for rework: SUPERVISOR_REVIEW -> IN_PROGRESS
    wo = services.return_for_rework(
        wo,
        membership=sla_["sup"],
        actor=sla_["sup"].user,
        comment="Recheck discharge gauge calibration.",
    )
    wo.refresh_from_db()
    sr.refresh_from_db()
    assert wo.status == WorkOrder.Status.IN_PROGRESS
    assert sr.status == "IN_SERVICE"
    assert wo.supervisor_notes == "Recheck discharge gauge calibration."
    assert wo.closure_approvals.filter(decision=ClosureApproval.Decision.RETURNED).count() == 1

    # Reworked IN_PROGRESS still cannot roll back to DISPATCHED/DRAFT or be cancelled
    with pytest.raises(InvalidTransition):
        services.cancel_work_order(wo, membership=sla_["planner"], actor=sla_["planner"].user, reason="Too late to cancel")
    with pytest.raises(InvalidTransition):
        services.transition_work_order(
            wo,
            WorkOrder.Status.DISPATCHED,
            membership=sla_["ops"],
            actor=sla_["ops"].user,
            permission="work_order.view",
            action="invalid_rollback",
        )

    # Multiple hold/resume cycles during rework
    wo = services.hold_work_order(wo, membership=sla_["tech"], actor=sla_["tech"].user, reason="Waiting for calibrated gauge")
    assert wo.status == WorkOrder.Status.ON_HOLD
    assert wo.hold_reason == "Waiting for calibrated gauge"

    wo = services.resume_work_order(wo, membership=sla_["tech"], actor=sla_["tech"].user)
    assert wo.status == WorkOrder.Status.IN_PROGRESS
    assert wo.hold_reason == ""

    wo = services.hold_work_order(wo, membership=sla_["tech"], actor=sla_["tech"].user, reason="Second safety lockout")
    assert wo.status == WorkOrder.Status.ON_HOLD
    wo = services.resume_work_order(wo, membership=sla_["tech"], actor=sla_["tech"].user)
    assert wo.status == WorkOrder.Status.IN_PROGRESS

    # Re-complete -> submit_for_review -> close
    wo = services.complete_work_order(
        wo,
        membership=sla_["tech"],
        actor=sla_["tech"].user,
        resolution_notes="Gauge recalibrated and pressure verified within limits.",
    )
    assert wo.status == WorkOrder.Status.COMPLETED
    wo = services.submit_for_review(wo, membership=sla_["tech"], actor=sla_["tech"].user)
    assert wo.status == WorkOrder.Status.SUPERVISOR_REVIEW
    wo = services.close_work_order(
        wo,
        membership=sla_["sup"],
        actor=sla_["sup"].user,
        comment="Rework verified and approved.",
    )
    assert wo.status == WorkOrder.Status.CLOSED
    assert list(wo.closure_approvals.values_list("decision", flat=True)) == [
        ClosureApproval.Decision.RETURNED,
        ClosureApproval.Decision.APPROVED,
    ]
    assert services.allowed_actions(wo, sla_["sup"]) == []
    assert services.allowed_actions(wo, sla_["tech"]) == []


# -------------------------------------------------------------------------------------------------
# 6. Guard boundaries, optimistic locking & atomic rollbacks on downstream failures
# -------------------------------------------------------------------------------------------------


def test_guard_input_length_boundaries_and_stale_expected_version(p3):
    wo = _advance_to_state(p3, WorkOrder.Status.DRAFT)

    # Cancel reason < 3 chars fails; 3 chars succeeds
    with pytest.raises(ValidationFailed) as exc_short:
        services.cancel_work_order(wo, membership=p3["planner"], actor=p3["planner"].user, reason="ab")
    assert exc_short.value.code == "reason_required"
    assert wo.status == WorkOrder.Status.DRAFT

    wo_cancellable = _advance_to_state(p3, WorkOrder.Status.DISPATCHED)
    # Stale expected_version (0, ver-1, ver+1) blocks transition without DB write
    for bad_ver in (0, wo_cancellable.version + 1):
        with pytest.raises(Conflict) as exc_ver:
            services.start_work_order(
                wo_cancellable, membership=p3["tech"], actor=p3["tech"].user, expected_version=bad_ver
            )
        assert exc_ver.value.code == "work_order_version_conflict"
    wo_cancellable.refresh_from_db()
    assert wo_cancellable.status == WorkOrder.Status.DISPATCHED

    # Cancel boundary: 3-char reason succeeds from DISPATCHED
    cancelled = services.cancel_work_order(
        wo_cancellable, membership=p3["planner"], actor=p3["planner"].user, reason="abc"
    )
    assert cancelled.status == WorkOrder.Status.CANCELLED

    # Complete resolution_notes: 9 chars fails, 10 chars passes
    wo_prog = _advance_to_state(p3, WorkOrder.Status.IN_PROGRESS)
    services.record_labor(
        wo_prog,
        membership=p3["tech"],
        actor=p3["tech"].user,
        work_date=timezone.localdate(),
        hours="1.0",
        description="Checked unit",
    )
    _mark_checklist_valid(wo_prog)
    with pytest.raises(ValidationFailed) as exc_notes:
        services.complete_work_order(
            wo_prog, membership=p3["tech"], actor=p3["tech"].user, resolution_notes="123456789"
        )
    assert exc_notes.value.code == "resolution_notes_required"
    wo_prog.refresh_from_db()
    assert wo_prog.status == WorkOrder.Status.IN_PROGRESS

    done = services.complete_work_order(
        wo_prog, membership=p3["tech"], actor=p3["tech"].user, resolution_notes="1234567890"
    )
    assert done.status == WorkOrder.Status.COMPLETED


def test_sla_pause_reason_failure_rolls_back_hold_transition_atomically(p3):
    """A 2-char hold reason passes hold_work_order check but fails SLA pause_reason_required;
    transaction_work_order must atomically roll back WorkOrder.status, hold_reason, version, event, and audit.
    """
    profile = sla_services.create_profile(
        p3["org"],
        name="WO Hold Pause Boundary",
        applies_to="WORK_ORDER",
        actor=p3["ops"].user,
        pause_states=["WORK_ORDER:ON_HOLD"],
    )
    sla_services.set_target(profile, priority="MEDIUM", response_minutes=60, resolution_minutes=240, warning_percent=80, actor=p3["ops"].user)

    wo = _advance_to_state(p3, WorkOrder.Status.IN_PROGRESS)
    assert SLATracking.objects.filter(work_order=wo).exists()
    ver_before = wo.version
    events_before = wo.events.count()
    audits_before = AuditLog.objects.filter(organization=p3["org"], target_id=str(wo.pk)).count()

    with pytest.raises(ValidationFailed) as exc:
        services.hold_work_order(wo, membership=p3["tech"], actor=p3["tech"].user, reason="ab")
    assert exc.value.code == "pause_reason_required"

    wo.refresh_from_db()
    assert wo.status == WorkOrder.Status.IN_PROGRESS
    assert wo.hold_reason == ""
    assert wo.version == ver_before
    assert wo.events.count() == events_before
    assert AuditLog.objects.filter(organization=p3["org"], target_id=str(wo.pk)).count() == audits_before


def test_cancel_with_reserved_parts_rolls_back_inventory_when_state_or_version_invalid(inv_):
    """cancel_work_order calls inventory_services.on_work_order_cancelled before transition_work_order;
    if transition_work_order raises Conflict or InvalidTransition, the part reservation must roll back intact.
    """
    inventory_services.receive(inv_["wh"], inv_["part"], Decimal("5"), actor=inv_["stores"].user, reason="Seed stock")

    # Case A: Cancellable state (PLANNED) but stale expected_version -> reservation remains RESERVED
    wo_planned = _advance_to_state(inv_, WorkOrder.Status.PLANNED)
    line_a = inventory_services.request_part(
        wo_planned, part=inv_["part"], quantity=Decimal("2"), actor=inv_["planner"].user, membership=inv_["planner"]
    )
    inventory_services.reserve(line_a, warehouse=inv_["wh"], quantity=Decimal("2"), actor=inv_["stores"].user)
    line_a.refresh_from_db()
    assert line_a.status == WorkOrderPart.Status.RESERVED

    with pytest.raises(Conflict) as exc_ver:
        services.cancel_work_order(
            wo_planned,
            membership=inv_["planner"],
            actor=inv_["planner"].user,
            reason="Stale version cancel",
            expected_version=wo_planned.version + 5,
        )
    assert exc_ver.value.code == "work_order_version_conflict"
    wo_planned.refresh_from_db()
    line_a.refresh_from_db()
    assert wo_planned.status == WorkOrder.Status.PLANNED
    assert line_a.status == WorkOrderPart.Status.RESERVED

    # Case B: Non-cancellable state (IN_PROGRESS) with reserved (non-issued) parts -> reservation remains RESERVED
    wo_prog = _advance_to_state(inv_, WorkOrder.Status.IN_PROGRESS)
    line_b = inventory_services.request_part(
        wo_prog, part=inv_["part2"], quantity=Decimal("1"), actor=inv_["planner"].user, membership=inv_["planner"]
    )
    inventory_services.receive(inv_["wh"], inv_["part2"], Decimal("3"), actor=inv_["stores"].user, reason="Seed belt")
    inventory_services.reserve(line_b, warehouse=inv_["wh"], quantity=Decimal("1"), actor=inv_["stores"].user)

    with pytest.raises(InvalidTransition):
        services.cancel_work_order(
            wo_prog,
            membership=inv_["planner"],
            actor=inv_["planner"].user,
            reason="Invalid cancel in progress",
        )
    wo_prog.refresh_from_db()
    line_b.refresh_from_db()
    assert wo_prog.status == WorkOrder.Status.IN_PROGRESS
    assert line_b.status == WorkOrderPart.Status.RESERVED


def test_downstream_hook_failures_roll_back_state_transitions_atomically(p3, monkeypatch):
    # 1. assign_work_order rollback if WorkOrderAssignment.save fails
    wo_planned = _advance_to_state(p3, WorkOrder.Status.PLANNED)
    ver_planned = wo_planned.version

    def broken_assignment_save(self, *args, **kwargs):
        raise RuntimeError("Assignment persistence failure")

    monkeypatch.setattr(WorkOrderAssignment, "save", broken_assignment_save)
    with pytest.raises(RuntimeError, match="Assignment persistence failure"):
        services.assign_work_order(
            wo_planned, membership=p3["planner"], actor=p3["planner"].user, assignee_id=p3["tech"].pk
        )
    monkeypatch.undo()
    wo_planned.refresh_from_db()
    assert wo_planned.status == WorkOrder.Status.PLANNED
    assert wo_planned.assigned_to_id is None
    assert wo_planned.version == ver_planned
    assert not WorkOrderAssignment.objects.filter(work_order=wo_planned).exists()
    assert not wo_planned.events.filter(action="assigned").exists()

    # 2. start_work_order rollback if _sync_incident_request fails
    wo_disp = _advance_to_state(p3, WorkOrder.Status.DISPATCHED)
    ver_disp = wo_disp.version
    monkeypatch.setattr(services, "_sync_incident_request", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("Sync fail")))
    with pytest.raises(RuntimeError, match="Sync fail"):
        services.start_work_order(wo_disp, membership=p3["tech"], actor=p3["tech"].user)
    monkeypatch.undo()
    wo_disp.refresh_from_db()
    assert wo_disp.status == WorkOrder.Status.DISPATCHED
    assert wo_disp.started_at is None
    assert wo_disp.version == ver_disp
    assert not wo_disp.events.filter(action="started").exists()

    # 3. complete_work_order rollback if _sync_incident_request fails
    wo_prog = _advance_to_state(p3, WorkOrder.Status.IN_PROGRESS)
    services.record_labor(
        wo_prog, membership=p3["tech"], actor=p3["tech"].user,
        work_date=timezone.localdate(), hours="1.0", description="Labor entry",
    )
    _mark_checklist_valid(wo_prog)
    ver_prog = wo_prog.version
    monkeypatch.setattr(services, "_sync_incident_request", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("Complete sync fail")))
    with pytest.raises(RuntimeError, match="Complete sync fail"):
        services.complete_work_order(
            wo_prog, membership=p3["tech"], actor=p3["tech"].user,
            resolution_notes="Completed work but sync failed",
        )
    monkeypatch.undo()
    wo_prog.refresh_from_db()
    assert wo_prog.status == WorkOrder.Status.IN_PROGRESS
    assert wo_prog.completed_at is None
    assert wo_prog.resolution_notes == ""
    assert wo_prog.version == ver_prog
    assert not wo_prog.events.filter(action="completed").exists()

    # 4. close_work_order & return_for_rework rollback if downstream hook fails
    wo_rev, sr = _make_linked_review_wo(p3)
    ver_rev = wo_rev.version
    monkeypatch.setattr(services, "_sync_incident_request", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("Review sync fail")))
    with pytest.raises(RuntimeError, match="Review sync fail"):
        services.return_for_rework(wo_rev, membership=p3["sup"], actor=p3["sup"].user, comment="Rollback rework")
    monkeypatch.undo()
    wo_rev.refresh_from_db()
    sr.refresh_from_db()
    assert wo_rev.status == WorkOrder.Status.SUPERVISOR_REVIEW
    assert wo_rev.version == ver_rev
    assert not wo_rev.closure_approvals.exists()
    assert sr.status == "RESOLVED"

    monkeypatch.setattr(inventory_services, "on_work_order_closed", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("Inventory close fail")))
    with pytest.raises(RuntimeError, match="Inventory close fail"):
        services.close_work_order(wo_rev, membership=p3["sup"], actor=p3["sup"].user, comment="Close fail")
    monkeypatch.undo()
    wo_rev.refresh_from_db()
    assert wo_rev.status == WorkOrder.Status.SUPERVISOR_REVIEW
    assert wo_rev.closed_at is None
    assert wo_rev.closed_by_id is None
    assert wo_rev.version == ver_rev
    assert not wo_rev.closure_approvals.exists()


def test_workspace_signoff_completion_rolls_back_attachments_on_invalid_state(p3):
    wo_hold = _advance_to_state(p3, WorkOrder.Status.ON_HOLD)
    services.record_labor(
        wo_hold,
        membership=p3["tech"],
        actor=p3["tech"].user,
        work_date=timezone.localdate(),
        hours="1.0",
        description="Labor before hold",
    )
    sig_file = SimpleUploadedFile("sig.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, content_type="image/png")
    photo_file = SimpleUploadedFile("final.jpg", b"\xff\xd8\xff\xe0" + b"0" * 64, content_type="image/jpeg")

    with pytest.raises(InvalidTransition):
        workspace_services.complete_job_with_signoff(
            wo_hold,
            resolution_notes="Attempted completion from ON_HOLD with signoff",
            signer_name="Jane Client",
            signature_file=sig_file,
            final_photo_file=photo_file,
            membership=p3["tech"],
            actor=p3["tech"].user,
        )

    wo_hold.refresh_from_db()
    assert wo_hold.status == WorkOrder.Status.ON_HOLD
    assert not WorkOrderSignoff.objects.filter(work_order=wo_hold).exists()
    assert not wo_hold.evidence_links.exists()
