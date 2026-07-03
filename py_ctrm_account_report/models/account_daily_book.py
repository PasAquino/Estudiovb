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


class WizardReportDailyBook(models.TransientModel):
    _name = "daily.book.wizard"

    periodo = fields.Integer(string="Periodo")
    renumerar = fields.Boolean(default=False, string="Re Enumerar?", help="Marcar en caso que se requiera renumerar los asientos")
    journal_ids = fields.Many2many('account.journal', string="Diarios")
    tipo = fields.Selection([('xlsx', 'XLSX'), ('pdf', 'PDF')], string="Tipo de archivo", default='pdf')
    fecha_de_hoy = fields.Datetime(string='Fecha de hoy', default=lambda self: fields.datetime.now())
    fecha_inicio = fields.Date(string="Fecha desde")
    fecha_fin = fields.Date(string="Fecha hasta", default=fields.Date.today())
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    check_rubricadas = fields.Boolean(string="Hoja Rubricada")

    @api.model
    def _get_default_company(self):
        return self.env.user.company_id.id

    @api.model
    def _get_default_journals(self):
        journals = self.env['account.journal'].search([
            ('company_id', '=', self.env.user.company_id.id)])
        return journals.mapped('id')

    def check_report(self):
        data = {}
        data['form'] = self.read(['periodo',
                                  'renumerar',
                                  'journal_ids',
                                  'tipo'])[0]
        return self._print_report(data)

    def _print_report(self, data):
        data['form'].update(self.read(['periodo',
                                       'renumerar',
                                       'journal_ids',
                                       'tipo'])[0])
        if self.tipo == 'pdf':
            return self.env.ref(
                'py_ctrm_account_report.'
                'report_libro_diario_id').report_action(
                self, data=data)
        else:
            return {
                'type': 'ir.actions.act_url',
                'url': '/getLibroDiario/' + str(self.id),
                'target': 'current'
            }

    def print_report_xlsx(self):
        data = {}
        data['form'] = self.read(['periodo',
                                  'renumerar',
                                  'journal_ids',
                                  'tipo'])[0]
        data['form'].update(self.read(['periodo',
                                       'renumerar',
                                       'journal_ids',
                                       'tipo'])[0])

        return self.env['report'].get_action(self,
                                             'py_ctrm_account_report.'
                                             'libro_diario_paraguay_report_xlsx',
                                             data=data)

    def agregar_punto_de_miles(self, numero):
        numero_con_punto = '.'.join([str(int(numero))[::-1][i:i + 3] for i in
                                     range(0, len(str(int(numero))), 3)])[::-1]
        num_return = numero_con_punto
        return num_return

    def transporte(self, columna):
        total = 0
        for e in columna(range(20)):
            total = total + e
            return total

    def sumalista(self, listaNumeros):
        laSuma = 0
        for i in listaNumeros:
            laSuma = laSuma + i
        return laSuma


class ReportDailyBook(models.AbstractModel):
    _name = 'report.py_ctrm_account_report.daily_book'

    def _get_report_values(self, docids, data=None):
        Model = self.env.context.get('active_model')
        docs = self.env[Model].browse(self.env.context.get('active_id'))

        if docs.journal_ids:
            lineas_asiento = self.env['account.move.line'].search(
                [('move_id.date', '>=', docs.fecha_inicio),
                 ('move_id.date', '<=', docs.fecha_fin),
                 ('move_id.state', '=', 'posted'),
                 ('move_id.company_id', '=', docs.company_id.id),
                 ('journal_id', 'in', docs.journal_ids.mapped('id'))])
        else:
            journals = self.env['account.journal'].search([
                ('company_id', '=', self.env.user.company_id.id)])

            lineas_asiento = self.env['account.move.line'].search(
                [('move_id.date', '>=', docs.fecha_inicio),
                 ('move_id.date', '<=', docs.fecha_fin),
                 ('move_id.state', '=', 'posted'),
                 ('move_id.company_id', '=', docs.company_id.id),
                 ('journal_id', 'in', journals.ids)])

        if docs.renumerar:
            if len(lineas_asiento) > 0:
                lineas_asiento[0].move_id.renumerar_asientos(docs.periodo, docs.company_id.id)
                lineas_asiento = lineas_asiento.sorted(
                    lambda x: x.move_id.num_asiento)

        docargs = {
            'doc_ids': self.ids,
            'doc_model': Model,
            'docs': docs,
            'time': time,
            'lineas': lineas_asiento
        }

        return docargs


