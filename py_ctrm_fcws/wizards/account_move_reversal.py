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

    def reverse_moves(self):
        self.ensure_one()
        for refund in self:
            if not refund.motivo_emision:
                raise UserError(
                    "Debe seleccionar un motivo de emisión para poder continuar."
                )

        action = super().reverse_moves()

        for credit_note in self.new_move_ids.filtered(
            lambda move: move.move_type == "out_refund"
        ):
            credit_note.fcws_motivo_emision = self.motivo_emision
            doc = self.env["account.tip.doc"].search(
                [("tipdoc", "=", "sale"), ("internal_type", "=", "credit_note")],
                limit=1,
            )
            credit_note.tipdocing = doc

        return action
