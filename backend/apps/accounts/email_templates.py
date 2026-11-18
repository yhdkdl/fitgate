"""
HTML Email Template Builder for FitGate.

Renders gym-themed, responsive HTML emails with:
- Dark athletic header with brand accent line
- High-contrast, clean sans-serif typography
- Structured data cards and action buttons
- Zero emojis
"""

import html
from typing import Any, Dict, List, Optional, Tuple, Union


def format_plain_text_to_html(text: str) -> str:
    """Escape text and convert newlines to paragraph/break tags."""
    if not text:
        return ""
    paragraphs = text.strip().split("\n\n")
    html_paragraphs = []
    for p in paragraphs:
        lines = [html.escape(line) for line in p.split("\n")]
        html_paragraphs.append(f'<p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #334155;">{"<br>".join(lines)}</p>')
    return "".join(html_paragraphs)


def render_gym_email_html(
    headline: str,
    body_text_or_paragraphs: Union[str, List[str]],
    gym: Optional[Any] = None,
    badge_text: Optional[str] = None,
    action_url: Optional[str] = None,
    action_label: Optional[str] = None,
    detail_rows: Optional[List[Tuple[str, str]]] = None,
    notice_text: Optional[str] = None,
    preheader: Optional[str] = None,
) -> str:
    """
    Render a responsive gym-themed HTML email.
    
    Adheres strictly to:
    - High-contrast athletic styling (Charcoal, Deep Slate, Power Orange accent)
    - Clean card layout
    - Zero emojis
    """
    gym_name = "FITGATE"
    gym_location = ""
    if gym:
        if hasattr(gym, "name") and gym.name:
            gym_name = str(gym.name).upper()
        if hasattr(gym, "location") and gym.location:
            gym_location = str(gym.location)

    safe_headline = html.escape(headline)
    safe_badge = html.escape(badge_text) if badge_text else None
    safe_preheader = html.escape(preheader or headline)

    # Format body content
    if isinstance(body_text_or_paragraphs, list):
        formatted_body = "".join(
            f'<p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #334155;">{html.escape(p)}</p>'
            for p in body_text_or_paragraphs
        )
    else:
        formatted_body = format_plain_text_to_html(body_text_or_paragraphs)

    # Format detail rows (key-value summary table)
    detail_table_html = ""
    if detail_rows:
        rows_markup = []
        for key, val in detail_rows:
            rows_markup.append(
                f"""
                <tr>
                  <td style="padding: 10px 14px; font-size: 13px; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #E2E8F0; width: 40%;">{html.escape(key)}</td>
                  <td style="padding: 10px 14px; font-size: 14px; font-weight: 700; color: #0F172A; border-bottom: 1px solid #E2E8F0;">{html.escape(val)}</td>
                </tr>
                """
            )
        detail_table_html = f"""
        <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; margin: 24px 0 20px 0; border-collapse: collapse;">
          {"".join(rows_markup)}
        </table>
        """

    # Format Call to Action Button
    button_html = ""
    if action_url and action_label:
        safe_action_label = html.escape(action_label).upper()
        safe_action_url = html.escape(action_url)
        button_html = f"""
        <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="margin: 28px 0 24px 0;">
          <tr>
            <td align="center">
              <!--[if mso]>
              <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="{safe_action_url}" style="height:48px;v-text-anchor:middle;width:240px;" arcsize="12%" fillcolor="#0F172A">
              <w:anchorlock/>
              <center style="color:#ffffff;font-family:sans-serif;font-size:13px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;">{safe_action_label}</center>
              </v:roundrect>
              <![endif]-->
              <a href="{safe_action_url}" target="_blank" style="mso-hide:all; display: inline-block; background-color: #0F172A; color: #FFFFFF !important; font-size: 13px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; text-decoration: none; padding: 14px 32px; border-radius: 6px; border-bottom: 3px solid #F97316;">
                {safe_action_label}
              </a>
            </td>
          </tr>
        </table>
        """

    # Notice callout
    notice_html = ""
    if notice_text:
        safe_notice = html.escape(notice_text)
        notice_html = f"""
        <div style="background-color: #F1F5F9; border-left: 3px solid #64748B; padding: 12px 16px; border-radius: 0 6px 6px 0; font-size: 12px; color: #475569; line-height: 1.5; margin-top: 24px;">
          <span style="font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #334155;">Notice:</span> {safe_notice}
        </div>
        """

    badge_cell = ""
    if safe_badge:
        badge_cell = f"""
        <td align="right" valign="middle">
          <span style="display: inline-block; background-color: #1E293B; color: #F97316; font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; padding: 5px 12px; border-radius: 4px; border: 1px solid #334155;">
            {safe_badge}
          </span>
        </td>
        """

    location_subhead = ""
    if gym_location:
        location_subhead = f'<div style="font-size: 11px; font-weight: 600; color: #94A3B8; letter-spacing: 0.8px; text-transform: uppercase; margin-top: 4px;">{html.escape(gym_location)}</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_headline}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0F172A; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; color: #1E293B; -webkit-font-smoothing: antialiased;">
  <!-- Preheader text -->
  <div style="display: none; max-height: 0px; overflow: hidden; mso-hide: all;">
    {safe_preheader}
  </div>

  <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color: #0F172A; padding: 32px 16px;">
    <tr>
      <td align="center">
        <!-- Main Card Container -->
        <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0" style="max-width: 580px; background-color: #FFFFFF; border-radius: 10px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);">
          
          <!-- Athletic Header -->
          <tr>
            <td style="background-color: #090D16; padding: 26px 32px; border-bottom: 3px solid #F97316;">
              <table role="presentation" width="100%" border="0" cellpadding="0" cellspacing="0">
                <tr>
                  <td align="left" valign="middle">
                    <div style="font-size: 20px; font-weight: 800; letter-spacing: 1.5px; color: #FFFFFF; text-transform: uppercase;">
                      {html.escape(gym_name)}
                    </div>
                    {location_subhead}
                  </td>
                  {badge_cell}
                </tr>
              </table>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding: 36px 32px 32px 32px;">
              <h1 style="margin: 0 0 18px 0; font-size: 21px; font-weight: 700; color: #0F172A; letter-spacing: -0.3px; line-height: 1.3;">
                {safe_headline}
              </h1>

              {formatted_body}

              {detail_table_html}

              {button_html}

              {notice_html}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #F8FAFC; border-top: 1px solid #E2E8F0; padding: 22px 32px; text-align: center;">
              <div style="font-size: 11px; font-weight: 700; letter-spacing: 1px; color: #64748B; text-transform: uppercase;">
                {html.escape(gym_name)} • OFFICIAL NOTIFICATION
              </div>
              <div style="font-size: 11px; color: #94A3B8; margin-top: 8px; line-height: 1.5;">
                This is an automated operational message. Please do not reply directly.<br>
                FitGate Gym Management Platform • Support: support@fitgate.org
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
