from odoo import models, api, fields, _
from odoo.exceptions import ValidationError, UserError
from collections import defaultdict
import logging
from num2words import num2words

_logger = logging.getLogger(__name__)

MAP_PARTNER_TYPE_ACCOUNT_TYPE = {
    'customer': 'receivable',
    'supplier': 'payable',
}


class AccountPaymentParaguay(models.Model):
    _name = 'account.payment.paraguay'
    _description = 'Grupo de pago'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc, payment_date desc'

    name = fields.Char(compute='_compute_name', string='Referencia', store=True, index=True, tracking=True)
    document_number = fields.Char(string='Nro Documento', copy=False, readonly=True,
                                  states={'draft': [('readonly', False)]}, index=True)
    receiptbook_id = fields.Many2one('account.payment.receiptbook', 'Talonario', readonly=True, tracking=True,
                                     states={'draft': [('readonly', False)]}, ondelete='restrict')
    document_sequence_id = fields.Many2one(related='receiptbook_id.sequence_id')
    partner_id = fields.Many2one('res.partner', string='Cliente/Proveedor', required=True, readonly=True,
                                 states={'draft': [('readonly', False)]},
                                 tracking=True, change_default=True, index=True)
    partner_name = fields.Char('Cliente/Proveedor', related='partner_id.name', store=True)
    collection_user = fields.Many2one('res.users', string='Cobrador', help='Seleccione un cobrador',
                                      default=lambda self: self.env.user,
                                      states={'draft': [('readonly', False)]}, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda self: self.env.user.company_id.currency_id,
                                  readonly=True, states={'draft': [('readonly', False)]}, tracking=True)
    payment_date = fields.Date(string='Fecha de Pago', default=fields.Date.context_today, required=True, copy=False,
                               readonly=True,
                               states={'draft': [('readonly', False)]}, index=True, tracking=True)
    communication = fields.Char(string='Memo', readonly=True, states={'draft': [('readonly', False)]})
    nro_recibo = fields.Char(string='Recibo', readonly=True, states={'draft': [('readonly', False)]})
    partner_type = fields.Selection([('customer', 'Cliente'), ('supplier', 'Proveedor')], tracking=True,
                                    change_default=True)
    account_internal_type = fields.Char(compute='_compute_account_internal_type')
    state = fields.Selection([('draft', 'Borrador'),
                              ('to_approve', 'Aprobado'),
                              ('posted', 'Confirmado'),
                              ('cancel', 'Cancelada')], readonly=True, default='draft', copy=False, tracking=True,
                             string="Estado")
    payment_ids = fields.One2many('account.payment', 'payment_group_id', string='Lineas de Pago', ondelete='cascade',
                                  copy=False, readonly=True,
                                  states={'draft': [('readonly', False)]})
    payment_count = fields.Integer(string='Pagos', compute='_get_payments_generate', readonly=True)
    exchange_difference_count = fields.Integer(string='Diferencia de Cambio', compute='_get_exchange_difference_move',
                                               readonly=True)
    selected_financial_debt = fields.Monetary(string='Deuda Seleccionada', compute='_compute_selected_debt')
    selected_debt = fields.Monetary(string='Deuda Seleccionada', compute='_compute_selected_debt')
    unreconciled_amount = fields.Monetary(string='Ajuste / Adelanto', readonly=True,
                                          states={'draft': [('readonly', False)]})
    to_pay_amount = fields.Monetary(compute='_compute_to_pay_amount', inverse='_inverse_to_pay_amount',
                                    string='Monto a Pagar', readonly=True,
                                    states={'draft': [('readonly', False)]}, tracking=True)
    payments_amount = fields.Monetary(compute='_compute_payments_amount', inverse='_inverse_payments_amount',
                                      string='Monto', tracking=True)
    payments_amount_invoice = fields.Monetary(compute='_compute_payments_amount', inverse='_inverse_payments_amount',
                                              string='Monto')
    payments_amount_store = fields.Monetary(compute='_compute_payments_amount', string='Monto', store=True)
    payment_difference = fields.Monetary(compute='_compute_payment_difference', readonly=True,
                                         string="Diferencia en los Pagos",
                                         help="Diferencia entre la deuda seleccionada (o importe a pagar) y el importe de los pagos")
    matched_move_line_ids = fields.Many2many('account.move.line', compute='_compute_matched_move_line_ids',
                                             string='Lineas pagadas',
                                             help='Líneas que se han asociado a pagos, solo disponibles después de validación de pago')
    move_line_ids = fields.Many2many('account.move.line', compute='_compute_move_lines', readonly=True, copy=False)
    matched_amount = fields.Monetary(currency_field='currency_id')
    unmatched_amount = fields.Monetary(currency_field='currency_id')
    matched_amount_untaxed = fields.Monetary(currency_field='currency_id')
    invoices_payment_ids = fields.One2many('invoices.payment.paraguay', 'payment_group_id', string="Deudas",
                                           readonly=True,
                                           states={'draft': [('readonly', False)]})
    payment_methods_ids = fields.One2many('payment.methods.group', 'payment_group_id', string="Metodo de Pago",
                                          readonly=True,
                                          states={'draft': [('readonly', False)]})
    company_id = fields.Many2one('res.company', 'Compañia', required=True, index=True,
                                 default=lambda self: self.env.company)
    payment_methods = fields.Char(string='Métodos de Pago', compute='_compute_payment_methods',
                                  search='_search_payment_methods')
    payment_type = fields.Selection([('entry', 'Asientos'),
                                     ('invoice', 'Facturas')], default='invoice', string="Tipo",
                                    states={'draft': [('readonly', False)]})

    def unlink(self):
        for record in self:
            if record.state in ('to_approve', 'posted', 'cancel'):
                if record.state == 'to_approve':
                    raise UserError(_('Solo puede eliminar un pago en estado borrador'))
                elif record.state == 'posted':
                    raise UserError(_('Solo puede eliminar un pago en estado borrador'))
                else:
                    raise UserError(_('Solo puede eliminar un pago en estado borrador'))
            else:
                return super(AccountPaymentParaguay, self).unlink()

    @api.onchange('payment_type')
    def onchange_payment_type(self):
        for record in self:
            if record.state == 'draft':
                record.invoices_payment_ids = False

    def _compute_payment_methods(self):
        for rec in self:
            rec.payment_methods = ", ".join(rec.payment_ids.sudo().mapped('journal_id.name'))

    def _search_payment_methods(self, operator, value):
        recs = self.search([('payment_ids.journal_id.name', operator, value)])
        return [('id', 'in', recs.ids)]

    @api.depends('state', 'document_number')
    def _compute_name(self):
        for rec in self:
            _logger.info('Obtener el nombre del grupo de pago %s' % rec.id)
            if rec.state == 'posted':
                if rec.document_number:
                    name = ("%s%s" % ('', rec.document_number))
                else:
                    name = ', '.join(rec.payment_ids.mapped('name'))
            else:
                name = _('Pago en borrador')
            rec.name = name

    _sql_constraints = [('name_uniq', 'unique(document_number, receiptbook_id)',
                         'El número de documento debe ser único por talonario!')]

    def generar_texto(self, numero, moneda):
        if moneda == 2:
            new_number = round(numero, 2)
            nuevo_numero = str(new_number).split('.')
            entero = num2words(int(nuevo_numero[0]), lang='es').capitalize()
            if len(nuevo_numero[1]) == 1:
                if nuevo_numero[1] == '0':
                    decimal = num2words(int(nuevo_numero[1]), lang='es').capitalize()
                else:
                    decimal = num2words(int(nuevo_numero[1] + '0'), lang='es').capitalize()
            else:
                decimal = num2words(int(nuevo_numero[1]), lang='es').capitalize()
            letras = entero + ' con ' + decimal + ' Centavos'
        else:
            letras = num2words(numero, lang='es').capitalize()
        letras_return = letras
        return letras_return

    def action_create_payment(self):
        for rec in self:
            if rec.payment_methods_ids:
                amount_payment = 0
                amount_invoice = 0
                for eca in rec.payment_methods_ids:
                    amount_payment += eca.amount_payment
                for auxi in rec.invoices_payment_ids:
                    amount_invoice += auxi.amount_payment
                if round(amount_payment) != round(amount_invoice):
                    raise ValidationError(_('El monto de los pagos no coincide con los montos a pagar'))
                move_type = {'customer': 'inbound', 'supplier': 'outbound'}
                type_invoice = move_type[self.partner_type]
                for eca in rec.payment_methods_ids:
                    payment = self.env['account.payment'].create({
                        'date': eca.payment_date,
                        'ref': eca.communication,
                        'payment_group_id': rec.id,
                        'amount': eca.amount_payment,
                        'payment_type': type_invoice,
                        'tipo_cambio': eca.tipo_cambio,
                        'partner_id': rec.partner_id.id,
                        'partner_type': rec.partner_type,
                        'currency_id': eca.currency_id.id,
                        'journal_id': eca.payment_journal.id})
                return self.write({'state': 'to_approve'})
        else:
            raise UserError(_('Agregue las lineas de pagos antes de aprobar'))

    def action_cancel(self):
        for rec in self:
            rec.matched_move_line_ids.remove_move_reconcile()
            rec.payment_ids.action_cancel()
        self.write({'state': 'cancel'})

    @api.depends('payment_ids.invoice_line_ids')
    def _compute_move_lines(self):
        for rec in self:
            rec.move_line_ids = rec.payment_ids.mapped('invoice_line_ids')

    def _compute_matched_move_line_ids(self):
        for rec in self:
            lines = rec.move_line_ids.browse()
            payment_lines = rec.payment_ids.mapped('invoice_line_ids')
            reconciles = rec.env['account.partial.reconcile'].search([('credit_move_id', 'in', payment_lines.ids)])
            lines |= reconciles.mapped('debit_move_id')
            reconciles = rec.env['account.partial.reconcile'].search([('debit_move_id', 'in', payment_lines.ids)])
            lines |= reconciles.mapped('credit_move_id')
            rec.matched_move_line_ids = lines - payment_lines

    def action_draft(self):
        self.mapped('payment_ids').action_draft()
        self.mapped('payment_methods_ids').action_draft()
        self.mapped('payment_ids').unlink()
        return self.write({'state': 'draft'})

    def action_post(self):
        for rec in self:
            if not rec.document_number:
                if not rec.receiptbook_id.sequence_id:
                    raise UserError(
                        _('¡Error!. Defina la secuencia en los documentos relacionados con el talonario o establezca el número de documento.'))
                rec.document_number = (
                    rec.receiptbook_id.with_context(ir_sequence_date=rec.payment_date).sequence_id.next_by_id())
            invoices_payment = defaultdict(list)
            invoices_name = []
            account_difference = 0
            invoices_no_reconcile = []
            for eca in rec.invoices_payment_ids:
                if eca.invoice_id.amount_residual != eca.amount_payment:
                    invoices_no_reconcile.append(eca.invoice_id.name)
            for invoice in rec.invoices_payment_ids:
                account_id = invoice.invoice_id.mapped('line_ids').filtered(
                    lambda x: not x.reconciled and x.account_id.internal_type in ('payable', 'receivable'))
                if invoice.invoice_id.name in invoices_no_reconcile:
                    vals = {
                        'move_id': invoice.invoice_id.name,
                        'amount_payment': invoice.amount_payment,
                        'account_id': account_id.account_id.id,
                        'reconcile_invoice': invoice.invoice_id.id,
                    }
                    account_difference = account_id.account_id.id
                    if invoice.invoice_id.name not in invoices_name:
                        invoices_name.append(invoice.invoice_id.name)
                    invoices_payment[invoice.invoice_id.name].append(vals)
            if invoices_no_reconcile:
                for payment in rec.payment_ids:
                    line_ids = []
                    payment_line_ids = payment.move_id.line_ids.filtered(lambda x: x.partner_id == payment.partner_id)
                    payment_line_id = payment.line_ids.filtered(
                        lambda x: not x.reconciled and x.account_id.internal_type in ('payable', 'receivable'))
                    for line in payment_line_ids:
                        if line == payment_line_id:
                            line_ids.append(line.id)
                    if line_ids:
                        line_ids = list(set(line_ids))
                        payment.move_id.with_context(check_move_validity=False,
                                                     skip_account_move_synchronization=True).write(
                            {'line_ids': [(2, line) for line in line_ids]})
            reconcile_invoice = []
            for name in invoices_name:
                for invoice_vals in invoices_payment[name]:
                    for payment in rec.payment_ids:
                        if name not in reconcile_invoice:
                            reconcile_invoice.append(name)
                            payment_display_name = payment._prepare_payment_display_name()
                            default_line_name = self.env['account.move.line']._get_default_line_name(
                                _("Internal Transfer") if payment.is_internal_transfer else payment_display_name[
                                    '%s-%s' % (payment.payment_type, payment.partner_type)],
                                invoice_vals.get('amount_payment'),
                                payment.currency_id,
                                payment.date,
                                partner=payment.partner_id)
                            if payment.payment_group_id:
                                if payment.partner_type == 'customer':
                                    default_line_name = default_line_name + ' ' + str(rec.document_number)
                                else:
                                    default_line_name = default_line_name + ' ' + str(rec.document_number)
                            if payment.currency_id.name != 'PYG':
                                if payment.tipo_cambio:
                                    if payment.partner_type == 'supplier':
                                        debit = invoice_vals.get('amount_payment') * payment.tipo_cambio
                                        credit = 0
                                        amount_currency = invoice_vals.get('amount_payment')
                                    else:
                                        debit = 0
                                        credit = invoice_vals.get('amount_payment') * payment.tipo_cambio
                                        amount_currency = invoice_vals.get('amount_payment') * -1
                                else:
                                    if payment.partner_type == 'supplier':
                                        debit = payment.company_id.currency_id._convert(
                                            invoice_vals.get('amount_payment'),
                                            payment.currency_id,
                                            payment.company_id,
                                            payment.date,
                                        )
                                        credit = 0
                                        amount_currency = invoice_vals.get('amount_payment')
                                    else:
                                        debit = 0
                                        credit = payment.company_id.currency_id._convert(
                                            invoice_vals.get('amount_payment'),
                                            payment.currency_id,
                                            payment.company_id,
                                            payment.date,
                                        )
                                        amount_currency = invoice_vals.get('amount_payment') * -1
                            else:
                                if payment.partner_type == 'supplier':
                                    debit = invoice_vals.get('amount_payment')
                                    credit = 0
                                    amount_currency = invoice_vals.get('amount_payment')
                                else:
                                    debit = 0
                                    credit = invoice_vals.get('amount_payment')
                                    amount_currency = invoice_vals.get('amount_payment') * -1
                            line_vals_list = [{
                                'name': default_line_name,
                                'date_maturity': payment.date,
                                'amount_currency': amount_currency,
                                'currency_id': payment.currency_id.id,
                                'debit': debit,
                                'credit': credit,
                                'partner_id': payment.partner_id.id,
                                'account_id': invoice_vals.get('account_id'),
                                'reconcile_invoice': invoice_vals.get('reconcile_invoice'),
                                'partial_reconcile': True,
                            }]
                            for vals in line_vals_list:
                                vals.update({'move_id': payment.move_id.id})
                                payment.move_id.with_context(check_move_validity=False,
                                                             skip_account_move_synchronization=True).line_ids.create(
                                    vals)
            if invoices_no_reconcile:
                for payment in rec.payment_ids:
                    difference, debit, credit = 0, 0, 0
                    for line in payment.line_ids:
                        debit += line.debit
                        credit += line.credit
                        if payment.move_id.id == line.move_id.id:
                            difference = abs(debit - credit)
                    if difference != 0:
                        if payment.currency_id.name != 'PYG':
                            if payment.tipo_cambio:
                                if payment.partner_type == 'supplier':
                                    debit = difference
                                    credit = 0
                                    amount_currency = difference / payment.tipo_cambio
                                else:
                                    debit = 0
                                    credit = difference
                                    amount_currency = (difference * -1) / payment.tipo_cambio
                            else:
                                if payment.partner_type == 'supplier':
                                    debit = difference
                                    credit = 0
                                    amount_currency = payment.company_id.currency_id._convert(
                                        difference,
                                        payment.currency_id,
                                        payment.company_id,
                                        payment.date)
                                else:
                                    debit = 0
                                    credit = difference
                                    amount_currency = payment.company_id.currency_id._convert(
                                        difference,
                                        payment.currency_id,
                                        payment.company_id,
                                        payment.date) * -1
                        else:
                            if payment.partner_type == 'supplier':
                                debit = difference
                                credit = 0
                                amount_currency = difference
                            else:
                                debit = 0
                                credit = difference
                                amount_currency = difference * -1
                        payment_display_name = payment._prepare_payment_display_name()
                        default_line_name = self.env['account.move.line']._get_default_line_name(
                            _("Internal Transfer") if payment.is_internal_transfer else payment_display_name[
                                '%s-%s' % (payment.payment_type, payment.partner_type)], amount_currency,
                            payment.currency_id, payment.date,
                            partner=payment.partner_id)
                        if payment.payment_group_id:
                            if payment.partner_type == 'customer':
                                default_line_name = default_line_name + ' ' + str(rec.document_number)
                            else:
                                default_line_name = default_line_name + ' ' + str(rec.document_number)
                        line_vals_list = [{
                            'name': default_line_name,
                            'date_maturity': payment.date,
                            'amount_currency': amount_currency,
                            'currency_id': payment.currency_id.id,
                            'debit': debit,
                            'credit': credit,
                            'partner_id': payment.partner_id.id,
                            'account_id': account_difference,
                        }]
                        for vals in line_vals_list:
                            vals.update({'move_id': payment.move_id.id})
                            payment.move_id.with_context(check_move_validity=False,
                                                         skip_account_move_synchronization=True).line_ids.create(vals)
            rec.payment_ids.filtered(lambda x: x.state == 'draft').action_post()
            rec.payment_methods_ids.filtered(lambda x: x.state == 'draft').action_post()
            if rec.currency_id.name != 'PYG':
                invoice_liquidity = rec.invoices_payment_ids.invoice_id.mapped('line_ids').filtered(
                    lambda x: not x.reconciled and x.account_id.internal_type in ('payable', 'receivable'))
                invoice_liquidity = invoice_liquidity.sorted(lambda x: x.move_id.name in reconcile_invoice,
                                                             reverse=True)
                payment_counterpart_aml = rec.payment_ids.mapped('invoice_line_ids').filtered(
                    lambda x: not x.reconciled and x.account_id.internal_type in ('payable', 'receivable'))
                payment_counterpart_aml = payment_counterpart_aml.sorted(lambda x: x.reconcile_invoice, reverse=True)
                for liquidity in invoice_liquidity:
                    for counterpart_aml in payment_counterpart_aml:
                        if counterpart_aml.reconcile_invoice == liquidity.move_id:
                            (counterpart_aml + liquidity).reconcile()
                payment_counterpart_aml = rec.payment_ids.mapped('invoice_line_ids').filtered(
                    lambda x: not x.reconciled and x.account_id.internal_type in ('payable', 'receivable'))
                invoice_liquidity = rec.invoices_payment_ids.invoice_id.mapped('line_ids').filtered(
                    lambda x: not x.reconciled and x.account_id.internal_type in ('payable', 'receivable'))
                (payment_counterpart_aml + invoice_liquidity).reconcile()
            else:
                payment_counterpart_aml = rec.payment_ids.mapped('invoice_line_ids').filtered(
                    lambda x: not x.reconciled and x.account_id.internal_type in ('payable', 'receivable'))
                invoice_liquidity = rec.invoices_payment_ids.invoice_id.mapped('line_ids').filtered(
                    lambda x: not x.reconciled and x.account_id.internal_type in (
                        'payable', 'receivable') and x.move_id.name not in reconcile_invoice)
                (payment_counterpart_aml + invoice_liquidity).reconcile()
                invoice_liquidity = rec.invoices_payment_ids.invoice_id.mapped('line_ids').filtered(
                    lambda x: not x.reconciled and x.account_id.internal_type in ('payable', 'receivable'))
                invoice_liquidity = invoice_liquidity.sorted(lambda x: x.move_id.name in reconcile_invoice,
                                                             reverse=True)
                payment_counterpart_aml = rec.payment_ids.mapped('invoice_line_ids').filtered(
                    lambda x: not x.reconciled and x.account_id.internal_type in ('payable', 'receivable'))
                payment_counterpart_aml = payment_counterpart_aml.sorted(lambda x: x.reconcile_invoice, reverse=True)
                for liquidity in invoice_liquidity:
                    for counterpart_aml in payment_counterpart_aml:
                        if counterpart_aml.reconcile_invoice == liquidity.move_id:
                            (counterpart_aml + liquidity).reconcile()
            rec.write({'state': 'posted'})

    def button_journal_entries(self):
        return {
            'name': _('Artículos de diario'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move.line',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('payment_id', 'in', self.payment_ids.ids)],
        }

    @api.depends('partner_type')
    def _compute_account_internal_type(self):
        for rec in self:
            if rec.partner_type:
                rec.account_internal_type = MAP_PARTNER_TYPE_ACCOUNT_TYPE[rec.partner_type]

    @api.depends('invoices_payment_ids')
    def _get_exchange_difference_move(self):
        for rec in self:
            if rec.state == 'posted':
                difference_count = 0
                invoices = []
                exchange_move = []
                for eca in rec.invoices_payment_ids:
                    for auxi in eca.invoice_id:
                        if auxi not in invoices:
                            for ross in auxi.line_ids:
                                if ross.full_reconcile_id:
                                    if ross.full_reconcile_id.exchange_move_id:
                                        if ross.full_reconcile_id.exchange_move_id not in exchange_move:
                                            difference_count += 1
                                            invoices.append(auxi)
                                            exchange_move.append(ross.full_reconcile_id.exchange_move_id)
                rec.exchange_difference_count = difference_count
            else:
                rec.exchange_difference_count = 0

    def action_view_exchange_difference(self):
        invoices = []
        for rec in self:
            for eca in rec.invoices_payment_ids:
                for invoice in eca.invoice_id:
                    if invoice not in invoices:
                        for ross in invoice.line_ids:
                            if ross.full_reconcile_id:
                                invoices.append(ross.full_reconcile_id.exchange_move_id.id)
        # action = self.env.ref('account.action_move_journal_line').read()[0]
        # if len(invoices) > 0:
        #     action['domain'] = [('id', 'in', invoices)]
        # else:
        #     action = {'type': 'ir.actions.act_window_close'}
        # return action
        return {
            'name': _('Diferencia de Cambio'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', invoices)],
        }

    @api.depends('payment_ids')
    def _get_payments_generate(self):
        for order in self:
            payments = self.env['account.payment'].search([('payment_group_id', '=', order.id)])
            order.payment_count = len(payments)

    def action_view_payments_group(self):
        payments_ids = self.mapped('payment_ids')
        # action = self.env.ref('account.action_account_payments').read()[0]
        # if len(payments_ids) > 0:
        #     action['domain'] = [('id', 'in', payments_ids.ids)]
        # else:
        #     action = {'type': 'ir.actions.act_window_close'}
        # context = {'default_payment_group_id': self.id}
        # action['context'] = context
        # return action
        return {
            'name': _('Pagos'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.payment',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', payments_ids.ids)],
            'context': "{'default_payment_group_id': %d}" % (self.id)}

    @api.depends('payment_methods_ids.amount_payment')
    def _compute_payments_amount(self):
        for rec in self:
            rec.payments_amount = sum(rec.payment_methods_ids.mapped('amount_payment'))
            rec.payments_amount_store = sum(rec.payment_methods_ids.mapped('amount_payment'))
            rec.payments_amount_invoice = sum(rec.invoices_payment_ids.mapped('amount_payment'))

    @api.depends('payment_methods_ids.amount_payment')
    def _inverse_payments_amount(self):
        for rec in self:
            rec.payments_amount = sum(rec.payment_methods_ids.mapped('amount_payment'))
            rec.payments_amount_store = sum(rec.payment_methods_ids.mapped('amount_payment'))
            rec.payments_amount_invoice = sum(rec.invoices_payment_ids.mapped('amount_payment'))

    @api.depends('to_pay_amount', 'payments_amount')
    def _compute_payment_difference(self):
        for rec in self:
            rec.payment_difference = rec.payments_amount_invoice - rec.payments_amount

    @api.depends('selected_debt', 'unreconciled_amount')
    def _compute_to_pay_amount(self):
        for rec in self:
            rec.to_pay_amount = rec.payments_amount_invoice + rec.unreconciled_amount

    @api.onchange('to_pay_amount')
    def _inverse_to_pay_amount(self):
        for rec in self:
            rec.unreconciled_amount = rec.to_pay_amount - rec.payments_amount_invoice

    @api.depends('invoices_payment_ids.amount_payment')
    def _compute_selected_debt(self):
        for rec in self:
            selected_financial_debt = 0.0
            selected_debt = 0.0
            for line in rec.invoices_payment_ids:
                selected_financial_debt += line.amount_residual
                selected_debt += line.amount_residual
            rec.selected_financial_debt = selected_financial_debt
            rec.selected_debt = selected_debt

    def payment_print(self):
        for eca in self:
            if eca.partner_type == 'supplier':
                return self.env.ref('account_payment_paraguay.report_orden_pago_action').report_action(self)
            else:
                raise UserError(_('Aún no implementado'))


class BillsDueToPay(models.Model):
    _name = 'invoices.payment.paraguay'
    _description = 'Facturas Pagar o Cobrar'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    payment_group_id = fields.Many2one('account.payment.paraguay', 'Recibo', ondelete='cascade', readonly=True)
    partner_id = fields.Many2one(related='payment_group_id.partner_id', string='Partner')
    partner_type = fields.Selection(related='payment_group_id.partner_type')
    invoice_id = fields.Many2one('account.move', string="Factura")
    invoice_date = fields.Date(related='invoice_id.invoice_date', string='Fecha Factura')
    invoice_date_due = fields.Date(related='invoice_id.invoice_date_due', string='Fecha de Vencimiento')
    amount_total = fields.Monetary(related="invoice_id.amount_total", string='Total', store=True)
    amount_residual = fields.Monetary(related='invoice_id.amount_residual', string='Importe Adeudado', store=True)
    amount_residual_signed = fields.Monetary(related='invoice_id.amount_residual_signed',
                                             string='Importe Adeudado en la Moneda de la Empresa',
                                             store=True, currency_field='company_currency_id')
    amount_payment = fields.Monetary(string='Monto a Pagar', copy=False)
    currency_id = fields.Many2one('res.currency', string='Moneda')
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda de la Compañía',
                                          readonly=True, store=True, help='Utility field to express amount currency')
    company_id = fields.Many2one('res.company', 'Compañía', required=True, index=True,
                                 default=lambda self: self.env.company)

    @api.onchange('invoice_id')
    def invoice_id_change(self):
        if self.payment_group_id.payment_type == 'invoice':
            filter_invoice_ids = [data.invoice_id.id for data in self.payment_group_id.invoices_payment_ids]
            move_type = {'customer': 'out_invoice', 'supplier': 'in_invoice'}
            type_invoice = move_type[self.partner_type]
            values = {}
            values['domain'] = {'invoice_id': [('id', 'not in', filter_invoice_ids), ('amount_residual', '>', 0),
                                               ('partner_id', '=', self.partner_id.id), ('state', '=', 'posted'),
                                               ('company_id', '=', self.company_id.id), ('payment_state', '!=', 'paid'),
                                               ('move_type', '=', type_invoice)]}
            self.amount_payment = self.amount_residual
            return values
        else:
            filter_invoice_ids = [data.invoice_id.id for data in self.payment_group_id.invoices_payment_ids]
            move_type = {'customer': 'entry', 'supplier': 'entry'}
            type_invoice = move_type[self.partner_type]
            values = {}
            values['domain'] = {'invoice_id': [('id', 'not in', filter_invoice_ids),
                                               ('invoice_line_ids.partner_id', '=', self.partner_id.id),
                                               ('state', '=', 'posted'),
                                               ('company_id', '=', self.company_id.id),
                                               ('move_type', '=', type_invoice)]}
            self.amount_payment = self.amount_total
            return values


