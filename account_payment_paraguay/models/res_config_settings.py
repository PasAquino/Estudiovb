from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    check_deposit_offsetting_account = fields.Selection(related="company_id.check_deposit_offsetting_account", readonly=False)
    check_deposit_transfer_account_id = fields.Many2one(related="company_id.check_deposit_transfer_account_id", readonly=False)
    check_deposit_post_move = fields.Boolean(related="company_id.check_deposit_post_move", readonly=False)
