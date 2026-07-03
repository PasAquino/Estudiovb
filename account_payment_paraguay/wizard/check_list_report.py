# -*- coding: utf-8 -*-
from odoo import fields, models, exceptions, api
import time, collections
import io, datetime
from odoo.exceptions import ValidationError
import xlsxwriter
import logging
from datetime import date

import base64
import xlwt
import base64
import xlsxwriter
from io import StringIO
from odoo import http, _
from odoo.http import request
from odoo.addons.web.controllers.main import serialize_exception, content_disposition

_logger = logging.getLogger(__name__)
import werkzeug


class CheckListReport(models.TransientModel):
    _name = "check.list.wizard"

    date_end = fields.Date(string="Fecha Desde")
    date_start = fields.Date(string="Fecha Desde")
    detalle_cheque = fields.Char(string='Nro de Cheque')
    bank_id = fields.Many2one('res.bank', string='Banco')
    partner_id = fields.Many2one('res.partner', string='Empresa')
    collection_user = fields.Many2one('res.users', string='Cobrador')
    date_today = fields.Datetime(string='Fecha de hoy', default=lambda self: fields.datetime.now())
    company_id = fields.Many2one('res.company', 'Compañía', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string="Moneda", default=lambda self: self._get_default_currency_id())
    journal_id = fields.Many2one('account.journal', string='Diario',
                                 domain=[('type', '=', 'bank'), ('bank_account_id', '=', False), ('diario_de_cheques', '=', True)])
    tipo = fields.Selection([('xlsx', 'XLSX'), ('pdf', 'PDF')], string="Tipo de archivo", default='pdf')
    check_type = fields.Selection([('cheques_tipo_pago', 'Cheques Pagados'),
                                   ('cheques_tipo_cobro', 'Cheques Cobrados'),
                                   ('to_deposit', 'Cheques Pendiente a Depositar'),
                                   ('deposited', 'Cheques Depositado')], string="Tipo de Cheque")

    @api.model
    def _get_default_currency_id(self):
        company_id = self.env.user.company_id
        currency_id = company_id.currency_id
        return currency_id

    @api.onchange('journal_id')
    def onchange_journal_id(self):
        if self.journal_id:
            if self.journal_id.currency_id:
                self.currency_id = self.journal_id.currency_id
            else:
                self.currency_id = self.journal_id.company_id.currency_id

    def check_report(self):
        data = {}
        data['form'] = self.read(['check_type', 'tipo'])[0]
        return self._print_report(data)

    def _print_report(self, data):
        data['form'].update(self.read(['check_type', 'tipo'])[0])
        if self.tipo == 'pdf':
            return self.env.ref('account_payment_paraguay.report_listado_cheques_action').report_action(self, data=data)
        else:
            return {
                'type': 'ir.actions.act_url',
                'url': '/getCheques/' + str(self.id),
                'target': 'current'
            }

    def agregar_punto_de_miles(self, numero):
        numero_con_punto = '.'.join([str(int(numero))[::-1][i:i + 3] for i in range(0, len(str(int(numero))), 3)])[::-1]
        num_return = numero_con_punto
        return num_return


class ReportCheckBook(models.AbstractModel):
    _name = 'report.account_payment_paraguay.template_check_list'

    def _get_report_values(self, docids, data=None):
        model = self.env.context.get('active_model')
        docs = self.env[model].browse(self.env.context.get('active_id'))
        domain = []
        cheques_depositados = []
        cheques_no_depositado = []

        domain += [('payment_date', '>=', docs.date_start),
                   ('payment_date', '<=', docs.date_end),
                   ('state', '=', 'posted'),
                   ('payment_journal.diario_de_cheques', '=', True),
                   ('company_id', '=', docs.company_id.id)]

        if docs.check_type == 'cheques_tipo_pago':
            domain += [('partner_type', '=', 'supplier')]
        if docs.check_type == 'cheques_tipo_cobro':
            domain += [('partner_type', '=', 'customer')]
        if docs.check_type == 'to_deposit':
            domain += [('state_check', '=', 'to_deposit'),
                       ('partner_type', '=', 'customer')]
        if docs.check_type == 'deposited':
            domain += [('state_check', '=', 'deposited'),
                       ('partner_type', '=', 'customer')]
        if docs.partner_id:
            domain += [('partner_id', '=', docs.partner_id)]
        if docs.detalle_cheque:
            domain += [('detalle_cheque', '=', docs.detalle_cheque)]
        if docs.bank_id:
            domain += [('bank_id', '=', docs.bank_id.id)]
        if docs.journal_id:
            domain += [('payment_journal', '=', docs.journal_id.id)]
        if docs.currency_id:
            domain += [('currency_id', '=', docs.currency_id.id)]

        listado_cheques = self.env['payment.methods.group'].search(domain)

        if docs.check_type == 'deposited':
            cheques_depositados = self.env['account.checkbooks.deposit'].search([('id', 'in', listado_cheques.check_deposit_id.ids),
                                                                                 ('state', '=', 'posted'),
                                                                                 ('deposit_date', '>=', docs.date_start),
                                                                                 ('deposit_date', '<=', docs.date_end)])

        if docs.check_type == 'to_deposit':
            cheques_no_depositado = self.env['account.checkbooks.deposit'].search([('id', 'in', listado_cheques.check_deposit_id.ids),
                                                                                   ('state', '=', 'posted'),
                                                                                   ('deposit_date', '>=', docs.date_start),
                                                                                   ('deposit_date', '<=', docs.date_end)])

        docargs = {
            'doc_ids': self.ids,
            'doc_model': model,
            'docs': docs,
            'time': time,
            'listado_cheques': listado_cheques,
            'cheques_depositados': cheques_depositados,
            'cheques_no_depositado': cheques_no_depositado,
        }
        return docargs
