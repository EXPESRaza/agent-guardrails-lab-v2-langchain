"""Langchain tool implementations for agent guardrails lab."""
from __future__ import annotations

from typing import Any, Dict, Optional, Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field


# Tool argument schemas
class SearchWebArgs(BaseModel):
    """Arguments for web search tool."""
    query: str = Field(description="The search query to execute")


class SendEmailArgs(BaseModel):
    """Arguments for send email tool."""
    to: str = Field(description="Email recipient address")
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Email message body")


class DeleteRecordsArgs(BaseModel):
    """Arguments for delete records tool."""
    table: str = Field(description="Database table name")
    where: str = Field(description="SQL WHERE clause condition")


class CustomerLookupArgs(BaseModel):
    """Arguments for customer lookup tool."""
    query: str = Field(description="Customer search query")


# Tool implementations
class SearchWebTool(BaseTool):
    """Tool for searching the web. Low risk operation."""

    name: str = "search_web"
    description: str = (
        "Search the web for information. Use this when the user asks to "
        "search, lookup information online, or find web results."
    )
    args_schema: Type[BaseModel] = SearchWebArgs

    def _run(self, query: str) -> str:
        """Execute web search."""
        return f"[search_web] Results for: {query}"

    async def _arun(self, query: str) -> str:
        """Async execution (not implemented)."""
        raise NotImplementedError("Async not supported")


class SendEmailTool(BaseTool):
    """Tool for sending emails. High risk operation requiring approval."""

    name: str = "send_email"
    description: str = (
        "Send an email message. Use this when the user wants to send an email, "
        "notify someone, or communicate with team members via email."
    )
    args_schema: Type[BaseModel] = SendEmailArgs

    def _run(self, to: str, subject: str, body: str) -> str:
        """Send email."""
        return f"[send_email] Email queued to {to} with subject '{subject}'."

    async def _arun(self, to: str, subject: str, body: str) -> str:
        """Async execution (not implemented)."""
        raise NotImplementedError("Async not supported")


class DeleteRecordsTool(BaseTool):
    """Tool for deleting database records. Very high risk operation requiring approval."""

    name: str = "delete_records"
    description: str = (
        "Delete records from a database table. Use this when the user explicitly "
        "requests to delete or remove data from the database. This is a destructive "
        "operation and requires careful consideration."
    )
    args_schema: Type[BaseModel] = DeleteRecordsArgs

    def _run(self, table: str, where: str) -> str:
        """Delete database records."""
        return f"[delete_records] Deleted from {table} where {where}."

    async def _arun(self, table: str, where: str) -> str:
        """Async execution (not implemented)."""
        raise NotImplementedError("Async not supported")


class CustomerLookupTool(BaseTool):
    """Tool for looking up customer information. Medium risk operation."""

    name: str = "customer_lookup"
    description: str = (
        "Look up customer information in the database. Use this when the user "
        "wants to find customer details, check customer records, or retrieve "
        "customer data."
    )
    args_schema: Type[BaseModel] = CustomerLookupArgs

    def _run(self, query: str) -> str:
        """Lookup customer information."""
        return f"[customer_lookup] Customer found for query: {query}"

    async def _arun(self, query: str) -> str:
        """Async execution (not implemented)."""
        raise NotImplementedError("Async not supported")
