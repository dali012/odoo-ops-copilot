"""Thin wrapper around Odoo's external XML-RPC API.

Docs: https://www.odoo.com/documentation/18.0/developer/reference/external_api.html
"""
import xmlrpc.client
from functools import cached_property

from .config import config


class OdooClient:
    def __init__(self):
        self.url = config.ODOO_URL
        self.db = config.ODOO_DB
        self.username = config.ODOO_USERNAME
        self.password = config.ODOO_PASSWORD

    @cached_property
    def uid(self) -> int:
        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
        uid = common.authenticate(self.db, self.username, self.password, {})
        if not uid:
            raise RuntimeError("Odoo authentication failed - check .env credentials.")
        return uid

    @cached_property
    def models(self):
        return xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")

    def execute(self, model: str, method: str, *args, **kwargs):
        return self.models.execute_kw(
            self.db, self.uid, self.password, model, method, list(args), kwargs
        )

    def search_read(self, model, domain=None, fields=None, limit=80):
        return self.execute(
            model, "search_read",
            domain or [],
            fields=fields or [],
            limit=limit,
        )


odoo = OdooClient()
