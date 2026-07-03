from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    fcws_enabled = fields.Boolean(
        string="Usar Facturación Electrónica (FCWS)",
        help="Si está activado, las facturas emitidas con este diario serán enviadas al servicio FCWS.",
    )
    timbrado_id = fields.Many2one('account.journal.stamped', string='Timbrado', copy=False)
