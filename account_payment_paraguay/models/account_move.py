from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class AccountMoveInherit(models.Model):
    _inherit = "account.move"

    def _get_tax_factor(self):
        self.ensure_one()
        return self.amount_total and (self.amount_untaxed / self.amount_total) or 1.0

    def action_account_invoice_payment_group(self):
        self.ensure_one()
        partner_type = ""
        if self.move_type == 'out_invoice':
            partner_type = 'customer'
        if self.move_type == 'in_invoice':
            partner_type = 'supplier'
        return {
            'name': _('Registrar Pago'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.payment.paraguay',
            'view_id': False,
            'target': 'current',
            'type': 'ir.actions.act_window',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_partner_type': partner_type,
                'default_invoices_payment_ids': [(0, 0, {'invoice_id': self.id})],
                'create': True,
                'default_company_id': self.company_id.id,
            },
        }
