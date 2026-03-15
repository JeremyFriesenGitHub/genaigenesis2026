"""Zillow contact-agent flow using MultiOn browse API. One command, multi-step execution."""
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from multion.client import MultiOn

LOG = logging.getLogger(__name__)


@dataclass
class Lead:
    name: str
    email: str
    phone: str
    message: str


@dataclass
class ContactResult:
    session_id: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    url: Optional[str] = None
    screenshot: Optional[str] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


def _build_cmd(lead: Lead, mode: str) -> str:
    submit_line = "Then click the submit/send button to send the form." if mode == "submit" else "Do NOT click submit. Stop after filling the form."
    return (
        f"On this Zillow listing page, click the 'Contact agent' button to open the contact form. "
        f"Then fill in the form fields: "
        f"Name: '{lead.name}', "
        f"Email: '{lead.email}', "
        f"Phone: '{lead.phone}', "
        f"Message: '{lead.message}'. "
        f"{submit_line}"
    )


def run_contact_flow(
    listing_url: str,
    lead: Lead,
    mode: str = "preview",
    *,
    local: bool = False,
    use_proxy: bool = True,
    include_screenshot: bool = True,
    max_steps: int = 20,
) -> ContactResult:
    """
    Use MultiOn browse to open a Zillow listing, click Contact agent, fill the form.
    mode="preview": fill but don't submit. mode="submit": fill and submit.
    """
    result = ContactResult()
    api_key = os.environ.get("MULTION_API_KEY")
    if not api_key:
        result.error = "MULTION_API_KEY not set in environment"
        return result

    client = MultiOn(api_key=api_key)
    cmd = _build_cmd(lead, mode)

    try:
        LOG.info("MultiOn browse: %s", listing_url)
        LOG.info("Command: %s", cmd)

        resp = client.browse(
            cmd=cmd,
            url=listing_url,
            local=local,
            use_proxy=use_proxy,
            include_screenshot=include_screenshot,
            max_steps=max_steps,
        )

        result.session_id = resp.session_id
        result.status = resp.status
        result.message = resp.message
        result.url = resp.url
        result.screenshot = resp.screenshot
        if resp.metadata:
            result.metadata = {
                "step_count": getattr(resp.metadata, "step_count", None),
                "processing_time": getattr(resp.metadata, "processing_time", None),
            }

        LOG.info("Status: %s", resp.status)
        LOG.info("Message: %s", resp.message)
        if mode == "preview":
            LOG.info("Preview complete. Form filled, not submitted.")
        return result

    except Exception as e:
        LOG.exception("MultiOn contact flow failed")
        result.error = str(e)
        return result
