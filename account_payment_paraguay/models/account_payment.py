from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    payment_group_id = fields.Many2one('account.payment.paraguay', 'Recibo', ondelete='cascade', readonly=True)
    payment_group_company_id = fields.Many2one(related='payment_group_id.company_id', string='Compañía del grupo de pago')
    journal_ids = fields.Many2many('account.journal', compute='_compute_journals')
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda de la Compañía', )
    amount_company_currency = fields.Monetary(string='Monto en la Moneda de la Empresa', compute='_compute_amount_company_currency',
                                              inverse='_inverse_amount_company_currency', currency_field='company_currency_id')
    signed_amount = fields.Monetary(string='Monto', compute='_compute_signed_amount')
    signed_amount_company_currency = fields.Monetary(string='Monto del Pago en la Moneda de la Empresa', compute='_compute_signed_amount',
                                                     currency_field='company_currency_id')
    force_amount_company_currency = fields.Monetary(string='Monto Forzado en la Moneda de la Empresa', currency_field='company_currency_id',
                                                    copy=False)
    other_currency = fields.Boolean(compute='_compute_other_currency')
    tipo_cambio = fields.Float(string='Tipo de Cambio', digits=(16, 2))
    exchange_rate = fields.Float(string='Tipo de Cambio', compute='_compute_exchange_rate', digits=(16, 4))

    @api.depends('amount', 'other_currency', 'amount_company_currency')
    def _compute_exchange_rate(self):
        for rec in self:
            if rec.other_currency:
                if rec.tipo_cambio:
                    rec.exchange_rate = rec.tipo_cambio
                else:
                    rec.exchange_rate = rec.amount and (rec.amount_company_currency / rec.amount) or 0.0
                    rec.tipo_cambio = rec.exchange_rate
            else:
                rec.exchange_rate = False
                rec.tipo_cambio = False

    @api.depends('currency_id')
    def _compute_other_currency(self):
        for rec in self:
            rec.other_currency = False
            if rec.company_currency_id and rec.currency_id and rec.company_currency_id != rec.currency_id:
                rec.other_currency = True

    @api.depends('payment_type')
    def _compute_journals(self):
        for rec in self:
            rec.journal_ids = rec.journal_ids.search(rec.get_journals_domain())

    def get_journals_domain(self):
        self.ensure_one()
        domain = [('type', 'in', ('bank', 'cash'))]
        return domain

    @api.depends('amount', 'payment_type', 'partner_type', 'amount_company_currency')
    def _compute_signed_amount(self):
        for rec in self:
            sign = 1.0
            if (rec.partner_type == 'supplier' and rec.payment_type == 'inbound') or (
                    rec.partner_type == 'customer' and rec.payment_type == 'outbound'):
                sign = -1.0
            rec.signed_amount = rec.amount and rec.amount * sign
            rec.signed_amount_company_currency = (rec.amount_company_currency and rec.amount_company_currency * sign)

    @api.depends('amount', 'other_currency', 'force_amount_company_currency')
    def _compute_amount_company_currency(self):
        """
        * Si las monedas son iguales devuelve 1
        * si no, si hay force_amount_company_currency, devuelve ese valor
        * sino, devuelve el amount convertido a la moneda de la cia
        """
        for rec in self:
            if not rec.other_currency:
                amount_company_currency = rec.amount
            elif rec.force_amount_company_currency:
                amount_company_currency = rec.force_amount_company_currency
            else:
                if rec.tipo_cambio:
                    amount_company_currency = rec.amount * rec.tipo_cambio
                else:
                    amount_company_currency = rec.currency_id._convert(rec.amount, rec.company_id.currency_id, rec.company_id, rec.date)
            rec.amount_company_currency = amount_company_currency

    @api.onchange('amount_company_currency')
    def _inverse_amount_company_currency(self):
        for rec in self:
            if rec.other_currency and rec.amount_company_currency != rec.currency_id._convert(rec.amount, rec.company_id.currency_id, rec.company_id,
                                                                                              rec.date):
                force_amount_company_currency = rec.amount_company_currency
            else:
                force_amount_company_currency = False
            rec.force_amount_company_currency = force_amount_company_currency

    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        ''' Prepare the dictionary to create the default account.move.lines for the current payment.
        :param write_off_line_vals: Optional dictionary to create a write-off account.move.line easily containing:
            * amount:       The amount to be added to the counterpart amount.
            * name:         The label to set on the line.
            * account_id:   The account on which create the write-off.
        :return: A list of python dictionary to be passed to the account.move.line's 'create' method.
        '''
        self.ensure_one()
        write_off_line_vals = write_off_line_vals or {}

        if not self.outstanding_account_id:
            raise UserError(_(
                "You can't create a new payment without an outstanding payments/receipts account set either on the company or the %s payment method in the %s journal.",
                self.payment_method_line_id.name, self.journal_id.display_name))

        # Compute amounts.
        write_off_amount_currency = write_off_line_vals.get('amount', 0.0)

        if self.payment_type == 'inbound':
            # Receive money.
            liquidity_amount_currency = self.amount
        elif self.payment_type == 'outbound':
            # Send money.
            liquidity_amount_currency = -self.amount
            write_off_amount_currency *= -1
        else:
            liquidity_amount_currency = write_off_amount_currency = 0.0

        write_off_balance = self.currency_id._convert(
            write_off_amount_currency,
            self.company_id.currency_id,
            self.company_id,
            self.date,
        )
        liquidity_balance = self.currency_id._convert(
            liquidity_amount_currency,
            self.company_id.currency_id,
            self.company_id,
            self.date,
        )
        if self.tipo_cambio:
            liquidity_balance = liquidity_amount_currency * self.tipo_cambio
        counterpart_amount_currency = -liquidity_amount_currency - write_off_amount_currency
        counterpart_balance = -liquidity_balance - write_off_balance
        currency_id = self.currency_id.id

        if self.is_internal_transfer:
            if self.payment_type == 'inbound':
                liquidity_line_name = _('Transfer to %s', self.journal_id.name)
            else:  # payment.payment_type == 'outbound':
                liquidity_line_name = _('Transfer from %s', self.journal_id.name)
        else:
            liquidity_line_name = self.payment_reference

        # Compute a default label to set on the journal items.

        payment_display_name = self._prepare_payment_display_name()

        default_line_name = self.env['account.move.line']._get_default_line_name(
            _("Internal Transfer") if self.is_internal_transfer else payment_display_name['%s-%s' % (self.payment_type, self.partner_type)],
            self.amount,
            self.currency_id,
            self.date,
            partner=self.partner_id,
        )
        if self.payment_group_id:
            if self.payment_group_id.partner_type == 'customer':
                default_line_name = default_line_name + ' ' + str(self.payment_group_id.document_number)
            else:
                default_line_name = default_line_name + ' ' + str(self.payment_group_id.document_number)
        line_vals_list = [
            # Liquidity line.
            {
                'name': liquidity_line_name or default_line_name,
                'date_maturity': self.date,
                'amount_currency': liquidity_amount_currency,
                'currency_id': currency_id,
                'debit': liquidity_balance if liquidity_balance > 0.0 else 0.0,
                'credit': -liquidity_balance if liquidity_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.outstanding_account_id.id,
            },
            # Receivable / Payable.
            {
                'name': self.payment_reference or default_line_name,
                'date_maturity': self.date,
                'amount_currency': counterpart_amount_currency,
                'currency_id': currency_id,
                'debit': counterpart_balance if counterpart_balance > 0.0 else 0.0,
                'credit': -counterpart_balance if counterpart_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': self.destination_account_id.id,
            },
        ]
        if not self.currency_id.is_zero(write_off_amount_currency):
            # Write-off line.
            line_vals_list.append({
                'name': write_off_line_vals.get('name') or default_line_name,
                'amount_currency': write_off_amount_currency,
                'currency_id': currency_id,
                'debit': write_off_balance if write_off_balance > 0.0 else 0.0,
                'credit': -write_off_balance if write_off_balance < 0.0 else 0.0,
                'partner_id': self.partner_id.id,
                'account_id': write_off_line_vals.get('account_id'),
            })
        return line_vals_list
