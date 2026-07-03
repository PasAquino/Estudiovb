from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    check_deposit_offsetting_account = fields.Selection(
        selection=[("bank_account", "Cuenta bancaria"), ("transfer_account", "Cuenta de transferencia")],
        string="Cuenta de compensación de depósitos de cheques",
        default="bank_account")
    check_deposit_transfer_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta de transferencia para depósitos de cheques",
        ondelete="restrict",
        copy=False,
        domain=[("reconcile", "=", True), ("deprecated", "=", False)])
    check_deposit_post_move = fields.Boolean(string="Confirmar Depósitos Automáticamente")
