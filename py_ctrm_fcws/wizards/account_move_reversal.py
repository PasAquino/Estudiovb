from odoo import fields, models
from odoo.exceptions import UserError


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    motivo_emision = fields.Selection(
        [
            ("1", "Devolución y Ajuste de precios"),
            ("2", "Devolución"),
            ("3", "Descuento"),
            ("4", "Bonificación"),
            ("5", "Crédito incobrable"),
            ("6", "Recupero de costo"),
            ("7", "Recupero de gasto"),
            ("8", "Ajuste de precio"),
        ],
        string="Motivo",
        required=True,
    )

    def reverse_moves(self, is_modify=False):
        for refund in self:
            if not refund.motivo_emision:
                raise UserError(
                    "Debe seleccionar un motivo de emisión para poder continuar."
                )

        action = super().reverse_moves()

        for refund in self:
            credit_note = self.env["account.move"].browse(action["res_id"])
            credit_note.fcws_motivo_emision = refund.motivo_emision
            doc = self.env["account.tip.doc"].search(
                [("tipdoc", "=", "sale"), ("internal_type", "=", "credit_note")],
                limit=1,
            )
            credit_note.tipdocing = doc

        return action
