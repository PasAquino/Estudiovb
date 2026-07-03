# -*- coding: utf-8 -*-
from odoo import fields, models, exceptions, api
from datetime import datetime, timedelta, time
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare
from odoo.osv import expression
import time, collections
from lxml import etree
from odoo.exceptions import ValidationError


class WizardReportePagos(models.TransientModel):
    _name = 'wizard.reporte.pagos'
    _description = "Planilla de Pagos"

    desde = fields.Date(string="Fecha desde")
    hasta = fields.Date(string="Fecha hasta")
    tipo_archivo = fields.Selection([('xlsx', 'Excel'), ('pdf', 'PDF')])
    fecha_de_hoy = fields.Datetime(string='Fecha de hoy', default=lambda self: fields.datetime.now())
    receiptbook_id = fields.Many2one('account.payment.receiptbook', 'Talonario')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)

    def check_report(self):
        data = {}
        data['form'] = self.read(['desde', 'hasta'])[0]
        return self._print_report(data)

    def _print_report(self, data):
        data['form'].update(self.read(['desde', 'hasta', 'tipo_archivo', ])[0])
        return self.env.ref('py_ctrm_account_report.report_pagos_action').report_action(self, data)

    def agregar_punto_de_miles(self, numero):
        numero_con_punto = '.'.join(
            [str(int(numero))[::-1][i:i + 3] for i in range(0, len(str(int(numero))), 3)])[::-1]
        return numero_con_punto


class ReportePagos(models.AbstractModel):
    _name = 'report.py_ctrm_account_report.report_pagos_py'

    @api.model
    def _get_report_values(self, docids, data=None):
        Model = self.env.context.get('active_model')
        docs = self.env[Model].browse(self.env.context.get('active_id'))
        domain = []
        diccionario_recibos = collections.OrderedDict()
        dic_agrupados = collections.OrderedDict()

        if docs.desde and docs.hasta:
            domain += [('payment_date', '>=', docs.desde),
                       ('payment_date', '<=', docs.hasta),
                       ('partner_type', '=', 'supplier'),
                       ('company_id', '=', docs.company_id.id),
                       ('state', '=', 'posted')]

        if docs.receiptbook_id:
            domain += [('receiptbook_id', '=', docs.receiptbook_id.id)]
        orden = 'payment_date asc, name asc'
        pagos = self.env['account.payment.paraguay'].search(domain, order=orden)

        cobros = self.env['payment.methods.group'].search([('payment_group_id', 'in', pagos.ids)], order='payment_journal')

        lista_moneda = [moneda.currency_id.name for moneda in cobros]
        lista_moneda.sort()
        dic_diario = collections.OrderedDict()
        cobros1 = self.env['payment.methods.group'].search([('currency_id.name', '=', 'PYG'), ('payment_group_id', 'in', pagos.ids)]).sorted(lambda x: x.payment_journal.id)
        list_diarios1 = [cobro1.payment_journal for cobro1 in cobros1]
        list_diarios1.sort()
        list_diarios1 = list(set(list_diarios1))
        dic_diario1 = collections.OrderedDict()
        for diario1 in list_diarios1:
            suma1 = sum([cobro1.amount_payment for cobro1 in cobros1.filtered(lambda r: r.payment_journal.id == diario1.id)])
            dic_diario1.setdefault(diario1, suma1)
        dic_diario1 = dic_diario1.items()
        cobros2 = self.env['payment.methods.group'].search([('currency_id.name', '=', 'USD'),
                                                      ('payment_group_id', 'in', pagos.ids)]).sorted(lambda x: x.payment_journal.id)
        list_diarios2 = [cobro2.payment_journal for cobro2 in cobros2]
        list_diarios2.sort()
        list_diarios2 = list(set(list_diarios2))
        dic_diario2 = collections.OrderedDict()
        suma2 = 0
        for diario2 in list_diarios2:
            suma2 = sum([cobro2.amount_payment for cobro2 in cobros2.filtered(lambda r: r.payment_journal.id == diario2.id)])
            dic_diario2.setdefault(diario2, suma2)
        dic_diario2 = dic_diario2.items()
        lineas_asiento = self.env['payment.methods.group'].search([('payment_group_id', 'in', pagos.ids)])
        lineas_asiento = lineas_asiento.sorted(lambda x: x.id)
        lineas_cabecera = self.env['account.payment.paraguay'].search([('payment_date', '>=', docs.desde),
                                                                    ('payment_date', '<=', docs.hasta),
                                                                    ('state', '=', 'posted')]).sorted(lambda x: x.id)
        print(dic_agrupados.values())
        dic_agrupados = dic_agrupados.items()

        docargs = {
            'doc_ids': self.ids,
            'doc_model': Model,
            'docs': docs,
            'time': time,
            'dic_agrupados': dic_agrupados,
            'dic_diario': dic_diario,
            'dic_diario1': dic_diario1,
            'dic_diario2': dic_diario2,
            'lineas': lineas_asiento,
            'cabecera': lineas_cabecera,
            'pagos': pagos,
        }
        return docargs

    def setear_lista(self, dic, lista_tipo):
        """

        :param dic: diccionario con el contenido del recibo mas la lista de las sumas de sus tipos
        :param lista_tipo: lista de tipos que estan habilitados para el reporte
        :return: una lista del diccionario recibos y el sub-totalizador
        """

        lista_total_tipo = [0] * len(lista_tipo)
        for l in dic.values():
            lista_total_tipo = [a + b for (a, b) in zip(lista_total_tipo, l)]
        dic = dic.items()
        list_resul = [dic, lista_total_tipo]

        return list_resul
