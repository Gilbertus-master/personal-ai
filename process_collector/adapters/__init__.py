"""Process collector adapters for various business systems."""

from process_collector.adapters.jira_adapter import JiraAdapter
from process_collector.adapters.sales_adapter import SalesAdapter
from process_collector.adapters.helpdesk_adapter import HelpdeskAdapter
from process_collector.adapters.engineering_adapter import EngineeringAdapter
from process_collector.adapters.finance_adapter import FinanceAdapter
from process_collector.adapters.generic_sql import GenericSQLAdapter

ADAPTER_REGISTRY: dict[str, type] = {
    "jira": JiraAdapter,
    "crm": SalesAdapter,
    "helpdesk": HelpdeskAdapter,
    "github_cicd": EngineeringAdapter,
    "finance": FinanceAdapter,
    "generic_sql": GenericSQLAdapter,
}

__all__ = [
    "ADAPTER_REGISTRY",
    "JiraAdapter",
    "SalesAdapter",
    "HelpdeskAdapter",
    "EngineeringAdapter",
    "FinanceAdapter",
    "GenericSQLAdapter",
]
