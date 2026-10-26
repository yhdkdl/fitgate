"""API Views for Gym Payment Configuration, Chapa Checkout, Webhook processing, and Admin status."""

import logging
import secrets

from django.conf import settings
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
from apps.payments.models import GymPaymentConfig, Payment
from apps.payments.serializers import (
    ChapaCheckoutRequestSerializer,
    ChapaCheckoutResponseSerializer,
    GymPaymentConfigSerializer,
    GymPaymentConfigUpdateSerializer,
    SuperAdminGymPaymentStatusSerializer,
)
from apps.payments.services import process_chapa_webhook
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
