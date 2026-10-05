from odoo import fields, models


class AccountDebitNote(models.TransientModel):
    _inherit = "account.debit.note"

    copy_lines = fields.Boolean(default=True)
    fcws_motivo_emision = fields.Selection(
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
        string="Motivo de emisión FCWS",
        default="1",
        required=True,
    )

    def create_debit(self):
        self.ensure_one()
        reason = dict(self._fields["fcws_motivo_emision"].selection).get(
            self.fcws_motivo_emision
        )
        if reason:
            self.reason = reason
        action = super().create_debit()
        debit_notes = self.env["account.move"].browse(action.get("res_id"))
        if not debit_notes and action.get("domain"):
            debit_notes = self.env["account.move"].search(action["domain"])
        debit_notes.write({"fcws_motivo_emision": self.fcws_motivo_emision})
        document_type = self.env["account.tip.doc"].search(
            [("tipdoc", "=", "sale"), ("internal_type", "=", "debit_note")],
            limit=1,
        )
        if document_type:
            debit_notes.tipdocing = document_type
        return action