class PaymentMethodsGroup(models.Model):
    _name = 'payment.methods.group'
    _description = 'Métodos de Pagos'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    payment_group_id = fields.Many2one('account.payment.paraguay', 'Recibo', ondelete='cascade', readonly=True)
    partner_id = fields.Many2one(related='payment_group_id.partner_id', string='Partner', store=True)
    state = fields.Selection([('draft', 'Pendiente'), ('posted', 'Confirmado')], default="draft", string="Estado",
                             tracking=True)
    partner_type = fields.Selection(related='payment_group_id.partner_type', store=True)
    payment_date = fields.Date(string='Fecha de Pago', default=fields.Date.context_today)
    payment_journal = fields.Many2one('account.journal', string="Diario de Pago", tracking=True)
    amount_payment = fields.Monetary(string='Monto a Pagar', copy=False)
    currency_id = fields.Many2one('res.currency', string='Moneda', store=True, readonly=False,
                                  compute='_compute_currency_id')
    company_currency_id = fields.Many2one(related='company_id.currency_id', string='Moneda de la Compañía')
    check_deposit_id = fields.Many2one('account.checkbooks.deposit', string="Deposito de Cheque", copy=False)
    state_check = fields.Selection([('to_deposit', 'Pendiente a Depositar'), ('deposited', 'Depositado')],
                                   default="to_deposit", string="Estado de Cheque")
    bank_id = fields.Many2one('res.bank', 'Banco')
    cuenta_bank = fields.Many2one('res.partner.bank', string="Cuenta Bancaria")
    cheques_al_dia = fields.Boolean('Cheques al día')
    fecha_cobro = fields.Date(string='Fecha Emisión')
    fecha_diferida = fields.Date(string='Fecha Diferida')
    cheques_diferidos = fields.Boolean('Cheques Diferidos')
    cheques_tipo_pago = fields.Boolean('Cheques Tipo Pago')
    cheques_tipo_cobro = fields.Boolean('Cheque Tipo Cobro')
    detalle_cheque = fields.Char(string='Nro de Cheque')
    es_transferencia = fields.Boolean('Es una Transferencia?', default=False)
    detalle_transferencia = fields.Char(string='Nro de Transferencia')
    tipo_cambio = fields.Float(string='Tipo de Cambio', digits=(16, 2))
    account_bank_id = fields.Many2one('res.partner.bank', string="Cuenta Bancaria")
    communication = fields.Char(string='Memo', readonly=True, states={'draft': [('readonly', False)]})
    # tal_cheq = fields.Many2one('account.check.cheques')
    company_id = fields.Many2one('res.company', 'Compañía', required=True, index=True,
                                 default=lambda self: self.env.company)
    other_currency = fields.Boolean(compute='_compute_other_currency')
    exchange_rate = fields.Float(string='Tipo de Cambio', compute='_compute_exchange_rate', digits=(16, 2))
    amount_company_currency = fields.Monetary(string='Monto en la Moneda de la Empresa',
                                              compute='_compute_amount_company_currency',
                                              inverse='_inverse_amount_company_currency',
                                              currency_field='company_currency_id')
    force_amount_company_currency = fields.Monetary(string='Monto Forzado en la Moneda de la Empresa',
                                                    currency_field='company_currency_id',
                                                    copy=False)
    tal_cheq = fields.Many2one(
        'account.checkbooks')
    number_used = fields.Integer(string="Ultimo Número Utilizado")

    def action_post(self):
        for eca in self:
            eca.tal_cheq.number_used = eca.number_used
            eca.tal_cheq.current_number = eca.number_used + 1
            eca.write({'state': 'posted'})

    def action_draft(self):
        for eca in self:
            eca.write({'state': 'draft'})

    @api.depends('amount_payment', 'other_currency', 'force_amount_company_currency')
    def _compute_amount_company_currency(self):
        for rec in self:
            if not rec.other_currency:
                amount_company_currency = rec.amount_payment
            elif rec.force_amount_company_currency:
                amount_company_currency = rec.force_amount_company_currency
            else:
                amount_company_currency = rec.currency_id._convert(rec.amount_payment, rec.company_id.currency_id,
                                                                   rec.company_id, rec.payment_date)
            rec.amount_company_currency = amount_company_currency

    @api.onchange('amount_company_currency')
    def _inverse_amount_company_currency(self):
        for rec in self:
            if rec.other_currency and rec.amount_company_currency != rec.currency_id._convert(rec.amount_payment,
                                                                                              rec.company_id.currency_id,
                                                                                              rec.company_id,
                                                                                              rec.payment_date):
                force_amount_company_currency = rec.amount_company_currency
            else:
                force_amount_company_currency = False
            rec.force_amount_company_currency = force_amount_company_currency

    @api.depends('payment_journal')
    def _compute_currency_id(self):
        for pay in self:
            pay.currency_id = pay.payment_group_id.currency_id or pay.payment_journal.company_id.currency_id

    @api.depends('currency_id')
    def _compute_other_currency(self):
        for rec in self:
            rec.other_currency = False
            if rec.company_currency_id and rec.currency_id and rec.company_currency_id != rec.currency_id:
                rec.other_currency = True

    @api.depends('amount_payment', 'other_currency', 'amount_company_currency')
    def _compute_exchange_rate(self):
        for rec in self:
            if rec.other_currency:
                rec.exchange_rate = rec.amount_payment and (rec.amount_company_currency / rec.amount_payment) or 0.0
                rec.tipo_cambio = rec.exchange_rate
            else:
                rec.exchange_rate = False
                rec.tipo_cambio = False

    @api.onchange('tipo_cambio')
    def onchange_tipo_cambio(self):
        for rec in self:
            if rec.exchange_rate != rec.tipo_cambio:
                rec.amount_company_currency = rec.tipo_cambio * rec.amount_payment

    @api.onchange('currency_id')
    def _currency_onchange_payment(self):
        for payment in self:
            if payment.payment_group_id.currency_id != payment.currency_id:
                raise ValidationError(_('No puede seleccionar otro tipo de moneda distinta a su grupo de pago'))

    @api.onchange('payment_journal')
    def onchange_check_cheques_diferidos(self):
        for eca in self:
            if eca.es_transferencia is False:
                if eca.partner_type == 'supplier':
                    if eca.payment_journal:
                        if eca.payment_journal.type == 'bank' and (eca.payment_journal.cheques_diferidos is True\
                                or eca.payment_journal.cheques_al_dia is True):
                            if eca.payment_journal.cheques_tipo_pago is False:
                                raise ValidationError('El diario asignado no se encuentra\n'
                                                      'habilitado para pagos.\n'
                                                      'Favor verifique!')
                            if eca.payment_journal.bank_account_id:
                                if not eca.payment_journal.bank_account_id.acc_number:
                                    raise ValidationError('No tiene asignado una Chequera\n'
                                                          'Debe asignar en el Diario del cheque\n'
                                                          'Luego debe crear en Contabilidad / Cartera de Cheques')
                            if eca.payment_journal.cheques_diferidos is True:
                                eca.cheques_diferidos = eca.payment_journal.cheques_diferidos
                                eca.cheques_al_dia = eca.payment_journal.cheques_al_dia
                                eca.bank_id = eca.payment_journal.bank_account_id.bank_id.id
                                eca.cuenta_bank = eca.payment_journal.bank_account_id.id
                                eca.cheques_tipo_cobro = eca.payment_journal.cheques_tipo_cobro
                                eca.cheques_tipo_pago = eca.payment_journal.cheques_tipo_pago
                                eca.fecha_cobro = fields.date.today()
                            else:
                                eca.cheques_diferidos = eca.payment_journal.cheques_diferidos
                                eca.cheques_al_dia = eca.payment_journal.cheques_al_dia
                                eca.bank_id = eca.payment_journal.bank_account_id.bank_id
                                eca.cuenta_bank = eca.payment_journal.bank_account_id.id
                                eca.cheques_tipo_cobro = eca.payment_journal.cheques_tipo_cobro
                                eca.cheques_tipo_pago = eca.payment_journal.cheques_tipo_pago
                                eca.fecha_cobro = fields.date.today()
                else:
                    if eca.payment_journal:
                        if eca.payment_journal.cheques_diferidos is True:
                            eca.cheques_diferidos = eca.payment_journal.cheques_diferidos
                            eca.cheques_al_dia = eca.payment_journal.cheques_al_dia
                            eca.cheques_tipo_cobro = eca.payment_journal.cheques_tipo_cobro
                            eca.cheques_tipo_pago = eca.payment_journal.cheques_tipo_pago

                        else:
                            eca.cheques_diferidos = eca.payment_journal.cheques_diferidos
                            eca.cheques_al_dia = eca.payment_journal.cheques_al_dia
                            eca.cheques_tipo_cobro = eca.payment_journal.cheques_tipo_cobro
                            eca.cheques_tipo_pago = eca.payment_journal.cheques_tipo_pago

    @api.onchange('cuenta_bank')
    def onchange_cuenta(self):
        if self.es_transferencia is False:
            if self.payment_journal.type == 'bank' and (self.payment_journal.cheques_diferidos is True \
                    or self.payment_journal.cheques_al_dia is True) and self.payment_journal.cheques_tipo_pago is True:
                if self.cuenta_bank:
                    domain = [('company_id', '=', self.env.company.id),
                              ('cuenta_bank', '=', self.cuenta_bank.id),
                              ('bank_id', '=', self.bank_id.id),
                              ('active', '=', True),
                              ('active_state', '=', 'active')]
                    self.tal_cheq = self.env['account.checkbooks'].search(domain)

                    if self.partner_type == 'supplier' and not self.tal_cheq:
                        raise ValidationError('No Tiene Asignado una Chequera\n'
                                              'Debe crear en Contabilidad / Cartera de Cheques')

                    self.detalle_cheque = self.tal_cheq.current_number
                    proximo = self.tal_cheq.current_number

                    # chequear numero a validar es mayor que el maximo
                    if proximo > self.tal_cheq.number_end:
                        raise ValidationError(
                            _('La Chequera ya no es valido, el numero de documento '
                              'que quiere validar esta mas alla del rango.\n'
                              'El proximo numero de Cheque es %s mientras que el '
                              'rango de validez del Cheque es [%s - %s]') %
                            (proximo, self.tal_cheq.number_start,
                             self.tal_cheq.number_end))

                    # chequear numero a validar es menor que el minimo
                    if proximo < self.tal_cheq.number_start:
                        raise ValidationError(
                            _('La Chequera no es valido. Intenta validar un numero de '
                              'documento que es menor al minimo valido para esta '
                              'Chequera.\n'
                              'El proximo numero de la Chequera es %s mientras que el '
                              'rango de validez es [%s - %s]') %
                            (proximo, self.tal_cheq.number_start,
                             self.tal_cheq.number_end))

                    # numero a validar es igual al maximo, invalidar chequera
                    if proximo == self.tal_cheq.number_end:
                        self.tal_cheq.active_state = 'inactive'
                    self.number_used = int(self.detalle_cheque)


