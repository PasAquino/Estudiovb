# -*- coding: utf-8 -*-
from odoo import fields, models, exceptions, api
from datetime import datetime, timedelta, time
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare
from odoo.osv import expression
import time, collections
from lxml import etree
from odoo.exceptions import ValidationError


class WizardReporteCobranzas(models.TransientModel):
    _name = 'report.cobranzas.py'

    desde = fields.Date(string="Fecha desde")
    hasta = fields.Date(string="Fecha hasta")
    cobrador = fields.Many2one('res.users', 'Cobrador')
    moneda = fields.Many2one('res.currency', string='Moneda', readonly=True)
    orden = fields.Selection([('fecha', 'Fecha'), ('cobrador', 'Cobrador')], default='fecha')
    tipo_archivo = fields.Selection([('xlsx', 'Excel'), ('pdf', 'PDF')])
    filtro_caja = fields.Boolean()
    filtro_cobranza = fields.Boolean()
    talonario_id = fields.Many2one('account.journal')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    cliente = fields.Many2one('res.partner', 'Cliente')
    detalle_factura = fields.Boolean(default=True)
    agrupar = fields.Selection([('collection_user', 'Cobrador'), ('currency_id', 'Moneda')], default='collection_user')
    estado = fields.Selection([('state', 'Cancelado')])
    invoice_payment_term_id = fields.Selection([('Contado', 'Contado'), ('Credito', 'Credito')], string='Condición de Pago')
    fecha_de_hoy = fields.Datetime(string='Fecha de hoy', default=lambda self: fields.datetime.now())

    def check_report(self):
        data = {}
        data['form'] = self.read(['desde', 'hasta', 'cobrador', 'moneda'])[0]
        return self._print_report(data)

    def _print_report(self, data):
        data['form'].update(self.read(['desde', 'hasta', 'cobrador', 'tipo_archivo', 'orden', 'moneda'])[0])
        return self.env.ref('py_ctrm_account_report.report_cobranzas_action').report_action(self, data)

    @api.model
    def cantidad_cobros(self, desde, hasta, cobrador):
        cobros = self.env['account.payment.paraguay'].search(
            [('payment_date', '>=', desde), ('payment_date', '<=', hasta), ('collection_user', '=', cobrador)])
        if len(cobros) > 0:
            return len(cobros)
        else:
            return 0

    def agregar_punto_de_miles(self, numero):
        numero_con_punto = '.'.join(
            [str(int(numero))[::-1][i:i + 3] for i in range(0, len(str(int(numero))), 3)])[::-1]
        return numero_con_punto


