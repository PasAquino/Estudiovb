# -*- coding: utf-8 -*-
from odoo import fields, models, exceptions, api
import time, collections
import io
from odoo.exceptions import ValidationError
import xlsxwriter
import logging
from datetime import date
from datetime import datetime

import xlsxwriter
from odoo import http, _
from odoo.http import request
from odoo.addons.web.controllers.main import serialize_exception, \
    content_disposition

_logger = logging.getLogger(__name__)
import werkzeug


class ReportAccountLedgerBook(models.TransientModel):
    _name = "account.ledger.book"

    periodo = fields.Integer(string="Nro Inicial")
    renumerar = fields.Boolean(default=False, string="Re Enumerar?", help="Marcar en caso que se requiera renumerar los asientos")
    account_ids = fields.Many2many('account.account', string="Cuentas a filtrar")
    tipo = fields.Selection([('xlsx', 'XLSX'), ('pdf', 'PDF')], string="Tipo de archivo", default='pdf')
    fecha_de_hoy = fields.Datetime(string='Fecha de hoy', default=fields.Datetime.now)
    fecha_inicio = fields.Date(string="Fecha desde")
    fecha_fin = fields.Date(string="Fecha hasta", default=fields.Date.today())
    company_id = fields.Many2one('res.company', 'Compañia', required=True, index=True, default=lambda self: self.env.company)
    check_rubricadas = fields.Boolean(string="Hoja Rubricada")

    @api.model
    def _get_default_company(self):
        return self.env.user.company_id.id

    @api.model
    def _get_default_accounts(self):
        accounts = self.env['account.account'].search(
            [('company_id', '=', self.env.user.company_id.id)])
        return accounts.mapped('id')

    def check_report(self):
        data = {}
        data['form'] = self.read(['periodo',
                                  'renumerar',
                                  'account_ids',
                                  'tipo'])[0]
        return self._print_report(data)

    def _print_report(self, data):
        data['form'].update(self.read(['periodo',
                                       'renumerar',
                                       'account_ids',
                                       'tipo'])[0])
        if self.tipo == 'pdf':
            return self.env.ref(
                'py_ctrm_account_report.'
                'report_libro_diario_id_new').report_action(
                self, data=data)
        else:
            return {
                'type': 'ir.actions.act_url',
                'url': '/getLibroMayor/' + str(self.id),
                'target': 'current'
            }

    def print_report_xlsx(self):
        data = {}
        data['form'] = self.read(['account_ids',
                                  'tipo'])[0]
        data['form'].update(self.read(['account_ids',
                                       'tipo'])[0])

        return self.env['report'].get_action(self,
                                             'py_ctrm_account_report.'
                                             'libro_mayor_paraguay_report_xlsx',
                                             data=data)

    def cantidad_cuenta(self, account_id):
        cantidad = self.env['account.move.line'].search_count(
            [('account_id', '=', account_id),
             ('move_id.date', '>=', self.fecha_inicio),
             ('move_id.date', '<=', self.fecha_fin)])
        return cantidad

    def agregar_punto_de_miles(self, numero):
        numero = round(numero)
        if numero >= 0:
            numero_con_punto = '.'.join(
                [str(int(numero))[::-1][i:i + 3] for i in
                 range(0, len(str(int(numero))), 3)])[::-1]
        else:
            numero *= -1
            numero_con_punto = '.'.join(
                [str(int(numero))[::-1][i:i + 3] for i in
                 range(0, len(str(int(numero))), 3)])[::-1]
            numero_con_punto = '-' + numero_con_punto
        num_return = numero_con_punto
        return num_return


class ReportLedgerBookPy(models.AbstractModel):
    _name = 'report.py_ctrm_account_report.account_ledger_book'

    def _get_report_values(self, docids, data=None):
        Model = self.env.context.get('active_model')
        docs = self.env[Model].browse(self.env.context.get('active_id'))
        if docs.account_ids:
            lineas_asiento = self.env['account.move.line'].search([
                ('move_id.date', '>=', docs.fecha_inicio),
                ('move_id.date', '<=', docs.fecha_fin),
                ('move_id.state', '=', 'posted'),
                ('account_id', 'in', docs.account_ids.mapped('id'))])
            lineas_asiento = lineas_asiento.sorted(
                key=lambda p: (p.account_id.code, p.move_id.date, p.move_id.id))
        else:
            accounts = self.env['account.account'].search(
                [('company_id', '=', self.env.user.company_id.id)])

            lineas_asiento = self.env['account.move.line'].search([
                ('move_id.date', '>=', docs.fecha_inicio),
                ('move_id.date', '<=', docs.fecha_fin),
                ('move_id.state', '=', 'posted'),
                ('account_id', 'in', accounts.ids)])
            lineas_asiento = lineas_asiento.sorted(
                key=lambda p: (p.account_id.code, p.move_id.date, p.move_id.id))
        docargs = {
            'doc_ids': self.ids,
            'doc_model': Model,
            'docs': docs,
            'time': time,
            'lineas': lineas_asiento
        }

        return docargs


