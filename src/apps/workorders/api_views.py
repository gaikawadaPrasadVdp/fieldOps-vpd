"""Canonical consolidation module (PRD Compliance Directive Gap C).
WorkOrderViewSet is canonically implemented in ``apps.workorders.views``.
This module re-exports the canonical viewset and serializers to guarantee 100% backward compatibility
across legacy imports, external clients, and test harnesses.
"""
from apps.workorders.serializers import (
    AssignSerializer,
    ClosureApprovalSerializer,
    CreateWorkOrderSerializer as WorkOrderWriteSerializer,
    EvidenceSerializer as WorkOrderEvidenceSerializer,
    ExpectedVersionSerializer,
    LaborInputSerializer as LaborWriteSerializer,
    LaborSerializer,
    MaterialInputSerializer as MaterialWriteSerializer,
    MaterialSerializer,
    PlanSerializer,
    ReassignSerializer,
    ReviewSerializer,
    UpdateWorkOrderSerializer as WorkOrderPatchSerializer,
    WorkNoteSerializer,
    WorkOrderCompleteSerializer,
    WorkOrderEventSerializer as EventSerializer,
    WorkOrderReasonSerializer,
    WorkOrderSerializer,
)
from apps.workorders.views import WorkOrderViewSet

__all__ = [
    "WorkOrderViewSet",
    "WorkOrderSerializer",
    "WorkOrderWriteSerializer",
    "WorkOrderPatchSerializer",
    "PlanSerializer",
    "AssignSerializer",
    "ReassignSerializer",
    "WorkOrderReasonSerializer",
    "WorkOrderCompleteSerializer",
    "LaborSerializer",
    "LaborWriteSerializer",
    "MaterialSerializer",
    "MaterialWriteSerializer",
    "EventSerializer",
    "WorkOrderEvidenceSerializer",
    "ClosureApprovalSerializer",
    "ExpectedVersionSerializer",
    "ReviewSerializer",
    "WorkNoteSerializer",
]
