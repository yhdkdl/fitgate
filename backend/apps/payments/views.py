"""API Views for Gym Payment Configuration, Chapa Checkout, Webhook processing, and Admin status."""

import logging
import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import (
    IsGymOwner,
    IsSuperAdmin,
    RequirePasswordChanged,
)
from apps.accounts.services import record_audit_log
from apps.memberships.models import Member, MembershipPlan
from apps.payments.chapa_client import ChapaAPIError, ChapaClient
from apps.payments.models import GymPaymentConfig, Payment, Receipt
from apps.payments.serializers import (
    ChapaCheckoutRequestSerializer,
    ChapaCheckoutResponseSerializer,
    GymPaymentConfigSerializer,
    GymPaymentConfigUpdateSerializer,
    MemberPaymentHistoryItemSerializer,
    ReceiptSerializer,
    ReconcileBankTransfersSerializer,
    RecordBankTransferPaymentRequestSerializer,
    RecordBankTransferResponseSerializer,
    RecordCashPaymentRequestSerializer,
    RecordCashPaymentResponseSerializer,
    ReverseBankTransferSerializer,
    SuperAdminGymPaymentStatusSerializer,
    UnreconciledBankTransferItemSerializer,
)
from apps.payments.services import (
    process_chapa_webhook,
    reconcile_bank_transfers,
    record_bank_transfer_payment,
    record_cash_payment,
    reverse_bank_transfer_payment,
)
from apps.tenants.models import GymTenant

logger = logging.getLogger(__name__)


class CanInitiateCheckout(BasePermission):
    """
    Online checkout can be initiated by members only (for themselves).
    Owner, Manager, Reception, Trainer, and Super Admin are denied.
    Staff take payments from members through the cash flow in Sprint 12.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role == User.ROLE_MEMBER


class GymPaymentConfigView(APIView):
    """
    Manage payment gateway credentials for the active gym.
    Restricted strictly to the Gym Owner of the active tenant.
    Super Admins, Managers, Receptionists, and Members are blocked.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsGymOwner]
    serializer_class = GymPaymentConfigSerializer

    @extend_schema(
        summary="Retrieve gym payment gateway configuration (masked)",
        description="Returns masked configuration state. Plaintext secrets are never returned.",
        responses={200: GymPaymentConfigSerializer},
    )
    def get(self, request):
        gym = request.tenant
        config, _ = GymPaymentConfig.objects.get_or_create(gym=gym)
        serializer = GymPaymentConfigSerializer(config)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Update gym payment credentials",
        description="Encrypts keys at rest using TENANT_CREDENTIALS_KEY and records an audit log.",
        request=GymPaymentConfigUpdateSerializer,
        responses={200: GymPaymentConfigSerializer},
    )
    def patch(self, request):
        return self.put(request)

    def put(self, request):
        gym = request.tenant
        config, _ = GymPaymentConfig.objects.get_or_create(gym=gym)
        serializer = GymPaymentConfigUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        updated = False
        if "public_key" in data:
            config.public_key = data["public_key"]
            updated = True
        if "secret_key" in data:
            config.secret_key = data["secret_key"]
            config.is_verified = False  # requires re-verification
            config.verified_at = None
            updated = True
        if "webhook_secret" in data:
            config.webhook_secret = data["webhook_secret"]
            updated = True

        if updated:
            config.save()
            record_audit_log(
                actor=request.user,
                gym=gym,
                action_type="payment_config_updated",
                affected_record_type="GymPaymentConfig",
                affected_record_id=str(config.id),
                metadata={
                    "is_test_mode": config.is_test_mode,
                    "masked_public_key": config.masked_public_key,
                },
            )

        resp_serializer = GymPaymentConfigSerializer(config)
        return Response(resp_serializer.data, status=status.HTTP_200_OK)