class DownloadXLSPy(http.Controller):
    @http.route('/getLibroMayor/<int:id>', auth='public')
    def generarXLSX(self, id=None, **kw):
        record = request.env['account.ledger.book'].browse(id)
        i = 5
        fp = io.BytesIO()
        workbook = xlsxwriter.Workbook(fp, {'in_memory': True})
        lineas_asiento = request.env['account.move.line'].search([
            ('move_id.date', '>=', record.fecha_inicio),
            ('move_id.date', '<=', record.fecha_fin),
            ('move_id.state', '=', 'posted'),
            ('account_id', 'in', record.account_ids.mapped('id'))])
        lineas_asiento = lineas_asiento.sorted(
            key=lambda p: (p.account_id.code, p.move_id.date, p.move_id.id))
        sheet = workbook.add_worksheet('Libro Mayor')
        bold = workbook.add_format(
            {'bold': True, 'border': 1, 'align': 'center'})
        border = workbook.add_format({'border': 1})
        # Create a format to use in the merged range.
        merge_format = workbook.add_format({
            'bold': 1,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'fg_color': '#FFFAFA',
            'font_color': 'black'})
        merge_format1 = workbook.add_format({
            'bold': 1,
            'align': 'center',
            'valign': 'vcenter',
            'font_color': 'black'})

        sheet.merge_range('A1:B1', record.company_id.name, merge_format1)
        sheet.merge_range('A2:B2', record.company_id.vat, merge_format1)
        sheet.write(0, 4, 'Fecha', merge_format1)
        sheet.write(0, 5, record.fecha_de_hoy.strftime('%d-%m-%Y'),
                    merge_format1)
        sheet.write(1, 4, 'Hora', merge_format1)
        sheet.write(1, 5, record.fecha_de_hoy.strftime('%H:%M:%S'),
                    merge_format1)
        sheet.merge_range('A3:F3', 'LIBRO MAYOR', merge_format)
        sheet.write(3, 1, 'DEL', merge_format1)
        sheet.write(3, 2, record.fecha_inicio.strftime('%d-%m-%Y'),
                    merge_format1)
        sheet.write(3, 3, 'AL', merge_format1)
        sheet.write(3, 4, record.fecha_fin.strftime('%d-%m-%Y'),
                    merge_format1)
        sheet.set_column('A:F', 29)
        sheet.write(4, 0, 'Fecha Oper.', bold)
        sheet.write(4, 1, 'Ref.', bold)
        sheet.write(4, 2, 'Detalles', bold)
        sheet.write(4, 3, 'Debito', bold)
        sheet.write(4, 4, 'Credito', bold)
        sheet.write(4, 5, 'Saldos', bold)
        cuenta_actual = None
        debito_total = 0
        credito_total = 0
        saldo_total = 0
        saldo_cuenta = 0

        for l in lineas_asiento:
            if l.account_id != cuenta_actual:
                acumulador = 0
                acumulador = acumulador + 1
                debito_total = 0
                credito_total = 0
                saldo_cuenta = 0
                i = i + 1
                cuenta_actual = l.account_id
                sheet.write(i, 1, l.account_id.code, merge_format1)
                sheet.write(i, 2, l.account_id.name, merge_format1)
                i = i + 1
                sheet.write(i, 0, l.move_id.date.strftime('%d-%m-%Y'))
                sheet.write(i, 1, l.move_id.num_asiento)
                sheet.write(i, 2, l.name)
                sheet.write(i, 3, record.agregar_punto_de_miles(l.debit))
                sheet.write(i, 4, record.agregar_punto_de_miles(l.credit))
                saldo_cuenta = saldo_cuenta + l.balance
                sheet.write(i, 5, record.agregar_punto_de_miles(saldo_cuenta))
                debito_total = l.debit + debito_total
                credito_total = l.credit + credito_total
                i = i + 1
            else:
                acumulador = acumulador + 1
                sheet.write(i, 0, l.move_id.date.strftime('%d-%m-%Y'))
                sheet.write(i, 1, l.move_id.num_asiento)
                sheet.write(i, 2, l.name)
                sheet.write(i, 3, record.agregar_punto_de_miles(l.debit))
                sheet.write(i, 4, record.agregar_punto_de_miles(l.credit))
                saldo_cuenta = saldo_cuenta + l.balance
                sheet.write(i, 5, record.agregar_punto_de_miles(saldo_cuenta))
                debito_total = l.debit + debito_total
                credito_total = l.credit + credito_total
                i = i + 1
                if acumulador == record.cantidad_cuenta(l.account_id.id):
                    sheet.write(i, 2, 'TOTALES:', merge_format1)
                    sheet.write(i, 3,
                                record.agregar_punto_de_miles(debito_total),
                                merge_format1)
                    sheet.write(i, 4,
                                record.agregar_punto_de_miles(credito_total),
                                merge_format1)
                    sheet.write(i, 5,
                                record.agregar_punto_de_miles(saldo_cuenta),
                                merge_format1)
                    i = i + 1

        # sheet.write(i, 2, 'TOTALES:', merge_format1)
        # sheet.write(i, 3, record.agregar_punto_de_miles(debito_total),
        #            merge_format1)
        # sheet.write(i, 4, record.agregar_punto_de_miles(credito_total),
        #                        merge_format1)
        # sheet.write(i, 5,
        #            record.agregar_punto_de_miles(saldo_cuenta))
        workbook.close()
        fp.seek(0)
        return request.make_response(fp.read(),
                                     [('Content-Type',
                                       'application/vnd.'
                                       'openxmlformats-officedocument.'
                                       'spreadsheetml.sheet'),
                                      ('Content-Disposition',
                                       content_disposition(
                                           'libro_mayor.xlsx'))])
