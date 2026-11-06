from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class HasTrainerModule(BasePermission):
    """
    Ensures that the gym has the trainer module enabled (GymConfig.has_trainer_module=True).
    Super Admin is denied on gym operational data.
    """

    message = "Trainer module is not enabled for this gym."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == User.ROLE_SUPER_ADMIN:
            raise PermissionDenied(
                "Super Admin cannot access gym trainer operational data."
            )

        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False

        # Tenant scoping: User must belong to the tenant
        if getattr(request.user, "gym_id", None) != tenant.id:
            return False

        config = getattr(tenant, "config", None)
        if not config or not config.has_trainer_module:
            from apps.tenants.models import GymConfig

            config = GymConfig.objects.filter(gym_id=tenant.id).first()
            if not config or not config.has_trainer_module:
                raise PermissionDenied("Trainer module is not enabled for this gym.")

        return True


class HasAIPlansEnabled(BasePermission):
    """
    Ensures that the gym has AI plans enabled (GymConfig.has_ai_plans=True).
    Super Admin is denied on gym operational data.
    """

    message = "AI training plans are not enabled for this gym."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == User.ROLE_SUPER_ADMIN:
            raise PermissionDenied("Super Admin cannot access gym training plans.")

        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False

        if getattr(request.user, "gym_id", None) != tenant.id:
            return False

        config = getattr(tenant, "config", None)
        if not config or not getattr(config, "has_ai_plans", False):
            from apps.tenants.models import GymConfig

            config = GymConfig.objects.filter(gym_id=tenant.id).first()
            if not config or not getattr(config, "has_ai_plans", False):
                raise PermissionDenied(
                    "AI training plans are not enabled for this gym."
                )

        return True


class IsOwnerOrManager(BasePermission):
    """Allows access only to Owner or Manager of the tenant."""

    message = "Only Gym Owner or Manager can perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == User.ROLE_SUPER_ADMIN:
            raise PermissionDenied(
                "Super Admin cannot access gym trainer operational data."
            )

        return request.user.role in (User.ROLE_OWNER, User.ROLE_MANAGER)


class IsTrainerRole(BasePermission):
    """Allows access only to Trainer of the tenant."""

    message = "Only Trainers can access this endpoint."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == User.ROLE_SUPER_ADMIN:
            raise PermissionDenied(
                "Super Admin cannot access gym trainer operational data."
            )

        return request.user.role == User.ROLE_TRAINER


class CanAccessMemberFitnessProfile(BasePermission):
    """
    Grants access to Gym Owner, Manager, or the assigned Trainer of the member.
    Super Admin, Reception, Member, unrelated trainers, and cross-tenant users receive 403 Forbidden.
    """

    message = "You do not have permission to access this fitness profile."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == User.ROLE_SUPER_ADMIN:
            raise PermissionDenied(
                "Super Admin cannot access member fitness profile data."
            )

        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False

        if getattr(request.user, "gym_id", None) != tenant.id:
            return False

        # Role check
        if request.user.role in (User.ROLE_OWNER, User.ROLE_MANAGER):
            return True

        if request.user.role == User.ROLE_TRAINER:
            member_id = view.kwargs.get("member_id")
            if not member_id:
                return False
            from apps.trainers.models import TrainerAssignment

            is_assigned = TrainerAssignment.objects.filter(
                trainer__user=request.user,
                member_id=member_id,
                ended_at__isnull=True,
                gym=tenant,
            ).exists()
            if not is_assigned:
                raise PermissionDenied(
                    "Trainers can only access fitness profiles for their currently assigned clients."
                )
            return True

        return False


class CanAccessMemberSelfFitnessProfile(BasePermission):
    """
    Allows a Member to view their own fitness profile read-only (GET only).
    Write methods receive 403 Forbidden.
    """

    message = "You do not have permission to access this fitness profile."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == User.ROLE_SUPER_ADMIN:
            raise PermissionDenied("Super Admin cannot access member fitness profiles.")

        tenant = getattr(request, "tenant", None)
        if not tenant or getattr(request.user, "gym_id", None) != tenant.id:
            return False

        if request.user.role != User.ROLE_MEMBER:
            return False

        if request.method not in ("GET", "HEAD", "OPTIONS"):
            raise PermissionDenied(
                "Members cannot edit their fitness profile directly."
            )

        return True


class CanManageMemberTrainingPlans(BasePermission):
    """
    Grants access to Gym Owner, Manager, or the assigned Trainer of the member
    to view prerequisites, list plans, or generate plans for that member.
    Unrelated trainers, Super Admin, Reception, and other roles receive 403.
    """

    message = "You do not have permission to manage training plans for this member."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == User.ROLE_SUPER_ADMIN:
            raise PermissionDenied("Super Admin cannot manage gym training plans.")

        tenant = getattr(request, "tenant", None)
        if not tenant or getattr(request.user, "gym_id", None) != tenant.id:
            return False

        if request.user.role in (User.ROLE_OWNER, User.ROLE_MANAGER):
            return True

        if request.user.role == User.ROLE_TRAINER:
            member_id = view.kwargs.get("member_id")
            if not member_id:
                return False
            from apps.trainers.models import TrainerAssignment

            is_assigned = TrainerAssignment.objects.filter(
                trainer__user=request.user,
                member_id=member_id,
                ended_at__isnull=True,
                gym=tenant,
            ).exists()
            if not is_assigned:
                raise PermissionDenied(
                    "Trainers can only manage training plans for their currently assigned clients."
                )
            return True

        return False


class CanManageTrainingPlanDetail(BasePermission):
    """
    Grants access to Gym Owner, Manager, or the assigned Trainer of the plan's member
    to view, approve, reject, or edit a specific training plan.
    """

    message = "You do not have permission to access or modify this training plan."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == User.ROLE_SUPER_ADMIN:
            raise PermissionDenied("Super Admin cannot manage gym training plans.")

        tenant = getattr(request, "tenant", None)
        if not tenant or getattr(request.user, "gym_id", None) != tenant.id:
            return False

        if request.user.role in (User.ROLE_OWNER, User.ROLE_MANAGER):
            return True

        if request.user.role == User.ROLE_TRAINER:
            plan_id = view.kwargs.get("pk") or view.kwargs.get("plan_id")
            if not plan_id:
                return False
            from apps.trainers.models import TrainerAssignment, TrainingPlan

            plan = TrainingPlan.all_objects.filter(id=plan_id, gym=tenant).first()
            if not plan:
                return True  # Let view return 404

            is_assigned = TrainerAssignment.all_objects.filter(
                trainer__user=request.user,
                member=plan.member,
                ended_at__isnull=True,
                gym=tenant,
            ).exists()
            if not is_assigned:
                raise PermissionDenied(
                    "Trainers can only access plans for their currently assigned clients."
                )
            return True

        return False


class CanAccessMemberApprovedPlans(BasePermission):
    """
    Allows a member to view only their approved training plans.
    """

    message = "You do not have permission to view training plans."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == User.ROLE_SUPER_ADMIN:
            raise PermissionDenied("Super Admin cannot access member plans.")

        tenant = getattr(request, "tenant", None)
        if not tenant or getattr(request.user, "gym_id", None) != tenant.id:
            return False

        return request.user.role == User.ROLE_MEMBER
