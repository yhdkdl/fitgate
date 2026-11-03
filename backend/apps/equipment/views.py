from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import FitGateJWTAuthentication
from apps.accounts.models import User
from apps.accounts.permissions import RequirePasswordChanged
from apps.accounts.services import record_audit_log
from apps.equipment.models import Equipment
from apps.equipment.permissions import (
    CanManageEquipment,
    CanReportEquipmentIssue,
    CanViewEquipment,
)
from apps.equipment.serializers import (
    EquipmentCreateUpdateSerializer,
    EquipmentSerializer,
    MaintenanceLogSerializer,
    ReportIssueSerializer,
    UpdateConditionSerializer,
)
from apps.equipment.services import report_equipment_issue, update_equipment_condition


class EquipmentListCreateView(APIView):
    authentication_classes = [FitGateJWTAuthentication]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), RequirePasswordChanged(), CanManageEquipment()]
        return [IsAuthenticated(), RequirePasswordChanged(), CanViewEquipment()]

    @extend_schema(
        tags=["equipment"],
        summary="List gym equipment",
        responses={200: EquipmentSerializer(many=True)},
    )
    def get(self, request):
        tenant = request.tenant
        if not tenant:
            raise PermissionDenied("Tenant context required.")

        qs = Equipment.all_objects.filter(gym=tenant).prefetch_related(
            "maintenance_logs"
        )

        # Member visibility check
        if request.user.role == User.ROLE_MEMBER:
            config = getattr(tenant, "config", None)
            show_unavailable = config and config.show_unavailable_equipment
            if not show_unavailable:
                qs = qs.filter(
                    condition__in=[
                        Equipment.CONDITION_GOOD,
                        Equipment.CONDITION_NEEDS_MAINTENANCE,
                    ],
                    quantity__gt=0,
                )

        serializer = EquipmentSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["equipment"],
        summary="Create gym equipment",
        request=EquipmentCreateUpdateSerializer,
        responses={201: EquipmentSerializer},
    )
    def post(self, request):
        tenant = request.tenant
        if not tenant:
            raise PermissionDenied("Tenant context required.")

        serializer = EquipmentCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        equipment = Equipment(gym=tenant, **serializer.validated_data)
        equipment.save()

        record_audit_log(
            actor=request.user,
            action_type="equipment_created",
            affected_record_type="Equipment",
            affected_record_id=str(equipment.id),
            gym=tenant,
            metadata={
                "name": equipment.name,
                "category": equipment.category,
                "quantity": equipment.quantity,
                "condition": equipment.condition,
            },
        )

        return Response(
            EquipmentSerializer(equipment).data, status=status.HTTP_201_CREATED
        )


class EquipmentDetailView(APIView):
    authentication_classes = [FitGateJWTAuthentication]

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated(), RequirePasswordChanged(), CanViewEquipment()]
        return [IsAuthenticated(), RequirePasswordChanged(), CanManageEquipment()]

    def _get_equipment(self, request, pk) -> Equipment:
        tenant = request.tenant
        if not tenant:
            raise PermissionDenied("Tenant context required.")

        item = Equipment.all_objects.filter(id=pk, gym=tenant).first()
        if not item:
            raise NotFound({"detail": "Equipment item not found."})

        if request.user.role == User.ROLE_MEMBER:
            config = getattr(tenant, "config", None)
            show_unavailable = config and config.show_unavailable_equipment
            if not show_unavailable and (
                item.condition
                in [
                    Equipment.CONDITION_UNDER_MAINTENANCE,
                    Equipment.CONDITION_OUT_OF_SERVICE,
                ]
                or item.quantity == 0
            ):
                raise NotFound({"detail": "Equipment item not found."})

        return item

    @extend_schema(
        tags=["equipment"],
        summary="Retrieve equipment item",
        responses={200: EquipmentSerializer},
    )
    def get(self, request, pk):
        item = self._get_equipment(request, pk)
        return Response(EquipmentSerializer(item).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["equipment"],
        summary="Update equipment item",
        request=EquipmentCreateUpdateSerializer,
        responses={200: EquipmentSerializer},
    )
    def put(self, request, pk):
        return self.patch(request, pk)

    def patch(self, request, pk):
        item = self._get_equipment(request, pk)
        serializer = EquipmentCreateUpdateSerializer(
            item, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()

        record_audit_log(
            actor=request.user,
            action_type="equipment_updated",
            affected_record_type="Equipment",
            affected_record_id=str(item.id),
            gym=request.tenant,
            metadata={"updated_fields": list(serializer.validated_data.keys())},
        )

        return Response(EquipmentSerializer(item).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["equipment"],
        summary="Delete equipment item",
        responses={204: None},
    )
    def delete(self, request, pk):
        item = self._get_equipment(request, pk)
        name = item.name
        item.delete()

        record_audit_log(
            actor=request.user,
            action_type="equipment_deleted",
            affected_record_type="Equipment",
            affected_record_id=str(pk),
            gym=request.tenant,
            metadata={"name": name},
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class EquipmentReportIssueView(APIView):
    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        CanReportEquipmentIssue,
    ]

    @extend_schema(
        tags=["equipment"],
        summary="Report an issue on equipment",
        request=ReportIssueSerializer,
        responses={201: MaintenanceLogSerializer},
    )
    def put(self, request, pk):
        return self.patch(request, pk)

    def patch(self, request, pk):
        return self.post(request, pk)

    def post(self, request, pk):
        tenant = request.tenant
        if not tenant:
            raise PermissionDenied("Tenant context required.")

        item = Equipment.all_objects.filter(id=pk, gym=tenant).first()
        if not item:
            raise NotFound({"detail": "Equipment item not found."})

        serializer = ReportIssueSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            log = report_equipment_issue(
                equipment=item,
                acting_user=request.user,
                issue_reason=serializer.validated_data["issue_reason"],
                other_details=serializer.validated_data.get("other_details", ""),
            )
            return Response(
                MaintenanceLogSerializer(log).data, status=status.HTTP_201_CREATED
            )
        except (DjangoValidationError, DRFValidationError) as exc:
            detail = getattr(
                exc,
                "detail",
                getattr(exc, "message", getattr(exc, "messages", str(exc))),
            )
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)


class EquipmentUpdateConditionView(APIView):
    authentication_classes = [FitGateJWTAuthentication]
    permission_classes = [IsAuthenticated, RequirePasswordChanged, CanManageEquipment]

    @extend_schema(
        tags=["equipment"],
        summary="Update condition and log resolution",
        request=UpdateConditionSerializer,
        responses={200: EquipmentSerializer},
    )
    def put(self, request, pk):
        return self.patch(request, pk)

    def patch(self, request, pk):
        return self.post(request, pk)

    def post(self, request, pk):
        tenant = request.tenant
        if not tenant:
            raise PermissionDenied("Tenant context required.")

        item = Equipment.all_objects.filter(id=pk, gym=tenant).first()
        if not item:
            raise NotFound({"detail": "Equipment item not found."})

        serializer = UpdateConditionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated = update_equipment_condition(
                equipment=item,
                new_condition=serializer.validated_data["condition"],
                acting_user=request.user,
                resolution_notes=serializer.validated_data.get("resolution_notes", ""),
            )
            return Response(
                EquipmentSerializer(updated).data, status=status.HTTP_200_OK
            )
        except (DjangoValidationError, DRFValidationError) as exc:
            detail = getattr(
                exc,
                "detail",
                getattr(exc, "message", getattr(exc, "messages", str(exc))),
            )
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
