from uuid import UUID

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.api import StandardPagination
from apps.core.exceptions import ValidationFailed
from apps.rbac import services as rbac
from apps.sites.models import Site
from apps.tenancy.api import TenantAPIMixin

from . import services
from .models import WorkOrder
from .serializers import (
    AssignSerializer,
    ChecklistReferenceSerializer,
    ClosureCommentSerializer,
    CreateWorkOrderSerializer,
    WorkOrderCompleteSerializer,
    EvidenceSerializer,
    ExpectedVersionSerializer,
    LaborInputSerializer,
    MaterialInputSerializer,
    PlanSerializer,
    ReassignSerializer,
    ProvisionalChecklistSerializer,
    ReviewSerializer,
    UpdateWorkOrderSerializer,
    WorkNoteSerializer,
    WorkOrderEventSerializer,
    WorkOrderReasonSerializer,
    WorkOrderSerializer,
)


class WorkOrderViewSet(TenantAPIMixin, viewsets.GenericViewSet):
    queryset = WorkOrder.objects.none()
    pagination_class = StandardPagination
    permission_map = {
        "list": "work_order.view_assigned",
        "retrieve": "work_order.view_assigned",
        "events": "work_order.view_assigned",
        "checklist_status": "work_order.view_assigned",
        "create": "work_order.create", "partial_update": "work_order.update",
        "plan": "work_order.plan", "assign": "work_order.assign", "reassign": "work_order.assign", "reassign": "work_order.assign",
        "dispatch_order": "work_order.dispatch", "start": "work_order.start", "hold": "work_order.hold",
        "resume": "work_order.start", "complete": "work_order.complete",
        "validate_checklist": "work_order.complete",
        "submit_for_review": "work_order.complete", "review": "work_order.review",
        "close": "work_order.close", "return_for_rework": "work_order.review",
        "provisional_checklist": "work_order.update", "checklist_reference": "work_order.update", "labor": "work_order.record",
        "materials": "work_order.record", "evidence": "work_order.attach", "notes": "work_order.record",
        "transition": "work_order.view_assigned",
        "closure": "work_order.view_assigned",
    }

    def get_required_permission(self):
        action = getattr(self, "action", None)
        if action == "list":
            return "work_order.view_assigned"
        if action == "transition":
            sub = getattr(self.request, "data", {}).get("action")
            return {"complete": "work_order.complete", "start": "work_order.start",
                    "hold": "work_order.hold", "resume": "work_order.start",
                    "plan": "work_order.plan", "assign": "work_order.assign",
                    "dispatch": "work_order.dispatch", "submit_for_review": "work_order.complete",
                    "close": "work_order.close", "return_for_rework": "work_order.review"}.get(sub, "work_order.view_assigned")
        if (action in ("retrieve", "events", "checklist_status", "validate_checklist", "closure") or (action == "materials" and self.request.method == "GET")):
            m = getattr(self.request, "membership", None)
            if m and rbac.has_permission_anywhere(m, "work_order.view"):
                return "work_order.view"
            return "work_order.view_assigned"
        return super().get_required_permission()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return WorkOrder.objects.none()
        m = self.request.membership
        if not m:
            return WorkOrder.objects.none()
        qs = WorkOrder.objects.for_organization(m.organization).select_related("site", "assigned_to__user", "created_by")
        if not rbac.has_permission_anywhere(m, "work_order.view"):
            qs = qs.filter(assigned_to=m)
        site_ids = [site.pk for site in Site.objects.for_organization(m.organization)
                    if rbac.has_permission(m, "work_order.view", site) or
                    rbac.has_permission(m, "work_order.view_assigned", site)]
        return qs.filter(site_id__in=site_ids)

    def get_serializer_class(self):
        if self.action == "create":
            return CreateWorkOrderSerializer
        if self.action == "partial_update":
            return UpdateWorkOrderSerializer
        if self.action == "plan":
            return PlanSerializer
        if self.action == "assign":
            return AssignSerializer
        if self.action == "reassign":
            return ReassignSerializer
        if self.action == "hold":
            return WorkOrderReasonSerializer
        if self.action in ("close", "return_for_rework"):
            return ClosureCommentSerializer
        if self.action == "notes":
            return WorkNoteSerializer
        if self.action == "complete":
            return WorkOrderCompleteSerializer
        if self.action == "review":
            return ReviewSerializer
        if self.action == "labor":
            return LaborInputSerializer
        if self.action == "materials":
            return MaterialInputSerializer
        if self.action == "provisional_checklist":
            return ProvisionalChecklistSerializer
        if self.action == "evidence":
            return EvidenceSerializer
        return WorkOrderSerializer

    @extend_schema(parameters=[
        OpenApiParameter("status", OpenApiTypes.STR, enum=[key for key, _ in WorkOrder.Status.choices]),
        OpenApiParameter("priority", OpenApiTypes.STR, enum=[key for key, _ in WorkOrder.Priority.choices]),
        OpenApiParameter("site", OpenApiTypes.UUID),
        OpenApiParameter("assignee", OpenApiTypes.UUID, description="Technician membership id"),
        OpenApiParameter("work_type", OpenApiTypes.STR, enum=[key for key, _ in WorkOrder.WorkType.choices]),
        OpenApiParameter("source", OpenApiTypes.STR, enum=[key for key, _ in WorkOrder.SourceType.distinct_choices()]),
        OpenApiParameter("overdue", OpenApiTypes.BOOL),
        OpenApiParameter("q", OpenApiTypes.STR, description="Search number, title, asset, or source reference"),
        OpenApiParameter("ordering", OpenApiTypes.STR, description="Allowed ordering: created_at, due_at, priority, planned_start, order_number; prefix with - for descending"),
    ])
    def list(self, request):
        qs = self.get_queryset()
        state = request.query_params.get("status")
        if state:
            if state not in dict(WorkOrder.Status.choices):
                raise ValidationFailed(f"Invalid status '{state}'.", code="invalid_filter")
            qs = qs.filter(status=state)
        priority = request.query_params.get("priority")
        if priority:
            if priority not in dict(WorkOrder.Priority.choices):
                raise ValidationFailed(f"Invalid priority '{priority}'.", code="invalid_filter")
            qs = qs.filter(priority=priority)
        work_type = request.query_params.get("work_type")
        if work_type in dict(WorkOrder.WorkType.choices):
            qs = qs.filter(work_type=work_type)
        source_type = request.query_params.get("source")
        if source_type in dict(WorkOrder.SourceType.choices):
            qs = qs.filter(source_type=source_type)
        site_id = request.query_params.get("site")
        if site_id:
            try:
                qs = qs.filter(site_id=UUID(site_id))
            except (ValueError, TypeError):
                return Response({"site": ["Enter a valid site id."]}, status=status.HTTP_400_BAD_REQUEST)
        assignee_id = request.query_params.get("assignee")
        if assignee_id:
            try:
                qs = qs.filter(assigned_to_id=UUID(assignee_id))
            except (ValueError, TypeError):
                return Response({"assignee": ["Enter a valid membership id."]}, status=status.HTTP_400_BAD_REQUEST)
        if request.query_params.get("overdue") in ("1", "true", "yes"):
            qs = qs.filter(due_at__lt=timezone.now()).exclude(
                status__in=[WorkOrder.Status.CLOSED, WorkOrder.Status.CANCELLED])
        search = request.query_params.get("q", "").strip()
        if search:
            qs = qs.filter(Q(order_number__icontains=search) | Q(title__icontains=search)
                           | Q(asset_reference__icontains=search) | Q(source_reference__icontains=search))
        ordering = request.query_params.get("ordering", "-created_at")
        allowed_ordering = {"created_at", "-created_at", "due_at", "-due_at", "priority", "-priority",
                            "planned_start", "-planned_start", "order_number", "-order_number"}
        if ordering in allowed_ordering:
            qs = qs.order_by(ordering)
        page = self.paginate_queryset(qs.distinct())
        return self.get_paginated_response(WorkOrderSerializer(page, many=True).data)

    @extend_schema(request=UpdateWorkOrderSerializer, responses={200: WorkOrderSerializer})
    def partial_update(self, request, pk=None):
        wo = self.get_object()
        serializer = self.get_serializer(wo, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = services.update_work_order(wo, membership=request.membership, actor=request.user,
                                             request=request, **serializer.validated_data)
        return Response(WorkOrderSerializer(updated).data)

    @extend_schema(responses={200: WorkOrderSerializer})
    def retrieve(self, request, pk=None):
        wo = self.get_object()
        return Response(WorkOrderSerializer(wo).data)

    @extend_schema(request=CreateWorkOrderSerializer, responses={201: WorkOrderSerializer})
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        site = data.pop("site")
        asset = data.pop("asset")
        component = data.pop("component", None)
        source_type = data.pop("source_type")
        source_request = data.pop("source_request", None)
        if source_request is not None:
            from apps.incidents import services as incident_services
            wo = incident_services.create_work_order_for_request(
                source_request, actor=request.user, membership=request.membership, request=request,
                component=component, **data)
        else:
            data.pop("source_reference", None)
            wo = services.create_work_order(request.organization, site_id=site.pk, asset=asset,
                component=component, source_type=source_type, source_reference="",
                actor=request.user, membership=request.membership, request=request, **data)
        return Response(WorkOrderSerializer(wo).data, status=status.HTTP_201_CREATED)

    def _action(self, pk, fn, serializer=None):
        wo = self.get_object()
        data = {}
        input_serializer = serializer or ExpectedVersionSerializer
        s = input_serializer(data=self.request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        result = fn(wo, membership=self.request.membership, actor=self.request.user, request=self.request, **data)
        if isinstance(result, WorkOrder):
            return Response(WorkOrderSerializer(result).data)
        return Response({"id": str(result.pk), "work_order": str(wo.pk)}, status=status.HTTP_201_CREATED)

    @extend_schema(request=PlanSerializer, responses={200: WorkOrderSerializer})
    @action(detail=True, methods=["post"])
    def plan(self, request, pk=None):
        return self._action(pk, services.plan_work_order, PlanSerializer)

    @extend_schema(request=AssignSerializer, responses={200: WorkOrderSerializer})
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        return self._action(pk, lambda wo, **kw: services.assign_work_order(
            wo, assignee_id=kw.pop("assigned_to"), **kw), AssignSerializer)

    @extend_schema(request=ReassignSerializer, responses={200: WorkOrderSerializer})
    @action(detail=True, methods=["post"])
    def reassign(self, request, pk=None):
        return self._action(
            pk,
            lambda wo, **kw: services.reassign_work_order(
                wo,
                assignee_id=kw.pop("assigned_to", None) or kw.pop("technician", None),
                **kw,
            ),
            ReassignSerializer,
        )

    @extend_schema(request=ExpectedVersionSerializer, responses={200: WorkOrderSerializer})
    @action(detail=True, methods=["post"], url_path="dispatch")
    def dispatch_order(self, request, pk=None):
        return self._action(pk, services.dispatch_work_order)

    @extend_schema(request=ExpectedVersionSerializer, responses={200: WorkOrderSerializer})
    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        return self._action(pk, services.start_work_order)

    @extend_schema(request=WorkOrderReasonSerializer, responses={200: WorkOrderSerializer})
    @action(detail=True, methods=["post"])
    def hold(self, request, pk=None):
        return self._action(pk, services.hold_work_order, WorkOrderReasonSerializer)

    @extend_schema(request=ExpectedVersionSerializer, responses={200: WorkOrderSerializer})
    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        return self._action(pk, services.resume_work_order)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        act = request.data.get("action")
        clean_data = {k: v for k, v in request.data.items() if k != "action"}
        request._full_data = clean_data
        handler_map = {
            "complete": self.complete,
            "start": self.start,
            "hold": self.hold,
            "resume": self.resume,
            "plan": self.plan,
            "assign": self.assign, "reassign": self.reassign,
            "dispatch": self.dispatch_order,
            "submit_for_review": self.submit_for_review,
            "close": self.close,
            "return_for_rework": self.return_for_rework,
        }
        handler = handler_map.get(act)
        if not handler:
            raise ValidationFailed(f"Unsupported transition action: {act}")
        return handler(request, pk=pk)

    @extend_schema(request=WorkOrderCompleteSerializer, responses={200: WorkOrderSerializer},
                   description="IN_PROGRESS -> COMPLETED. Saves resolution notes after M08 checklist validation and work-type evidence requirements pass.")
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return self._action(pk, services.complete_work_order, WorkOrderCompleteSerializer)

    @extend_schema(request=ExpectedVersionSerializer, responses={200: WorkOrderSerializer},
                   description="Assigned technician only: COMPLETED -> SUPERVISOR_REVIEW after checklist, notes, and evidence validation.")
    @action(detail=True, methods=["post"], url_path="submit-for-review")
    def submit_for_review(self, request, pk=None):
        return self._action(pk, services.submit_for_review)

    @extend_schema(request=ReviewSerializer, responses={200: WorkOrderSerializer},
                   description="Compatibility decision endpoint; approved=true closes, false returns SUPERVISOR_REVIEW to IN_PROGRESS.")
    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        """Compatibility decision endpoint; approved=true closes, false returns SUPERVISOR_REVIEW to IN_PROGRESS.

        New clients should call /close/ or /return-for-rework/ explicitly. All decisions share review_work_order().
        """
        return self._action(pk, services.review_work_order, ReviewSerializer)

    @extend_schema(request=ClosureCommentSerializer,
        description="Approve a SUPERVISOR_REVIEW work order and close it. Safe to retry; repeated close returns the existing closed record.",
        responses={200: WorkOrderSerializer})
    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        return self._action(pk, services.close_work_order, ClosureCommentSerializer)

    @extend_schema(request=ClosureCommentSerializer,
        description="Return a SUPERVISOR_REVIEW work order to IN_PROGRESS with a required rework comment.",
        responses={200: WorkOrderSerializer})
    @action(detail=True, methods=["post"], url_path="return-for-rework")
    def return_for_rework(self, request, pk=None):
        return self._action(pk, services.return_for_rework, ClosureCommentSerializer)

    @extend_schema(request=WorkNoteSerializer, responses={200: WorkOrderSerializer},
                   description="Append a technician progress note to the work-order event history.")
    @action(detail=True, methods=["post"])
    def notes(self, request, pk=None):
        return self._action(pk, lambda wo, **kw: services.record_work_update(
            wo, update=kw.pop("text"), **kw), WorkNoteSerializer)

    @extend_schema(exclude=True)
    @action(detail=True, methods=["post"], url_path="provisional-checklist")
    def provisional_checklist(self, request, pk=None):
        return self._action(pk, lambda wo, **kw: services.set_checklist(wo, items=kw.pop("items"), **kw),
                            ProvisionalChecklistSerializer)

    @extend_schema(request=ChecklistReferenceSerializer, responses={200: WorkOrderSerializer},
                   description="Register opaque M08 template and instance references. This leaves checklist status pending; it does not mark checklist completion.")
    @action(detail=True, methods=["post"], url_path="checklist-reference")
    def checklist_reference(self, request, pk=None):
        return self._action(pk, services.register_checklist_reference, ChecklistReferenceSerializer)

    @extend_schema(responses={200: dict}, description="Return M08 checklist references and validation state. This endpoint is read-only.")
    @action(detail=True, methods=["get"], url_path="checklist-status")
    def checklist_status(self, request, pk=None):
        wo = self.get_object()
        from .checklist_adapter import get_checklist_summary
        return Response(get_checklist_summary(wo))

    @extend_schema(responses={200: dict, 409: dict},
                   description="Evaluate the local adapter contract without contacting M08. Returns valid or pending metadata; it never creates checklist answers.")
    @action(detail=True, methods=["post"], url_path="validate-checklist")
    def validate_checklist(self, request, pk=None):
        wo = self.get_object()
        from .checklist_adapter import get_checklist_status, get_checklist_summary
        result = get_checklist_status(wo)
        return Response(get_checklist_summary(wo),
            status=status.HTTP_200_OK if result.is_valid else status.HTTP_409_CONFLICT)

    @extend_schema(
        request=LaborInputSerializer,
        responses={201: inline_serializer("WorkOrderLaborRecordResponse", fields={"id": serializers.CharField(), "work_order": serializers.CharField()})},
        description="Record technician labor hours."
    )
    @action(detail=True, methods=["post"])
    def labor(self, request, pk=None):
        return self._action(pk, services.record_labor, LaborInputSerializer)

    @extend_schema(
        request=MaterialInputSerializer,
        responses={201: inline_serializer("WorkOrderMaterialRecordResponse", fields={"id": serializers.CharField(), "work_order": serializers.CharField()})},
        description="Record parts/materials used."
    )
    @action(detail=True, methods=["get", "post"])
    def materials(self, request, pk=None):
        if request.method == "GET":
            wo = self.get_object()
            from .serializers import MaterialSerializer
            qs = wo.material_entries.all().order_by("-created_at")
            page = self.paginate_queryset(qs)
            if page is not None:
                serializer = MaterialSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = MaterialSerializer(qs, many=True)
            return Response(serializer.data)
        return self._action(pk, services.record_material, MaterialInputSerializer)

    @extend_schema(
        request=EvidenceSerializer,
        responses={201: inline_serializer("WorkOrderEvidenceRecordResponse", fields={"id": serializers.CharField(), "work_order": serializers.CharField()})},
        description="Attach completion evidence."
    )
    @action(detail=True, methods=["post"])
    def evidence(self, request, pk=None):
        return self._action(pk, services.add_evidence, EvidenceSerializer)

    @extend_schema(responses={200: WorkOrderEventSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        wo = self.get_object()
        return Response(WorkOrderEventSerializer(wo.events.all(), many=True).data)

    @action(detail=True, methods=["get"])
    def closure(self, request, pk=None):
        wo = self.get_object()
        blockers = services.closure_blockers(wo)
        return Response({"blockers": blockers})