class GymPaymentConfigTestView(APIView):
    """
    Test Chapa connection and verify credentials.
    Restricted strictly to the Gym Owner.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsGymOwner]

    @extend_schema(
        summary="Test Chapa payment credentials",
        description="Performs an external verification call against Chapa API. Sets is_verified flag.",
        responses={
            200: OpenApiResponse(description="Connection verified successfully"),
            400: OpenApiResponse(description="Connection verification failed"),
        },
    )
    def post(self, request):
        gym = request.tenant
        config = GymPaymentConfig.objects.filter(gym=gym).first()
        if not config or not config.is_configured:
            return Response(
                {"detail": "Payment credentials are not fully configured."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = ChapaClient(secret_key=config.secret_key)
        success, message = client.test_connection()

        if success:
            config.is_verified = True
            config.verified_at = timezone.now()
            config.save(update_fields=["is_verified", "verified_at", "updated_at"])

            record_audit_log(
                actor=request.user,
                gym=gym,
                action_type="payment_config_tested",
                affected_record_type="GymPaymentConfig",
                affected_record_id=str(config.id),
                metadata={
                    "result": "success",
                    "is_test_mode": config.is_test_mode,
                },
            )
            return Response(
                {"success": True, "message": message, "is_verified": True},
                status=status.HTTP_200_OK,
            )
        else:
            record_audit_log(
                actor=request.user,
                gym=gym,
                action_type="payment_config_tested",
                affected_record_type="GymPaymentConfig",
                affected_record_id=str(config.id),
                metadata={
                    "result": "failed",
                    "error_summary": message,
                },
            )
            return Response(
                {"success": False, "message": message, "is_verified": False},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ChapaCheckoutView(APIView):
    """
    Initiate an online Chapa checkout session for a membership plan.
    Requires verified gym credentials; otherwise refuses and prompts front-desk cash payment.
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        CanInitiateCheckout,
    ]
    serializer_class = ChapaCheckoutRequestSerializer

    @extend_schema(
        summary="Initiate online Chapa checkout session",
        request=ChapaCheckoutRequestSerializer,
        responses={
            200: ChapaCheckoutResponseSerializer,
            400: OpenApiResponse(description="Online payment disabled or invalid plan"),
            502: OpenApiResponse(description="Payment gateway initialization failed"),
        },
    )
    def post(self, request):
        gym = request.tenant
        if not gym:
            return Response(
                {"detail": "Checkout must be initiated on a gym tenant domain."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ChapaCheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan_id = serializer.validated_data["plan_id"]

        config = GymPaymentConfig.objects.filter(gym=gym).first()
        if not config or not config.is_configured or not config.is_verified:
            return Response(
                {
                    "detail": "Online payment is not enabled for this gym. Please pay at the front desk."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve member strictly from logged-in member account
        member = Member.all_objects.filter(user=request.user, gym=gym).first()
        if not member:
            return Response(
                {"detail": "Member record not found for this gym."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve and validate plan
        plan = MembershipPlan.all_objects.filter(id=plan_id, gym=gym).first()
        if not plan:
            return Response(
                {"detail": "Membership plan not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not plan.is_active:
            return Response(
                {"detail": "Cannot checkout a deactivated membership plan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build transaction reference with 16 bytes of cryptographically secure randomness
        tx_ref = f"FG-{gym.subdomain}-{secrets.token_hex(16)}"

        # Create pending Payment record bound to gym, member, and plan
        payment = Payment.objects.create(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            member=member,
            plan=plan,
            method=Payment.METHOD_CHAPA,
            amount_etb=plan.price_etb,
            currency="ETB",
            chapa_ref=tx_ref,
            status=Payment.STATUS_PENDING,
        )

        record_audit_log(
            actor=request.user,
            gym=gym,
            action_type="payment_checkout_started",
            affected_record_type="Payment",
            affected_record_id=str(payment.id),
            metadata={
                "tx_ref": tx_ref,
                "plan_id": str(plan.id),
                "plan_name": plan.name,
                "amount_etb": str(plan.price_etb),
            },
        )

        client = ChapaClient(secret_key=config.secret_key)
        domain = getattr(settings, "DOMAIN", "localhost")
        scheme = getattr(settings, "PUBLIC_URL_SCHEME", "https")
        names = (member.full_name or "").split(maxsplit=1)
        first_name = names[0] if names else "Member"
        last_name = names[1] if len(names) > 1 else ""
        email = member.user.email if member.user else ""

        init_payload = {
            "amount": str(plan.price_etb),
            "currency": "ETB",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "tx_ref": tx_ref,
            "callback_url": f"{scheme}://{domain}/api/webhooks/chapa/",
            "return_url": f"{scheme}://{gym.subdomain}.{domain}/members/payment-complete?tx_ref={tx_ref}",
            "customization": {
                "title": f"{gym.name} - {plan.name}",
                "description": f"Subscription payment for {member.full_name}",
            },
        }

        try:
            init_resp = client.initialize_transaction(init_payload)
        except ChapaAPIError as exc:
            payment.status = Payment.STATUS_FAILED
            payment.metadata["initialization_error"] = exc.message
            payment.save(update_fields=["status", "metadata", "updated_at"])
            return Response(
                {"detail": f"Failed to initialize payment gateway: {exc.message}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        checkout_url = init_resp.get("data", {}).get("checkout_url", "")
        return Response(
            {
                "checkout_url": checkout_url,
                "tx_ref": tx_ref,
                "payment_id": payment.id,
            },
            status=status.HTTP_200_OK,
        )


class ChapaWebhookThrottle(AnonRateThrottle):
    scope = "webhook"
    rate = "120/minute"


class ChapaWebhookView(APIView):
    """
    Public webhook endpoint for Chapa payment confirmations.
    Unauthenticated at the transport layer; protected by HMAC SHA-256 signature verification
    and server-side transaction confirmation against Chapa API.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ChapaWebhookThrottle]

    @extend_schema(
        summary="Chapa payment webhook notification",
        description="Processes Chapa webhook notifications with HMAC verification and idempotency.",
        responses={
            200: OpenApiResponse(description="Payment confirmed or already handled"),
            400: OpenApiResponse(description="Invalid payload or verification failure"),
            401: OpenApiResponse(description="Invalid signature"),
            502: OpenApiResponse(description="Gateway verification failure"),
        },
    )
    def post(self, request):
        if len(request.body) > 65536:
            return Response(
                {"detail": "Webhook payload exceeds maximum size limit (64 KB)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sig_header = (
            request.headers.get("x-chapa-signature")
            or request.META.get("HTTP_X_CHAPA_SIGNATURE")
            or ""
        )
        success, message, http_status = process_chapa_webhook(
            raw_body=request.body,
            signature_header=sig_header,
        )
        return Response({"detail": message}, status=http_status)


class SuperAdminGymPaymentStatusView(APIView):
    """
    Platform administrator view of gym payment mode (test vs live).
    Super Admin can view whether a gym is running in test or live mode.
    Super Admin cannot view keys, set keys, or access credentials.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged, IsSuperAdmin]

    @extend_schema(
        summary="View gym payment mode (Super Admin)",
        description="Returns whether the gym is running in test or live mode. Never exposes keys.",
        responses={200: SuperAdminGymPaymentStatusSerializer},
    )
    def get(self, request, gym_id):
        gym = GymTenant.objects.filter(id=gym_id).first()
        if not gym:

            return Response(
                {"detail": "Gym tenant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        config = GymPaymentConfig.all_objects.filter(gym=gym).first()
        data = {
            "gym_id": gym.id,
            "gym_name": gym.name,
            "subdomain": gym.subdomain,
            "is_configured": bool(config and config.is_configured),
            "is_test_mode": config.is_test_mode if config else True,
            "is_verified": config.is_verified if config else False,
        }
        return Response(data, status=status.HTTP_200_OK)


class CanRecordCashPayment(BasePermission):
    """
    Manual cash payment recording can be executed by Owner, Manager, or Reception.
    Trainer, Member, and Super Admin are denied (403).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return False
        return (
            request.user.role
            in (User.ROLE_OWNER, User.ROLE_MANAGER, User.ROLE_RECEPTION)
            and request.user.gym_id == tenant.id
        )


class RecordCashPaymentView(APIView):
    """
    Staff-confirmed manual cash payment recording.
    Creates Payment (confirmed), Receipt, and Subscription in ONE atomic transaction.
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        CanRecordCashPayment,
    ]

    @extend_schema(
        summary="Record manual cash payment (Owner, Manager, Reception)",
        description="Records staff-confirmed cash payment, creates subscription, and generates digital receipt in one transaction.",
        request=RecordCashPaymentRequestSerializer,
        responses={
            201: RecordCashPaymentResponseSerializer,
            400: OpenApiResponse(description="Validation error or cross-gym entity"),
            403: OpenApiResponse(description="Unauthorized role or cross-gym staff"),
            404: OpenApiResponse(description="Member or plan not found"),
        },
    )
    def post(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response(
                {"detail": "Cash payment can only be recorded on a gym portal."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RecordCashPaymentRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        member_id = serializer.validated_data["member_id"]
        plan_id = serializer.validated_data["plan_id"]
        notes = serializer.validated_data.get("notes", "")
        idempotency_key = serializer.validated_data.get("idempotency_key", "")

        # Look up member
        member = Member.all_objects.filter(id=member_id).first()
        if not member:
            return Response(
                {"detail": "Member not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if member.gym_id != tenant.id:
            return Response(
                {"detail": "Member does not belong to this gym."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Look up plan
        plan = MembershipPlan.all_objects.filter(id=plan_id).first()
        if not plan:
            return Response(
                {"detail": "Membership plan not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if plan.gym_id != tenant.id:
            return Response(
                {"detail": "Plan does not belong to this gym."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not plan.is_active:
            return Response(
                {"detail": "Cannot record payment for a deactivated plan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment, receipt, subscription = record_cash_payment(
                gym=tenant,
                member=member,
                plan=plan,
                recorded_by=request.user,
                notes=notes,
                idempotency_key=idempotency_key or None,
            )
        except ValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        receipt_data = ReceiptSerializer(receipt).data if receipt else None
        return Response(
            {
                "detail": "Cash payment recorded and confirmed.",
                "payment_id": str(payment.id),
                "amount_etb": payment.amount_etb,
                "status": payment.status,
                "receipt": receipt_data,
                "subscription_id": (str(subscription.id) if subscription else None),
            },
            status=status.HTTP_201_CREATED,
        )


class CanViewGymPaymentHistory(BasePermission):
    """
    Staff payment history and revenue summary can be viewed by Owner or Manager of that gym.
    Super Admin, Reception, Trainer, and Member are denied (403).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return False
        return (
            request.user.role in (User.ROLE_OWNER, User.ROLE_MANAGER)
            and request.user.gym_id == tenant.id
        )


class GymPaymentListView(APIView):
    """
    Review gym payments filtered by date range, payment method, status, and member.
    Includes total confirmed revenue summary.
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        CanViewGymPaymentHistory,
    ]

    @extend_schema(
        summary="List gym payments & revenue summary (Owner, Manager)",
        description="Filter payments by date range, payment method, status, and member. Returns confirmed revenue total.",
        responses={
            200: OpenApiResponse(
                description="Paginated payment list with confirmed revenue total"
            )
        },
    )
    def get(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "Gym context missing."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = Payment.all_objects.select_related(
            "member", "plan", "confirmed_by", "receipt"
        ).filter(gym=tenant)

        start_date = request.query_params.get("start_date")
        if start_date:
            qs = qs.filter(created_at__date__gte=start_date)

        end_date = request.query_params.get("end_date")
        if end_date:
            qs = qs.filter(created_at__date__lte=end_date)

        method = request.query_params.get("method")
        if method:
            qs = qs.filter(method=method)

        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        member_id = request.query_params.get("member_id")
        if member_id:
            qs = qs.filter(member_id=member_id)

        confirmed_revenue = qs.filter(status=Payment.STATUS_CONFIRMED).aggregate(
            total=Sum("amount_etb")
        )["total"] or Decimal("0.00")

        results = []
        for p in qs[:200]:
            receipt_no = (
                p.receipt.receipt_number if hasattr(p, "receipt") and p.receipt else ""
            )
            notes = p.metadata.get("notes", "") if isinstance(p.metadata, dict) else ""
            reversal_at = (
                p.reversal.reversed_at
                if hasattr(p, "reversal") and p.reversal
                else None
            )
            results.append(
                {
                    "id": str(p.id),
                    "created_at": p.created_at,
                    "payer_type": p.payer_type,
                    "member_id": str(p.member_id) if p.member_id else None,
                    "member_name": p.member.full_name if p.member else "",
                    "plan_id": str(p.plan_id) if p.plan_id else None,
                    "plan_name": p.plan.name if p.plan else "",
                    "method": p.method,
                    "amount_etb": p.amount_etb,
                    "currency": p.currency,
                    "status": p.status,
                    "confirmed_by_id": (
                        str(p.confirmed_by_id) if p.confirmed_by_id else None
                    ),
                    "confirmed_by_name": (
                        p.confirmed_by.full_name if p.confirmed_by else ""
                    ),
                    "receipt_number": receipt_no,
                    "notes": notes,
                    "bank_reference": p.bank_reference or "",
                    "transfer_date": p.transfer_date,
                    "channel": p.channel or "",
                    "is_reconciled": p.is_reconciled,
                    "reconciled_at": p.reconciled_at,
                    "is_reversed": p.status == Payment.STATUS_REVERSED,
                    "reversed_at": reversal_at,
                }
            )

        return Response(
            {
                "count": len(results),
                "total_confirmed_revenue_etb": str(confirmed_revenue),
                "results": results,
            },
            status=status.HTTP_200_OK,
        )


class MemberPaymentHistoryView(APIView):
    """
    Self-service payment history for the logged-in member.
    Owner, Manager, Reception, Trainer, Super Admin get 403.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged]

    @extend_schema(
        summary="View member personal payment history",
        description="Returns the logged-in member's complete payment history with dates, amounts, and receipt references.",
        responses={200: MemberPaymentHistoryItemSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        if request.user.role != User.ROLE_MEMBER:
            return Response(
                {"detail": "Member payment history is accessible to members only."},
                status=status.HTTP_403_FORBIDDEN,
            )

        tenant = getattr(request, "tenant", None)
        member = Member.all_objects.filter(user=request.user).first()
        if not member:
            return Response({"results": []}, status=status.HTTP_200_OK)

        qs = Payment.all_objects.select_related(
            "plan", "subscription", "receipt", "reversal"
        ).filter(member=member)
        if tenant:
            qs = qs.filter(gym=tenant)

        results = []
        for p in qs:
            receipt_no = (
                p.receipt.receipt_number if hasattr(p, "receipt") and p.receipt else ""
            )
            reversal_at = (
                p.reversal.reversed_at
                if hasattr(p, "reversal") and p.reversal
                else None
            )
            results.append(
                {
                    "id": str(p.id),
                    "created_at": p.created_at,
                    "plan_name": p.plan.name if p.plan else "",
                    "method": p.method,
                    "amount_etb": p.amount_etb,
                    "currency": p.currency,
                    "status": p.status,
                    "receipt_number": receipt_no,
                    "bank_reference": p.bank_reference or "",
                    "is_reversed": p.status == Payment.STATUS_REVERSED,
                    "reversed_at": reversal_at,
                    "subscription_start_date": (
                        p.subscription.start_date if p.subscription else None
                    ),
                    "subscription_end_date": (
                        p.subscription.end_date if p.subscription else None
                    ),
                }
            )

        return Response({"results": results}, status=status.HTTP_200_OK)


class ReceiptDetailView(APIView):
    """
    Retrieve digital receipt details.
    Accessible to staff (Owner, Manager, Reception of same gym)
    and the member who owns the receipt.
    """

    permission_classes = [IsAuthenticated, RequirePasswordChanged]

    @extend_schema(
        summary="Retrieve digital receipt details",
        description="Returns receipt details for staff or the member who owns the payment.",
        responses={200: ReceiptSerializer},
    )
    def get(self, request, receipt_id, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        receipt = (
            Receipt.all_objects.select_related("gym", "issued_by", "payment__member")
            .filter(id=receipt_id)
            .first()
        )
        if not receipt:
            return Response(
                {"detail": "Receipt not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if tenant and receipt.gym_id != tenant.id:
            return Response(
                {"detail": "Receipt not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = request.user
        is_staff_allowed = (
            user.role in (User.ROLE_OWNER, User.ROLE_MANAGER, User.ROLE_RECEPTION)
            and user.gym_id == receipt.gym_id
        )
        is_owner_member = (
            user.role == User.ROLE_MEMBER
            and receipt.payment.member
            and receipt.payment.member.user_id == user.id
        )

        if not (is_staff_allowed or is_owner_member):
            return Response(
                {"detail": "You do not have permission to view this receipt."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ReceiptSerializer(receipt)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CanRecordBankTransfer(BasePermission):
    """
    Bank transfer payment recording can be executed by Owner, Manager, or Reception.
    Super Admin, Trainer, Member are denied (403). Cross-gym denied (403).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == User.ROLE_SUPER_ADMIN:
            return False
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return False
        return (
            request.user.role
            in (User.ROLE_OWNER, User.ROLE_MANAGER, User.ROLE_RECEPTION)
            and request.user.gym_id == tenant.id
        )


class CanManageBankTransfers(BasePermission):
    """
    Owner ONLY of that gym can view unreconciled bank transfers, reconcile them, or reverse them.
    Super Admin, Manager, Reception, Trainer, Member are denied (403). Cross-gym denied (403).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == User.ROLE_SUPER_ADMIN:
            return False
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return False
        return request.user.role == User.ROLE_OWNER and request.user.gym_id == tenant.id


class RecordBankTransferPaymentView(APIView):
    """
    Record and confirm a bank-transfer payment for a member.
    Allowed: Owner, Manager, Reception of that gym.
    Denied: Member, Trainer, Super Admin (403). Other gyms (403).
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        CanRecordBankTransfer,
    ]

    @extend_schema(
        summary="Record member bank-transfer payment",
        description="Records a bank-transfer payment for a member with bank reference, transfer date, and channel.",
        request=RecordBankTransferPaymentRequestSerializer,
        responses={
            201: RecordBankTransferResponseSerializer,
            400: OpenApiResponse(description="Validation error or duplicate reference"),
            403: OpenApiResponse(description="Permission denied"),
        },
    )
    def post(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "Tenant required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RecordBankTransferPaymentRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        member_id = serializer.validated_data["member_id"]
        plan_id = serializer.validated_data["plan_id"]
        bank_reference = serializer.validated_data["bank_reference"]
        transfer_date = serializer.validated_data["transfer_date"]
        channel = serializer.validated_data.get("channel", "")
        notes = serializer.validated_data.get("notes", "")
        idempotency_key = serializer.validated_data.get("idempotency_key", "")

        member = Member.all_objects.filter(id=member_id).first()
        if not member or member.gym_id != tenant.id:
            return Response(
                {"detail": "Member does not belong to this gym."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plan = MembershipPlan.all_objects.filter(id=plan_id).first()
        if not plan or plan.gym_id != tenant.id:
            return Response(
                {"detail": "Plan does not belong to this gym."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not plan.is_active:
            return Response(
                {"detail": "Cannot record payment for a deactivated plan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment, receipt, subscription = record_bank_transfer_payment(
                gym=tenant,
                member=member,
                plan=plan,
                recorded_by=request.user,
                bank_reference=bank_reference,
                transfer_date=transfer_date,
                channel=channel,
                notes=notes,
                idempotency_key=idempotency_key or None,
            )
        except ValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        receipt_data = ReceiptSerializer(receipt).data if receipt else None
        return Response(
            {
                "detail": "Bank transfer payment recorded and confirmed.",
                "payment_id": str(payment.id),
                "amount_etb": payment.amount_etb,
                "status": payment.status,
                "bank_reference": payment.bank_reference,
                "is_reconciled": payment.is_reconciled,
                "receipt": receipt_data,
                "subscription_id": (str(subscription.id) if subscription else None),
            },
            status=status.HTTP_201_CREATED,
        )


class UnreconciledBankTransfersView(APIView):
    """
    List unreconciled bank transfers for owner review.
    Owner ONLY of that gym.
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        CanManageBankTransfers,
    ]

    @extend_schema(
        summary="List unreconciled bank transfers",
        description="Returns unreconciled bank transfers for owner reconciliation. Owner only.",
        responses={200: UnreconciledBankTransferItemSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST
            )

        transfers = (
            Payment.all_objects.select_related("member", "confirmed_by", "receipt")
            .filter(
                gym=tenant,
                method=Payment.METHOD_BANK_TRANSFER,
                status=Payment.STATUS_CONFIRMED,
                is_reconciled=False,
            )
            .order_by("-created_at")
        )

        results = []
        for t in transfers:
            receipt_no = (
                t.receipt.receipt_number if hasattr(t, "receipt") and t.receipt else ""
            )
            results.append(
                {
                    "id": str(t.id),
                    "transfer_date": t.transfer_date,
                    "created_at": t.created_at,
                    "bank_reference": t.bank_reference or "",
                    "channel": t.channel or "",
                    "amount_etb": t.amount_etb,
                    "member_id": str(t.member_id) if t.member_id else None,
                    "member_name": t.member.full_name if t.member else "",
                    "member_phone": t.member.phone if t.member else "",
                    "confirmed_by_id": (
                        str(t.confirmed_by_id) if t.confirmed_by_id else None
                    ),
                    "confirmed_by_name": (
                        t.confirmed_by.full_name if t.confirmed_by else ""
                    ),
                    "receipt_number": receipt_no,
                }
            )

        return Response(
            {"count": len(results), "results": results}, status=status.HTTP_200_OK
        )


class ReconcileBankTransfersView(APIView):
    """
    Reconcile one or multiple bank transfers against bank statement.
    Owner ONLY of that gym.
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        CanManageBankTransfers,
    ]

    @extend_schema(
        summary="Reconcile bank transfers",
        description="Marks bank transfers as reconciled. Owner only.",
        request=ReconcileBankTransfersSerializer,
        responses={200: OpenApiResponse(description="Reconciliation result")},
    )
    def post(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ReconcileBankTransfersSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        payment_ids = serializer.validated_data["payment_ids"]
        try:
            cleared_count = reconcile_bank_transfers(
                payment_ids=payment_ids,
                cleared_by=request.user,
                gym=tenant,
            )
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": f"Successfully cleared {cleared_count} bank transfer(s).",
                "cleared_count": cleared_count,
            },
            status=status.HTTP_200_OK,
        )


class ReverseBankTransferView(APIView):
    """
    Reverse an unreconciled bank transfer payment.
    Owner ONLY of that gym.
    """

    permission_classes = [
        IsAuthenticated,
        RequirePasswordChanged,
        CanManageBankTransfers,
    ]

    @extend_schema(
        summary="Reverse bank transfer payment",
        description="Reverses an unreconciled bank transfer, restores subscription state, and creates immutable reversal record. Owner only.",
        request=ReverseBankTransferSerializer,
        responses={200: OpenApiResponse(description="Reversal result")},
    )
    def post(self, request, payment_id, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response(
                {"detail": "Tenant required."}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ReverseBankTransferSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        reason = serializer.validated_data["reason"]
        try:
            payment, reversal = reverse_bank_transfer_payment(
                payment_id=payment_id,
                reversed_by=request.user,
                reason=reason,
                gym=tenant,
            )
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Bank transfer payment successfully reversed.",
                "payment_id": str(payment.id),
                "status": payment.status,
                "reversal_id": str(reversal.id),
                "reversed_at": reversal.reversed_at,
            },
            status=status.HTTP_200_OK,
        )
