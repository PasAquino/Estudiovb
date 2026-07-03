from odoo import fields, models


class L10n_latamIdentificationType(models.Model):
    _inherit = "l10n_latam.identification.type"

    rg_code = fields.Char("RG90 Code", help="RG90 Code")
    edi_code = fields.Char("EDI Code")
    position_id = fields.Many2one("account.fiscal.position", string="Fiscal Position")
