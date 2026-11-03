from django.urls import path

from apps.equipment.views import (
    EquipmentDetailView,
    EquipmentListCreateView,
    EquipmentReportIssueView,
    EquipmentUpdateConditionView,
)

urlpatterns = [
    path("equipment/", EquipmentListCreateView.as_view(), name="equipment-list-create"),
    path(
        "equipment/<uuid:pk>/", EquipmentDetailView.as_view(), name="equipment-detail"
    ),
    path(
        "equipment/<uuid:pk>/report-issue/",
        EquipmentReportIssueView.as_view(),
        name="equipment-report-issue",
    ),
    path(
        "equipment/<uuid:pk>/update-condition/",
        EquipmentUpdateConditionView.as_view(),
        name="equipment-update-condition",
    ),
    path(
        "equipment/<uuid:pk>/condition/",
        EquipmentUpdateConditionView.as_view(),
        name="equipment-condition",
    ),
]
