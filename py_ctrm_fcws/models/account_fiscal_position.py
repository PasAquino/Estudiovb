from odoo import fields, models


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"
    is_government = fields.Boolean(default=False, string="Es gubernamental?")
