"""Event collectors for various source systems."""

from process_discovery.event_collectors.jira_events import JiraEventCollector
from process_discovery.event_collectors.crm_events import CrmEventCollector
from process_discovery.event_collectors.helpdesk_events import HelpdeskEventCollector
from process_discovery.event_collectors.github_events import GithubEventCollector
from process_discovery.event_collectors.email_events import EmailEventCollector

ALL_COLLECTORS = [
    JiraEventCollector,
    CrmEventCollector,
    HelpdeskEventCollector,
    GithubEventCollector,
    EmailEventCollector,
]

__all__ = [
    "JiraEventCollector",
    "CrmEventCollector",
    "HelpdeskEventCollector",
    "GithubEventCollector",
    "EmailEventCollector",
    "ALL_COLLECTORS",
]
