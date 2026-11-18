"""
Unit tests for gym-themed HTML email template builder.
"""

import re
import pytest

from apps.accounts.email_templates import (
    format_plain_text_to_html,
    render_gym_email_html,
)


class DummyGym:
    def __init__(self, name="Iron Peak Gym", location="Addis Ababa, Bole"):
        self.name = name
        self.location = location


def test_format_plain_text_to_html_escapes_and_formats_paragraphs():
    raw = "Line 1\nLine 2\n\nParagraph 2 with <tag>"
    formatted = format_plain_text_to_html(raw)
    assert "<p " in formatted
    assert "Line 1<br>Line 2" in formatted
    assert "&lt;tag&gt;" in formatted


def test_render_gym_email_html_structure_with_gym():
    gym = DummyGym(name="Atlas Fitness", location="Bole Medhanialem")
    html_output = render_gym_email_html(
        headline="Membership Activated",
        body_text_or_paragraphs=["Welcome to our gym.", "Your pass is ready."],
        gym=gym,
        badge_text="MEMBER ACCESS",
        action_url="https://atlas.fitgate.org/login",
        action_label="Open Portal",
        detail_rows=[
            ("Plan", "Gold Annual"),
            ("Status", "Active"),
        ],
        notice_text="Badge rotates every 90 seconds.",
    )

    # Check gym header
    assert "ATLAS FITNESS" in html_output
    assert "Bole Medhanialem" in html_output
    assert "MEMBER ACCESS" in html_output

    # Check headline & body
    assert "Membership Activated" in html_output
    assert "Welcome to our gym." in html_output
    assert "Your pass is ready." in html_output

    # Check button and link
    assert 'href="https://atlas.fitgate.org/login"' in html_output
    assert "OPEN PORTAL" in html_output

    # Check detail table
    assert "Gold Annual" in html_output
    assert "Active" in html_output

    # Check notice
    assert "Badge rotates every 90 seconds." in html_output

    # Check no emojis
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff\U00002600-\U000027ff]", flags=re.UNICODE
    )
    assert not emoji_pattern.search(html_output), "Rendered HTML contains emojis!"


def test_render_gym_email_html_default_fallback_without_gym():
    html_output = render_gym_email_html(
        headline="System Notice",
        body_text_or_paragraphs="This is an automated system announcement.",
    )

    assert "FITGATE" in html_output
    assert "System Notice" in html_output
    assert "This is an automated system announcement." in html_output