class DownloadXLS(http.Controller):
    @http.route('/getLibroDiario/<int:id>', auth='public')
    def generarXLSX(self, id=None, **kw):
        record = request.env['daily.book.wizard'].browse(id)
        move_actual = None
        i = 5
        fp = io.BytesIO()
        workbook = xlsxwriter.Workbook(fp, {'in_memory': True})
        lineas_asiento = request.env['account.move.line'].search(
            [('move_id.date', '>=', record.fecha_inicio),
             ('move_id.date', '<=', record.fecha_fin),
             ('move_id.state', '=', 'posted'),
             ('move_id.company_id', '=', record.company_id.id),
             ('journal_id', 'in', record.journal_ids.mapped('id'))])
        lineas_asiento = lineas_asiento.sorted(
            key=lambda x: x.move_id.num_asiento)
        if record.renumerar:
            if len(lineas_asiento) > 0:
                lineas_asiento[0].move_id.renumerar_asientos(record.periodo, record.company_id.id)
        sheet = workbook.add_worksheet('Libro Diario')
        bold = workbook.add_format(
            {'bold': True, 'fg_color': 'white', 'align': 'center',
             'border': 1})
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
        sheet.write(0, 5, 'Fecha', merge_format1)
        sheet.write(0, 6, record.fecha_de_hoy.strftime('%d-%m-%Y'),
                    merge_format1)
        sheet.write(1, 5, 'Hora', merge_format1)
        sheet.write(1, 6, record.fecha_de_hoy.strftime('%H:%M:%S'),
                    merge_format1)
        sheet.merge_range('A3:G3', 'LIBRO DIARIO', merge_format)
        sheet.write(3, 1, 'DEL', merge_format1)
        sheet.write(3, 2, record.fecha_inicio.strftime('%d-%m-%Y'),
                    merge_format1)
        sheet.write(3, 4, 'AL', merge_format1)
        sheet.write(3, 5, record.fecha_fin.strftime('%d-%m-%Y'),
                    merge_format1)
        sheet.set_column('A:G', 27)
        sheet.write(4, 0, 'Asiento', bold)
        sheet.write(4, 1, 'Fecha', bold)
        sheet.write(4, 2, 'Codigo', bold)
        sheet.write(4, 3, 'Cuenta', bold)
        sheet.write(4, 4, 'Concepto', bold)
        sheet.write(4, 5, 'Débito', bold)
        sheet.write(4, 6, 'Crédito', bold)

        debito_total = 0
        credito_total = 0

        for l in lineas_asiento:
            if l.move_id != move_actual:
                move_actual = l.move_id
                sheet.write(i, 0, l.move_id.num_asiento)
                sheet.write(i, 1, l.move_id.date.strftime('%d-%m-%Y'))
                sheet.write(i, 2, l.account_id.code)
                sheet.write(i, 3, l.account_id.name)
                sheet.write(i, 4, l.name)
                sheet.write(i, 5, record.agregar_punto_de_miles(l.debit))
                sheet.write(i, 6, record.agregar_punto_de_miles(l.credit))
                debito_total = l.debit + debito_total
                credito_total = l.credit + credito_total
            else:
                sheet.write(i, 2, l.account_id.code)
                sheet.write(i, 3, l.account_id.name)
                sheet.write(i, 4, l.name)
                sheet.write(i, 5, record.agregar_punto_de_miles(l.debit))
                sheet.write(i, 6, record.agregar_punto_de_miles(l.credit))
                debito_total = l.debit + debito_total
                credito_total = l.credit + credito_total
            i = i + 1
        sheet.write(i, 3, 'TOTAL GENERAL:', merge_format1)
        sheet.write(i, 5, record.agregar_punto_de_miles(debito_total),
                    merge_format1)
        sheet.write(i, 6, record.agregar_punto_de_miles(credito_total),
                    merge_format1)
        workbook.close()
        fp.seek(0)
        return request.make_response(fp.read(),
                                     [('Content-Type',
                                       'application/vnd.'
                                       'openxmlformats-officedocument.'
                                       'spreadsheetml.sheet'),
                                      ('Content-Disposition',
                                       content_disposition(
                                           'libro_diario.xlsx'))])
