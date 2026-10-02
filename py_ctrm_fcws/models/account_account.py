from odoo import api, fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    account_type = fields.Selection(
        selection=[
            ("asset_receivable", "Receivable"),
            ("asset_cash", "Bank and Cash"),
            ("asset_current", "Current Assets"),
            ("liability_payable", "Payable"),
            ("liability_current", "Current Liabilities"),
            ("equity", "Equity"),
            ("income", "Income"),
            ("expense", "Expenses"),
            ("off_balance", "Off-Balance Sheet"),
        ],
        compute="_compute_account_type",
        string="Account Type",
    )

    @api.depends("internal_type", "internal_group")
    def _compute_account_type(self):
        """Expone en Odoo 15 la clasificación utilizada desde Odoo 17."""
        internal_type_mapping = {
            "receivable": "asset_receivable",
            "payable": "liability_payable",
            "liquidity": "asset_cash",
        }
        internal_group_mapping = {
            "asset": "asset_current",
            "liability": "liability_current",
            "equity": "equity",
            "income": "income",
            "expense": "expense",
            "off_balance": "off_balance",
        }
        for account in self:
            account.account_type = internal_type_mapping.get(
                account.internal_type
            ) or internal_group_mapping.get(account.internal_group)
