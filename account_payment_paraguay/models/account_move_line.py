from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang, format_date, get_lang

import logging

_logger = logging.getLogger(__name__)


class AccountMoveLineInherit(models.Model):
    _inherit = "account.move.line"

    payment_group_ids = fields.Many2many('account.payment.paraguay', 'account_move_line_payment_group_to_pay_rel', 'to_pay_line_id',
                                         'payment_group_id', string="Grupos de Pago", readonly=True)
    financial_amount_residual = fields.Monetary(compute='_compute_financial_amounts', string='Importe financiero residual',
                                                currency_field='company_currency_id')
    financial_amount = fields.Monetary(compute='_compute_financial_amounts', string='Importe financiero', currency_field='company_currency_id')
    reconcile_invoice = fields.Many2one('account.move', string="Factura Conciliada")
    partial_reconcile = fields.Boolean(string="Partial Reconcile")

    @api.depends('debit', 'credit')
    def _compute_financial_amounts(self):
        for line in self:
            if line.date:
                date = line.date
            else:
                date = fields.Date.today()
            financial_amount = (line.currency_id and line.currency_id._convert(line.amount_currency, line.company_id.currency_id,
                                                                               line.company_id, date) or line.balance)
            financial_amount_residual = (line.currency_id and line.currency_id._convert(line.amount_residual_currency, line.company_id.currency_id,
                                                                                        line.company_id, date) or line.amount_residual)
            line.financial_amount = financial_amount
            line.financial_amount_residual = financial_amount_residual

    @api.model
    def _get_default_line_name(self, document, amount, currency, date, partner=None, payment_group_id=None):
        ''' Helper to construct a default label to set on journal items.

        E.g. Vendor Reimbursement $ 1,555.00 - Azure Interior - 05/14/2020.

        :param document:    A string representing the type of the document.
        :param amount:      The document's amount.
        :param currency:    The document's currency.
        :param date:        The document's date.
        :param partner:     The optional partner.
        :param payment_group_id:     The optional payment_group_id.
        :return:            A string.
        '''
        values = ['%s %s' % (document, formatLang(self.env, amount, currency_obj=currency))]
        if partner:
            values.append(partner.display_name)
        values.append(format_date(self.env, fields.Date.to_string(date)))
        if payment_group_id:
            if payment_group_id.partner_type == 'customer':
                text = "Recibo Nº" + payment_group_id.name
                values.append(text)
            else:
                text = "Orden de Pago Nº" + payment_group_id.name
                values.append(text)
        return ' - '.join(values)