class ReporteCobranzas(models.AbstractModel):
    _name = 'report.py_ctrm_account_report.report_cobranzas_py'

    @api.model
    def _get_report_values(self, docids, data=None):
        Model = self.env.context.get('active_model')
        docs = self.env[Model].browse(self.env.context.get('active_id'))
        domain = []
        eca = []
        ids = []
        diccionario_recibos = collections.OrderedDict()
        dic_agrupados = collections.OrderedDict()

        if docs.estado:
            domain += [('company_id', '=', docs.company_id.id),
                       ('state', '=', 'cancel')]
        else:
            domain += [('company_id', '=', docs.company_id.id),
                       ('state', '=', 'posted')]

        if docs.desde and docs.hasta:
            domain += [('payment_date', '>=', docs.desde),
                       ('payment_date', '<=', docs.hasta),
                       ('partner_type', '=', 'customer')]

        if docs.talonario_id:
            domain += [('talonario_id', '=', docs.talonario_id.id)]

        if docs.cobrador:
            domain += [('collection_user', '=', docs.cobrador.id)]

        if docs.moneda:
            domain += [('currency_id', '=', docs.moneda.id)]

        if docs.cliente:
            domain += [('partner_id', '=', docs.cliente.id)]

        if docs.agrupar:
            orden = str(docs.agrupar) + ' asc'
        else:
            orden = 'payment_date asc'

        list_diarios = []
        recibos = self.env['account.payment.paraguay'].search(domain, order=orden)
        for h in recibos:
            if docs.invoice_payment_term_id == 'Contado':
                for u in h.matched_move_line_ids:
                    if u.move_id.invoice_payment_term_id.name == 'Contado' or u.move_id.invoice_date == u.move_id.invoice_date_due:
                        eca.append(h)
                        ids.append(h.id)
            else:
                for u in h.matched_move_line_ids:
                    if u.move_id.invoice_payment_term_id.name != 'Contado':
                        eca.append(h)
                        ids.append(h.id)
        domain += [('id', 'in', ids)]
        new_recibos = self.env['account.payment.paraguay'].search(domain, order=orden)
        new_recibos = new_recibos.sorted(lambda x: x.matched_move_line_ids.move_id[0].name)
        cobros = self.env['payment.methods.group'].search([('payment_group_id', 'in', ids)], order='payment_journal')
        lista_tipo = [cobro.payment_journal.tipo_reporte for cobro in cobros]
        lista_tipo.sort()
        lista_tipo = list(set(lista_tipo))

        list_diarios = [cobro.payment_journal for cobro in cobros]
        list_diarios.sort()
        list_diarios = list(set(list_diarios))

        lista_moneda = [moneda.currency_id.name for moneda in cobros]
        lista_moneda.sort()
        lista_moneda = list(set(lista_moneda))
        lista = []
        talonario_actual = ''
        cobrador_actual = ''
        moneda_actual = ''
        list_recibos = []

        dic_diario = collections.OrderedDict()
        suma = 0
        for diario in list_diarios:
            suma = sum([cobro.amount_payment for cobro in cobros.filtered(lambda r: r.payment_journal.id == diario.id)])
            dic_diario.setdefault(diario, suma)
        dic_diario = dic_diario.items()

        cobros1 = self.env['payment.methods.group'].search([('currency_id.name', '=', 'PYG'),
                                                      ('payment_group_id', 'in', ids)]).sorted(lambda x: x.payment_journal.id)
        list_diarios1 = [cobro1.payment_journal for cobro1 in cobros1]
        list_diarios1.sort()
        list_diarios1 = list(set(list_diarios1))
        dic_diario1 = collections.OrderedDict()
        suma1 = 0
        for diario1 in list_diarios1:
            suma1 = sum([cobro1.amount_payment for cobro1 in cobros1.filtered(lambda r: r.payment_journal.id == diario1.id)])
            dic_diario1.setdefault(diario1, suma1)
        dic_diario1 = dic_diario1.items()

        cobros2 = self.env['payment.methods.group'].search([('currency_id.name', '=', 'USD'),
                                                      ('payment_group_id', 'in', ids)]).sorted(lambda x: x.payment_journal.id)
        list_diarios2 = [cobro2.payment_journal for cobro2 in cobros2]
        list_diarios2.sort()
        list_diarios2 = list(set(list_diarios2))
        dic_diario2 = collections.OrderedDict()
        suma2 = 0
        for diario2 in list_diarios2:
            suma2 = sum([cobro2.amount_payment for cobro2 in cobros2.filtered(lambda r: r.payment_journal.id == diario2.id)])
            dic_diario2.setdefault(diario2, suma2)
        dic_diario2 = dic_diario2.items()

        lineas_asiento = self.env['payment.methods.group'].search([('payment_group_id', 'in', ids)])
        lineas_asiento = lineas_asiento.sorted(lambda x: x.id)

        lineas_cabecera = self.env['account.payment.paraguay'].search([('payment_date', '>=', docs.desde),
                                                                    ('payment_date', '<=', docs.hasta),
                                                                    ('state', '=', 'posted')]).sorted(lambda x: x.id)

        for recibo in new_recibos.sorted(key=lambda r: (r.collection_user.id, r.payment_date)):
            lista = []
            if docs.agrupar == 'collection_user':
                if not cobrador_actual:
                    cobrador_actual = recibo.collection_user.name
                    for tipo in lista_tipo:
                        suma = sum([cobro.amount_payment for cobro in recibo.payment_methods_ids if cobro.payment_journal.tipo_reporte == tipo])
                        lista.append(suma)
                    diccionario_recibos.setdefault(recibo, lista)
                elif cobrador_actual == recibo.collection_user.name:
                    for tipo in lista_tipo:
                        suma = sum([cobro.amount_payment for cobro in recibo.payment_methods_ids if cobro.payment_journal.tipo_reporte == tipo])
                        lista.append(suma)
                    diccionario_recibos.setdefault(recibo, lista)
                else:
                    list_recibos = self.setear_lista(diccionario_recibos, lista_tipo)
                    dic_agrupados.setdefault(cobrador_actual, list_recibos)
                    list_recibos = []
                    diccionario_recibos = collections.OrderedDict()
                    cobrador_actual = recibo.collection_user.name
                    for tipo in lista_tipo:
                        suma = sum([cobro.amount_payment for cobro in recibo.payment_methods_ids if cobro.payment_journal.tipo_reporte == tipo])
                        lista.append(suma)
                    diccionario_recibos.setdefault(recibo, lista)
            elif docs.agrupar == 'talonario_id':
                if not talonario_actual:
                    talonario_actual = recibo.talonario_id.name
                    for tipo in lista_tipo:
                        suma = sum([cobro.amount_payment for cobro in recibo.payment_methods_ids if cobro.payment_journal.tipo_reporte == tipo])
                        lista.append(suma)
                    diccionario_recibos.setdefault(recibo, lista)
                elif talonario_actual == recibo.talonario_id.name:
                    for tipo in lista_tipo:
                        suma = sum([cobro.amount_payment for cobro in recibo.payment_methods_ids if cobro.payment_journal.tipo_reporte == tipo])
                        lista.append(suma)
                    diccionario_recibos.setdefault(recibo, lista)
                else:
                    list_recibos = self.setear_lista(diccionario_recibos, lista_tipo)
                    dic_agrupados.setdefault(talonario_actual, list_recibos)
                    list_recibos = []
                    diccionario_recibos = collections.OrderedDict()
                    talonario_actual = recibo.talonario_id.name
                    for tipo in lista_tipo:
                        suma = sum([cobro.amount_payment for cobro in recibo.payment_methods_ids if cobro.payment_journal.tipo_reporte == tipo])
                        lista.append(suma)
                    diccionario_recibos.setdefault(recibo, lista)
            elif docs.agrupar == 'currency_id':
                if not moneda_actual:
                    moneda_actual = recibo.currency_id.name
                    for tipo in lista_tipo:
                        suma = sum([cobros2.amount_payment for cobros2 in recibo.payment_methods_ids if cobros2.payment_journal.tipo_reporte == tipo])
                        lista.append(suma)
                    diccionario_recibos.setdefault(recibo, lista)
                elif moneda_actual == recibo.currency_id.name:
                    for tipo in lista_tipo:
                        suma = sum([cobros2.amount_payment for cobros2 in recibo.payment_methods_ids if cobros2.payment_journal.tipo_reporte == tipo])
                        lista.append(suma)
                    diccionario_recibos.setdefault(recibo, lista)
                else:
                    list_recibos = self.setear_lista(diccionario_recibos, lista_tipo)
                    dic_agrupados.setdefault(moneda_actual, list_recibos)
                    list_recibos = []
                    diccionario_recibos = collections.OrderedDict()
                    moneda_actual = recibo.currency_id
                    for tipo in lista_tipo:
                        suma = sum([cobros2.amount_payment for cobros2 in recibo.payment_methods_ids if cobros2.payment_journal.tipo_reporte == tipo])
                        lista.append(suma)
                    diccionario_recibos.setdefault(recibo, lista)
            else:
                for tipo in lista_tipo:
                    suma = sum([cobro.amount_payment for cobro in recibo.payment_methods_ids if cobro.payment_journal.tipo_reporte == tipo])
                    lista.append(suma)
                diccionario_recibos.setdefault(recibo, lista)
                list_recibos = self.setear_lista(diccionario_recibos, lista_tipo)
                dic_agrupados.setdefault(1, list_recibos)

        if docs.agrupar:
            list_recibos = self.setear_lista(diccionario_recibos, lista_tipo)
            if talonario_actual:
                dic_agrupados.setdefault(talonario_actual, list_recibos)
            elif moneda_actual:
                dic_agrupados.setdefault(moneda_actual, list_recibos)
            else:
                dic_agrupados.setdefault(cobrador_actual, list_recibos)

        lista_total_tipo = [0] * len(lista_tipo)
        print(dic_agrupados.values())
        for l in dic_agrupados.values():
            lista_total_tipo = [a + b for (a, b) in zip(lista_total_tipo, l[1])]
        print(lista_total_tipo)
        dic_agrupados = dic_agrupados.items()

        # raise ValidationError('hola')

        docargs = {
            'doc_ids': self.ids,
            'doc_model': Model,
            'docs': docs,
            'time': time,
            'dic_agrupados': dic_agrupados,
            'lista_tipo': lista_tipo,
            'lista_total_tipo': lista_total_tipo,
            'dic_diario': dic_diario,
            'dic_diario1': dic_diario1,
            'dic_diario2': dic_diario2,
            'lineas': lineas_asiento,
            'cabecera': lineas_cabecera
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
