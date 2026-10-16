"""
Performance test for Sprint 8: QR Check-in (GATE).

Criterion:
"Performance: scan validation plus attendance recording completes in under 2 seconds
against a seeded dataset of 10,000 members."
"""

import time
import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.attendance.services import issue_member_qr_token, verify_and_process_scan
from apps.memberships.models import Member, MemberSubscription
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestQRScanPerformance:
    """Validate scan execution latency under high member volume (10,000 members)."""

    def test_scan_validation_and_recording_under_2_seconds_with_10k_members(self):
        gym = GymTenant.objects.create(
            name="FitGate Mega Hub",
            subdomain="megahub",
            tier=GymTenant.TIER_PRO,
            status=GymTenant.STATUS_ACTIVE,
            contact_phone="+251911999999",
            location="Meskel Square, Addis Ababa",
            tls_confirmed_at="2026-10-11T10:00:00Z",
        )

        reception = User.objects.create_user(
            email="reception@megahub.com",
            password="ReceptionPassword123!",
            gym=gym,
            role=User.ROLE_RECEPTION,
            must_change_password=False,
        )

        target_user = User.objects.create_user(
            email="targetmember@megahub.com",
            password="MemberPassword123!",
            gym=gym,
            role=User.ROLE_MEMBER,
            must_change_password=False,
        )

        target_member = Member.all_objects.create(
            gym=gym,
            user=target_user,
            full_name="Target Member",
            phone="+251911000001",
            status=Member.STATUS_ACTIVE,
            waiver_accepted_at=timezone.now(),
        )

        today = timezone.localdate()
        MemberSubscription.all_objects.create(
            gym=gym,
            member=target_member,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=29),
            status=MemberSubscription.STATUS_ACTIVE,
        )

        # Seed 10,000 members with bulk_create (User then Member)
        total_seeded = 10000
        batch_size = 2500

        users_to_seed = [
            User(
                id=uuid.uuid4(),
                email=f"bulk{i}@megahub.com",
                password="!",
                gym=gym,
                role=User.ROLE_MEMBER,
                is_active=True,
            )
            for i in range(total_seeded)
        ]
        User.objects.bulk_create(users_to_seed, batch_size=batch_size)

        members_to_seed = [
            Member(
                id=uuid.uuid4(),
                gym=gym,
                user=users_to_seed[i],
                full_name=f"Bulk Member {i}",
                phone=f"+25190{i:07d}",
                status=Member.STATUS_ACTIVE,
                waiver_accepted_at=timezone.now(),
            )
            for i in range(total_seeded)
        ]
        Member.all_objects.bulk_create(members_to_seed, batch_size=batch_size)

        assert Member.all_objects.filter(gym=gym).count() >= 10001

        # Issue token for target member
        token_str, qr_record = issue_member_qr_token(target_member)

        # Measure scan validation and attendance recording execution duration
        start_time = time.perf_counter()
        result = verify_and_process_scan(
            token_str=token_str,
            gym=gym,
            recorded_by=reception,
        )
        elapsed_time = time.perf_counter() - start_time

        print(
            f"\n[PERFORMANCE] 10,000 members scan execution time: {elapsed_time:.4f}s"
        )

        # Assertions
        assert result["status"] == "success"
        assert result["member"]["full_name"] == "Target Member"
        assert Attendance.all_objects.filter(gym=gym, member=target_member).count() == 1

        # Must complete in under 2 seconds (typically < 0.05s)
        assert elapsed_time < 2.0, (
            f"Expected scan validation + recording to complete under 2.0s, "
            f"but took {elapsed_time:.4f}s"
        )
