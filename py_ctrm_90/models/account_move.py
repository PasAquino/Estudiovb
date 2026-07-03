# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

import json



class AccountMove90(models.Model):
    _inherit = "account.move"

    imputa_iva = fields.Boolean(
        string="Imputa al IVA?"
    )
    imputa_ire = fields.Boolean(
        string="Imputa al IRE?"
    )
    imputa_irp = fields.Boolean(
        string="Imputa al IRP-RSP?"
    )
    no_imputa = fields.Selection([('imputa', 'S'), ('no_imputa', 'N')], string="No imputa ?", default="no_imputa")
    factura_electronica = fields.Boolean(string="Factura Electronica?", default=False)
    nota_credito_asociada = fields.Char(string="Nota de Credito")
    auxi_field = fields.Text(string="Campo auxiliar", compute="_compute_payments_widget_reconciled_names")

    @api.depends('move_type', 'line_ids.amount_residual')
    def _compute_payments_widget_reconciled_names(self):
        for move in self:
            payments_widget_vals = ""
            if move.state == 'posted' and move.is_invoice(include_receipts=True):
                payments_widget_vals = move._get_reconciled_info_values_names()
            if payments_widget_vals:
                move.nota_credito_asociada = payments_widget_vals
                move.auxi_field = "Campo ya calculado"
            else:
                move.auxi_field = json.dumps(False)

    def _get_reconciled_info_values_names(self):
        self.ensure_one()
        ref = ""
        for partial, amount, counterpart_line in self._get_reconciled_invoices_partials():
            if counterpart_line.move_id.ref:
                reconciliation_ref = '%s (%s)' % (counterpart_line.move_id.name, counterpart_line.move_id.ref)
            else:
                reconciliation_ref = counterpart_line.move_id.name
            if self.move_type in ('out_invoice', 'out_refund'):
                ref = counterpart_line.move_id.name
            else:
                ref = counterpart_line.move_id.ref
        return ref
