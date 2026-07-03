# -*- coding: utf-8 -*-
from odoo import fields, models, exceptions, api
import time, collections
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
import io
import logging
import xlsxwriter
from odoo import http, _
from odoo.http import request
from odoo.addons.web.controllers.main import serialize_exception, content_disposition
import operator
from collections import defaultdict

_logger = logging.getLogger(__name__)


class WizardReportBalanceBook(models.TransientModel):
    _name = "balance.book.wizard"

    fecha_de_hoy = fields.Datetime(string='Fecha de hoy', default=fields.Datetime.now)
    fecha_inicio = fields.Date(string="Fecha desde")
    fecha_fin = fields.Date(string="Fecha hasta", default=fields.Date.today())
    tipo = fields.Selection([('xlsx', 'XLSX'), ('pdf', 'PDF')], string="Tipo de archivo", default='pdf')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    resumen_balance = fields.Selection([('con_ceros', 'Cuentas con saldo 0'), ('sin_ceros', 'Cuentas sin saldo 0')], default='sin_ceros')

    @api.model
    def _get_default_company(self):
        return self.env.user.company_id.id

    # @api.multi
    def check_report(self):
        data = {}
        data['form'] = self.read(['fecha_inicio', 'fecha_fin', 'tipo'])[0]
        return self._print_report(data)

    def _print_report(self, data):
        data['form'].update(self.read(['fecha_inicio', 'fecha_fin', 'tipo'])[0])
        if self.tipo == 'pdf':
            return self.env.ref('py_ctrm_account_report.balance_id').report_action(self, data=data)
        else:
            return {
                'type': 'ir.actions.act_url',
                'url': '/getBalanceGeneral/' + str(self.id),
                'target': 'current'
            }

    def print_report_xlsx(self):
        data = {}
        data['form'] = self.read(['fecha_inicio', 'fecha_fin', 'tipo'])[0]
        data['form'].update(self.read(['fecha_inicio', 'fecha_fin', 'tipo'])[0])
        return self.env['report'].get_action(self, 'py_ctrm_account_report.balance_general_paraguay_report_xlsx', data=data)

    def agregar_punto_de_miles(self, numero):
        numero = round(numero)
        if numero >= 0:
            numero_con_punto = '.'.join(
                [str(int(numero))[::-1][i:i + 3] for i in range(0, len(str(int(numero))), 3)])[::-1]
        else:
            numero *= -1
            numero_con_punto = '.'.join([str(int(numero))[::-1][i:i + 3] for i in range(0, len(str(int(numero))), 3)])[::-1]
            numero_con_punto = '-' + numero_con_punto
        num_return = numero_con_punto
        return num_return

    def convertir_guaranies(self, factura):
        rate = self.env['res.currency.rate'].search(
            [('currency_id', '=', factura.currency_id.id), ('name', '=', str(factura.date_invoice))])
        monto = factura.amount_total * (1 / rate.rate)
        monto = self.agregar_punto_de_miles(monto, 1)
        return monto

    def sumalista(self, listaNumeros):
        laSuma = 0
        for i in listaNumeros:
            laSuma = laSuma + i
        return laSuma

    def _get_report_values1(self, docids, data=None):
        Model = self.env.context.get('active_model')
        docs = self.env[Model].browse(self.env.context.get('active_id'))

        movimientos = self.get_datos_balance1(docs.fecha_inicio, docs.fecha_fin, docs.company_id, docs.resumen_balance)

        docargs = {
            'doc_ids': self.ids,
            'doc_model': Model,
            'docs': docs,
            'time': time,
            'movimientos': movimientos,

        }
        return docargs

    def get_datos_balance1(self, fecha_inicio, fecha_fin, company_id, resumen_balance):
        """
        La idea es un dicionario que tenga la cuenta y el total sumado


        :param fecha_inicio:
        :param fecha_fin:
        :param company_id:
        :param resumen_balance:
        :return:
        """

        cuentas = list()
        domain = []
        domain_ant = []
        total1 = 0
        total2 = 0
        total3 = 0
        total4 = 0
        total5 = 0
        total7 = 0
        total10 = 0

        activos = list()
        pasivos = list()
        operativos = list()
        costos_cue = list()
        patrimonios = list()
        excedentes_cue = list()
        ordend_cue = list()
        ordena_cue = list()
        perdidas_ganancias_cue = list()

        activo = self.env['account.account'].search([('internal_group', '=ilike', 'asset')])
        pasivo = self.env['account.account'].search([('internal_group', '=ilike', 'liability')])
        patrimonio = self.env['account.account'].search([('internal_group', '=ilike', 'equity')])
        operativo = self.env['account.account'].search([('internal_group', '=ilike', 'income')])
        costos = self.env['account.account'].search([('internal_group', '=ilike', 'expense')])
        excedentes = self.env['account.account'].search([('code', '=ilike', '6%')])
        ordend = self.env['account.account'].search([('code', '=ilike', '7%')])
        ordena = self.env['account.account'].search([('code', '=ilike', '8%')])
        perdidas_ganancias = self.env['account.account'].search([('code', '=ilike', '999999')])

        codigo_cuentas = []
        account_oder = defaultdict(list)
        codes_numbers = []

        for cue in activo:
            cuentas.append(cue.id)
            activos.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        cuentas_hijas = self.env['account.move.line'].search(
            [('account_id', 'in', activos),
             ('company_id', '=', company_id.id),
             ('date', '>=', fecha_inicio),
             ('date', '<=', fecha_fin),
             ('parent_state', '=', 'posted')])
        if cuentas_hijas:
            for linea in cuentas_hijas:
                total1 += linea.debit - linea.credit

        for cue in pasivo:
            cuentas.append(cue.id)
            pasivos.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        cuentas_hijas = self.env['account.move.line'].search(
            [('account_id', 'in', pasivos),
             ('company_id', '=', company_id.id),
             ('date', '>=', fecha_inicio),
             ('date', '<=', fecha_fin),
             ('parent_state', '=', 'posted')])
        if cuentas_hijas:
            for linea in cuentas_hijas:
                total2 += linea.credit - linea.debit

        for cue in operativo:
            cuentas.append(cue.id)
            operativos.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        cuentas_hijas = self.env['account.move.line'].search(
            [('account_id', 'in', operativos),
             ('company_id', '=', company_id.id),
             ('date', '>=', fecha_inicio),
             ('date', '<=', fecha_fin),
             ('parent_state', '=', 'posted')])
        if cuentas_hijas:
            for linea in cuentas_hijas:
                total4 += linea.credit - linea.debit

        for cue in costos:
            cuentas.append(cue.id)
            costos_cue.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        cuentas_hijas = self.env['account.move.line'].search(
            [('account_id', 'in', costos_cue),
             ('company_id', '=', company_id.id),
             ('date', '>=', fecha_inicio),
             ('date', '<=', fecha_fin),
             ('parent_state', '=', 'posted')])
        if cuentas_hijas:
            for linea in cuentas_hijas:
                total5 += linea.debit - linea.credit
                total6 = total4 - total5
                total7 = total5 + total6

        for cue in patrimonio:
            cuentas.append(cue.id)
            patrimonios.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        cuentas_hijas = self.env['account.move.line'].search(
            [('account_id', 'in', patrimonios),
             ('company_id', '=', company_id.id),
             ('date', '>=', fecha_inicio),
             ('date', '<=', fecha_fin),
             ('parent_state', '=', 'posted')])
        if cuentas_hijas:
            for linea in cuentas_hijas:
                total3 += linea.credit - linea.debit
                total10 = total3 + total4 - total5

        for cue in excedentes:
            cuentas.append(cue.id)
            excedentes_cue.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        # cuentas_hijas = self.env['account.move.line'].search(
        #     [('account_id', 'in', excedentes_cue),
        #      ('company_id', '=', company_id.id),
        #      ('date', '>=', fecha_inicio),
        #      ('date', '<=', fecha_fin),
        #      ('parent_state', '=', 'posted')])
        # if cuentas_hijas:
        #     for linea in cuentas_hijas:
        #         excedentes_natu_credit.append(linea.credit)
        #         excedentes_natu_debit.append(linea.debit)

        for cue in ordend:
            cuentas.append(cue.id)
            ordend_cue.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        # cuentas_hijas = self.env['account.move.line'].search(
        #     [('account_id', 'in', ordend_cue),
        #      ('company_id', '=', company_id.id),
        #      ('date', '>=', fecha_inicio),
        #      ('date', '<=', fecha_fin),
        #      ('parent_state', '=', 'posted')])
        # if cuentas_hijas:
        #     for linea in cuentas_hijas:
        #         ordend_natu_credit.append(linea.credit)
        #         ordend_natu_debit.append(linea.debit)

        for cue in ordena:
            cuentas.append(cue.id)
            ordena_cue.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        # cuentas_hijas = self.env['account.move.line'].search(
        #     [('account_id', 'in', ordena_cue),
        #      ('company_id', '=', company_id.id),
        #      ('date', '>=', fecha_inicio),
        #      ('date', '<=', fecha_fin),
        #      ('parent_state', '=', 'posted')])
        # if cuentas_hijas:
        #     for linea in cuentas_hijas:
        #         ordena_natu_credit.append(linea.credit)
        #         ordena_natu_debit.append(linea.debit)

        for cue in perdidas_ganancias:
            cuentas.append(cue.id)
            perdidas_ganancias_cue.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        # cuentas_hijas = self.env['account.move.line'].search(
        #     [('account_id', 'in', perdidas_ganancias_cue),
        #      ('company_id', '=', company_id.id),
        #      ('date', '>=', fecha_inicio),
        #      ('date', '<=', fecha_fin),
        #      ('parent_state', '=', 'posted')])
        # if cuentas_hijas:
        #     for linea in cuentas_hijas:
        #         ultimo_natu_credit.append(linea.credit)
        #         ultimo_natu_debit.append(linea.debit)

        domain += [('company_id', '=', company_id.id),
                   ('date', '>=', fecha_inicio),
                   ('date', '<=', fecha_fin),
                   ('account_id', 'in', cuentas),
                   ('parent_state', '=', 'posted')]
        fi = datetime.strptime(str(fecha_inicio), '%Y-%m-%d')
        ff = datetime.strptime(str(fecha_fin), '%Y-%m-%d')
        fecha_inicio_ant = fi - relativedelta(years=1)
        fecha_fin_ant = ff - relativedelta(years=1)

        domain_ant += [('company_id', '=', company_id.id),
                       ('date', '>=', fecha_inicio_ant),
                       ('date', '<=', fecha_fin_ant),
                       ('account_id', 'in', cuentas),
                       ('parent_state', '=', 'posted')]

        movimientos = self.env['account.move.line'].search(domain, order='account_id')
        movimientos_ant = self.env['account.move.line'].search(domain_ant, order='account_id')
        dic = collections.OrderedDict()
        padres = list()
        ccc = list()
        final = list()
        cuentas_padres = movimientos.mapped('account_id.parent_id')
        cuentas = self.env['account.account'].with_context(
            show_parent_account=True).search(
            [('deprecated', '=', False),
             ('company_id', '=', company_id.id)])

        codes_numbers = sorted(codes_numbers, key=int)

        cuentas_ordenadas = []
        for code in codes_numbers:
            for order in account_oder[code]:
                cuentas_ordenadas.append(order)

        filas = 0
        for account in cuentas_ordenadas:
            filas += 1
            posicion_cuenta = self.env['account.account'].search([('company_id', '=', company_id.id), ('code', '=', account)])
            posicion_cuenta.account_order = filas

        for a in cuentas.sorted(key=lambda r: r.account_order, reverse=True):
            movi = movimientos.filtered(lambda r: r.account_id.id == a.id)
            # raise ValidationError('aaa %s' % movi)
            if a.internal_group == 'asset':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                total = debito - credito
            elif a.internal_group == 'liability':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                total = abs(debito - credito)
            elif a.internal_group == 'equity':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                total = abs(debito - credito)
            elif a.internal_group == 'income':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                total = abs(debito - credito)
            elif a.internal_group == 'expense':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                total = debito - credito
            elif a.internal_group == 'off_balance':
                total = sum(movi.mapped('balance'))
            else:
                total = sum(movi.mapped('balance'))
            total_ant = 0
            vals = {
                'code': a.code,
                'internal_group': a.internal_group,
                'total': total,
                'total_ant': total_ant,
                'account_id': a.id,
                'parent_id': a.parent_id.id,
                'name': a.name,
                'padre': False,
                'total1': total1,
                'total2': total2,
                'total3': total3,
                'total4': total4,
                'total5': total5,
                'total7': total7,
                'total10': total10,
            }
            ccc.append(vals)

        for b in cuentas.sorted(key=lambda r: r.code, reverse=True):
            movi = movimientos_ant.filtered(lambda r: r.account_id.id == b.id)
            total_ant = sum(movi.mapped('balance'))
            encon = list(filter(lambda r: r['account_id'] == b.id, ccc))
            if encon:
                encon[0]['total_ant'] += total_ant

        for mov in movimientos:
            encon = list(filter(lambda r: r['account_id'] == '999999', ccc))
        for e in ccc:
            movi = movimientos.filtered(lambda r: r.account_id.id == e['account_id'])
            if e['internal_group'] == 'asset':
                # if e['code'] == '213110':
                #    debito = sum(movi.mapped('debit'))
                #   credito = sum(movi.mapped('credit'))
                #   e['total'] = abs(debito - credito)
                # else:
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                e['total'] = debito - credito
            # elif e['name'] == 'RESULTADO DEL EJERCICIO':
            #    e['total'] = e['total4'] - e['total5']
            elif e['code'] == '999999':
                e['total'] = e['total4'] - e['total5']
            elif e['internal_group'] == 'liability':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                e['total'] = debito - credito
            elif e['internal_group'] == 'equity':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                e['total'] = debito - credito
            elif e['internal_group'] == 'income':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                e['total'] = debito - credito
            elif e['internal_group'] == 'expense':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                e['total'] = debito - credito
            else:
                e['total'] = sum(movi.mapped('balance'))
            # e['total'] = sum(movi.mapped('credit'))
        for i in ccc:
            codi = i['code']
            totali = i['total']
            totali_ant = i['total_ant']
            encon = list(filter(lambda r: r['account_id'] == i['parent_id'], ccc))
            # raise ValidationError('aaa %s' % encon[0]['total'])
            if encon:
                encon[0]['total'] += totali
                encon[0]['total_ant'] += totali_ant
                encon[0]['padre'] = True

        for a in ccc[::-1]:
            if resumen_balance == 'sin_ceros':
                if a['total'] != 0:
                    final.append(a)
            elif resumen_balance == 'con_ceros':
                final.append(a)

        for c in cuentas_padres:
            padres.append(c.code)
            if c.parent_id:
                padres.append(c.parent_id.id)

        return final


class ReportBalanceBook(models.AbstractModel):
    _name = 'report.py_ctrm_account_report.balance_book'

    def _get_report_values(self, docids, data=None):
        Model = self.env.context.get('active_model')
        docs = self.env[Model].browse(self.env.context.get('active_id'))

        movimientos = self.get_datos_balance(docs.fecha_inicio, docs.fecha_fin, docs.company_id, docs.resumen_balance)

        docargs = {
            'doc_ids': self.ids,
            'doc_model': Model,
            'docs': docs,
            'time': time,
            'movimientos': movimientos,

        }
        return docargs

    def get_datos_balance(self, fecha_inicio, fecha_fin, company_id, resumen_balance):
        """
        La idea es un dicionario que tenga la cuenta y el total sumado


        :param fecha_inicio:
        :param fecha_fin:
        :param company_id:
        :param resumen_balance:
        :return:
        """

        cuentas = list()
        domain = []
        domain_ant = []
        total1 = 0
        total2 = 0
        total3 = 0
        total4 = 0
        total5 = 0
        total7 = 0
        total10 = 0

        activos = list()
        pasivos = list()
        operativos = list()
        costos_cue = list()
        patrimonios = list()
        excedentes_cue = list()
        ordend_cue = list()
        ordena_cue = list()
        perdidas_ganancias_cue = list()

        activo = self.env['account.account'].search([('internal_group', '=ilike', 'asset')])
        pasivo = self.env['account.account'].search([('internal_group', '=ilike', 'liability')])
        patrimonio = self.env['account.account'].search([('internal_group', '=ilike', 'equity')])
        operativo = self.env['account.account'].search([('internal_group', '=ilike', 'income')])
        costos = self.env['account.account'].search([('internal_group', '=ilike', 'expense')])
        excedentes = self.env['account.account'].search([('code', '=ilike', '6%')])
        ordend = self.env['account.account'].search([('code', '=ilike', '7%')])
        ordena = self.env['account.account'].search([('code', '=ilike', '8%')])
        perdidas_ganancias = self.env['account.account'].search([('code', '=ilike', '999999')])

        codigo_cuentas = []
        account_oder = defaultdict(list)
        codes_numbers = []

        for cue in activo:
            cuentas.append(cue.id)
            activos.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        cuentas_hijas = self.env['account.move.line'].search(
            [('account_id', 'in', activos),
             ('company_id', '=', company_id.id),
             ('date', '>=', fecha_inicio),
             ('date', '<=', fecha_fin),
             ('parent_state', '=', 'posted')])
        if cuentas_hijas:
            for linea in cuentas_hijas:
                total1 += linea.debit - linea.credit

        for cue in pasivo:
            cuentas.append(cue.id)
            pasivos.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        cuentas_hijas = self.env['account.move.line'].search(
            [('account_id', 'in', pasivos),
             ('company_id', '=', company_id.id),
             ('date', '>=', fecha_inicio),
             ('date', '<=', fecha_fin),
             ('parent_state', '=', 'posted')])
        if cuentas_hijas:
            for linea in cuentas_hijas:
                total2 += linea.credit - linea.debit

        for cue in operativo:
            cuentas.append(cue.id)
            operativos.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        cuentas_hijas = self.env['account.move.line'].search(
            [('account_id', 'in', operativos),
             ('company_id', '=', company_id.id),
             ('date', '>=', fecha_inicio),
             ('date', '<=', fecha_fin),
             ('parent_state', '=', 'posted')])
        if cuentas_hijas:
            for linea in cuentas_hijas:
                total4 += linea.credit - linea.debit

        for cue in costos:
            cuentas.append(cue.id)
            costos_cue.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        cuentas_hijas = self.env['account.move.line'].search(
            [('account_id', 'in', costos_cue),
             ('company_id', '=', company_id.id),
             ('date', '>=', fecha_inicio),
             ('date', '<=', fecha_fin),
             ('parent_state', '=', 'posted')])
        if cuentas_hijas:
            for linea in cuentas_hijas:
                total5 += linea.debit - linea.credit
                total6 = total4 - total5
                total7 = total5 + total6

        for cue in patrimonio:
            cuentas.append(cue.id)
            patrimonios.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        cuentas_hijas = self.env['account.move.line'].search(
            [('account_id', 'in', patrimonios),
             ('company_id', '=', company_id.id),
             ('date', '>=', fecha_inicio),
             ('date', '<=', fecha_fin),
             ('parent_state', '=', 'posted')])
        if cuentas_hijas:
            for linea in cuentas_hijas:
                total3 += linea.credit - linea.debit
                total10 = total3 + total4 - total5

        for cue in excedentes:
            cuentas.append(cue.id)
            excedentes_cue.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        # cuentas_hijas = self.env['account.move.line'].search(
        #     [('account_id', 'in', excedentes_cue),
        #      ('company_id', '=', company_id.id),
        #      ('date', '>=', fecha_inicio),
        #      ('date', '<=', fecha_fin),
        #      ('parent_state', '=', 'posted')])
        # if cuentas_hijas:
        #     for linea in cuentas_hijas:
        #         excedentes_natu_credit.append(linea.credit)
        #         excedentes_natu_debit.append(linea.debit)

        for cue in ordend:
            cuentas.append(cue.id)
            ordend_cue.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        # cuentas_hijas = self.env['account.move.line'].search(
        #     [('account_id', 'in', ordend_cue),
        #      ('company_id', '=', company_id.id),
        #      ('date', '>=', fecha_inicio),
        #      ('date', '<=', fecha_fin),
        #      ('parent_state', '=', 'posted')])
        # if cuentas_hijas:
        #     for linea in cuentas_hijas:
        #         ordend_natu_credit.append(linea.credit)
        #         ordend_natu_debit.append(linea.debit)

        for cue in ordena:
            cuentas.append(cue.id)
            ordena_cue.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        # cuentas_hijas = self.env['account.move.line'].search(
        #     [('account_id', 'in', ordena_cue),
        #      ('company_id', '=', company_id.id),
        #      ('date', '>=', fecha_inicio),
        #      ('date', '<=', fecha_fin),
        #      ('parent_state', '=', 'posted')])
        # if cuentas_hijas:
        #     for linea in cuentas_hijas:
        #         ordena_natu_credit.append(linea.credit)
        #         ordena_natu_debit.append(linea.debit)

        for cue in perdidas_ganancias:
            cuentas.append(cue.id)
            perdidas_ganancias_cue.append(cue.id)
            codigo_cuentas.append(cue.code)
            account_oder[cue.code.split(".")[0]].append(cue.code)
            if cue.code.split(".")[0] not in codes_numbers:
                codes_numbers.append(cue.code.split(".")[0])
        # cuentas_hijas = self.env['account.move.line'].search(
        #     [('account_id', 'in', perdidas_ganancias_cue),
        #      ('company_id', '=', company_id.id),
        #      ('date', '>=', fecha_inicio),
        #      ('date', '<=', fecha_fin),
        #      ('parent_state', '=', 'posted')])
        # if cuentas_hijas:
        #     for linea in cuentas_hijas:
        #         ultimo_natu_credit.append(linea.credit)
        #         ultimo_natu_debit.append(linea.debit)

        domain += [('company_id', '=', company_id.id),
                   ('date', '>=', fecha_inicio),
                   ('date', '<=', fecha_fin),
                   ('account_id', 'in', cuentas),
                   ('parent_state', '=', 'posted')]
        fi = datetime.strptime(str(fecha_inicio), '%Y-%m-%d')
        ff = datetime.strptime(str(fecha_fin), '%Y-%m-%d')
        fecha_inicio_ant = fi - relativedelta(years=1)
        fecha_fin_ant = ff - relativedelta(years=1)

        domain_ant += [('company_id', '=', company_id.id),
                       ('date', '>=', fecha_inicio_ant),
                       ('date', '<=', fecha_fin_ant),
                       ('account_id', 'in', cuentas),
                       ('parent_state', '=', 'posted')]

        movimientos = self.env['account.move.line'].search(domain, order='account_id')
        movimientos_ant = self.env['account.move.line'].search(domain_ant, order='account_id')
        dic = collections.OrderedDict()
        padres = list()
        ccc = list()
        final = list()
        cuentas_padres = movimientos.mapped('account_id.parent_id')
        cuentas = self.env['account.account'].with_context(
            show_parent_account=True).search(
            [('deprecated', '=', False),
             ('company_id', '=', company_id.id)])

        codes_numbers = sorted(codes_numbers, key=int)

        cuentas_ordenadas = []
        for code in codes_numbers:
            for order in account_oder[code]:
                cuentas_ordenadas.append(order)

        filas = 0
        for account in cuentas_ordenadas:
            filas += 1
            posicion_cuenta = self.env['account.account'].search([('company_id', '=', company_id.id), ('code', '=', account)])
            posicion_cuenta.account_order = filas

        for a in cuentas.sorted(key=lambda r: r.account_order, reverse=True):
            movi = movimientos.filtered(lambda r: r.account_id.id == a.id)
            # raise ValidationError('aaa %s' % movi)
            if a.internal_group == 'asset':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                total = debito - credito
            elif a.internal_group == 'liability':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                total = abs(debito - credito)
            elif a.internal_group == 'equity':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                total = abs(debito - credito)
            elif a.internal_group == 'income':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                total = abs(debito - credito)
            elif a.internal_group == 'expense':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                total = debito - credito
            elif a.internal_group == 'off_balance':
                total = sum(movi.mapped('balance'))
            else:
                total = sum(movi.mapped('balance'))
            total_ant = 0
            vals = {
                'code': a.code,
                'internal_group': a.internal_group,
                'total': total,
                'total_ant': total_ant,
                'account_id': a.id,
                'parent_id': a.parent_id.id,
                'name': a.name,
                'padre': False,
                'total1': total1,
                'total2': total2,
                'total3': total3,
                'total4': total4,
                'total5': total5,
                'total7': total7,
                'total10': total10,
            }
            ccc.append(vals)

        for b in cuentas.sorted(key=lambda r: r.code, reverse=True):
            movi = movimientos_ant.filtered(lambda r: r.account_id.id == b.id)
            total_ant = sum(movi.mapped('balance'))
            encon = list(filter(lambda r: r['account_id'] == b.id, ccc))
            if encon:
                encon[0]['total_ant'] += total_ant

        for mov in movimientos:
            encon = list(filter(lambda r: r['account_id'] == '999999', ccc))
        for e in ccc:
            movi = movimientos.filtered(lambda r: r.account_id.id == e['account_id'])
            if e['internal_group'] == 'asset':
                # if e['code'] == '213110':
                #    debito = sum(movi.mapped('debit'))
                #   credito = sum(movi.mapped('credit'))
                #   e['total'] = abs(debito - credito)
                # else:
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                e['total'] = debito - credito
            # elif e['name'] == 'RESULTADO DEL EJERCICIO':
            #    e['total'] = e['total4'] - e['total5']
            elif e['code'] == '999999':
                e['total'] = e['total4'] - e['total5']
            elif e['internal_group'] == 'liability':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                e['total'] = debito - credito
            elif e['internal_group'] == 'equity':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                e['total'] = debito - credito
            elif e['internal_group'] == 'income':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                e['total'] = debito - credito
            elif e['internal_group'] == 'expense':
                debito = sum(movi.mapped('debit'))
                credito = sum(movi.mapped('credit'))
                e['total'] = debito - credito
            else:
                e['total'] = sum(movi.mapped('balance'))
            # e['total'] = sum(movi.mapped('credit'))
        for i in ccc:
            codi = i['code']
            totali = i['total']
            totali_ant = i['total_ant']
            encon = list(filter(lambda r: r['account_id'] == i['parent_id'], ccc))
            # raise ValidationError('aaa %s' % encon[0]['total'])
            if encon:
                encon[0]['total'] += totali
                encon[0]['total_ant'] += totali_ant
                encon[0]['padre'] = True

        for a in ccc[::-1]:
            if resumen_balance == 'sin_ceros':
                if a['total'] != 0:
                    final.append(a)
            elif resumen_balance == 'con_ceros':
                final.append(a)

        for c in cuentas_padres:
            padres.append(c.code)
            if c.parent_id:
                padres.append(c.parent_id.id)

        return final


class DownloadXLSPy(http.Controller):
    @http.route('/getBalanceGeneral/<int:id>', auth='public')
    def generarXLSX(self, id=None, **kw):
        record = request.env['balance.book.wizard'].browse(id)
        move_actual = None
        movimientos = record.get_datos_balance1(record.fecha_inicio,
                                                record.fecha_fin,
                                                record.company_id,
                                                record.resumen_balance)
        i = 3
        fp = io.BytesIO()
        workbook = xlsxwriter.Workbook(fp, {'in_memory': True})
        sheet = workbook.add_worksheet('Balance')
        bold = workbook.add_format({'bold': True, 'fg_color': 'white', 'align': 'center', 'border': 1})
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
        merge_format2 = workbook.add_format({
            'bold': 1,
            'font_color': 'black'})
        merge_format3 = workbook.add_format({
            'bold': 1,
            'align': 'left',
            'valign': 'vleft',
            'font_color': 'black'})
        merge_format6 = workbook.add_format({
            'align': 'left',
            'valign': 'vleft',
            'font_color': 'black',
            'fg_color': '8afe5c'})
        number_format1 = workbook.add_format({'bold': 1, 'num_format': '#,##0'})
        number_format2 = workbook.add_format({'num_format': '#,##0'})
        sheet.write(0, 0, record.company_id.name, merge_format1)
        sheet.write(1, 0, record.company_id.vat, merge_format1)
        sheet.write(0, 2, 'Fecha: ' + record.fecha_de_hoy.strftime('%d-%m-%Y'), merge_format1)
        sheet.write(1, 2, 'Hora: ' + record.fecha_de_hoy.strftime('%H:%M:%S'), merge_format1)
        sheet.merge_range('A3:C3', 'Balance General DEL ' + record.fecha_inicio.strftime(
            '%d-%m-%Y') + ' AL ' + record.fecha_fin.strftime('%d-%m-%Y'), merge_format1)
        sheet.set_column('A:C', 30)

        total_activo = 0
        total_pasivo = 0
        total_patrimonio = 0
        total_ingreso = 0
        total_egreso = 0
        for m in movimientos:
            if record.resumen_balance == 'sin_ceros':
                if record.agregar_punto_de_miles((m['total'])) != '0':
                    if m['padre'] == True:
                        sheet.write(i, 0, m['code'], merge_format2)
                        sheet.write(i, 1, m['name'], merge_format2)
                        if str(m['code'])[0] == '2':
                            sheet.write_number(i, 2, (m['total'] * -1), number_format1)
                            if m['name'].upper() == 'PASIVO':
                                total_pasivo = m['total']
                        elif str(m['code'])[0] == '3':
                            sheet.write_number(i, 2, (m['total'] * -1), number_format1)
                            if m['name'].upper() == 'PATRIMONIO NETO':
                                total_patrimonio = m['total']
                        elif str(m['code'])[0] == '4':
                            sheet.write_number(i, 2, (m['total'] * -1), number_format1)
                            if m['name'].upper() == 'INGRESOS':
                                total_ingreso = m['total']
                        else:
                            sheet.write_number(i, 2, (m['total']), number_format1)
                            if m['name'].upper() == 'ACTIVO':
                                total_activo = m['total']
                            elif m['name'].upper() == 'EGRESOS':
                                total_egreso = m['total']
                    else:
                        sheet.write(i, 0, m['code'])
                        sheet.write(i, 1, m['name'])
                        if str(m['code'])[0] == '2':
                            sheet.write_number(i, 2, (m['total'] * -1), number_format1)
                        elif str(m['code'])[0] == '3':
                            sheet.write_number(i, 2, (m['total'] * -1), number_format1)
                        elif str(m['code'])[0] == '4':
                            sheet.write_number(i, 2, (m['total'] * -1), number_format1)
                        else:
                            sheet.write_number(i, 2, (m['total']), number_format1)
                    i = i + 1
            if record.resumen_balance == 'con_ceros':
                if m['padre'] == True:
                    sheet.write(i, 0, m['code'], merge_format2)
                    sheet.write(i, 1, m['name'], merge_format2)
                    sheet.write_number(i, 2, abs(m['total']), number_format1)
                else:
                    sheet.write(i, 0, m['code'])
                    sheet.write(i, 1, m['name'])
                    sheet.write_number(i, 2, abs(m['total']), number_format2)
                i = i + 1

        i = i + 4
        resultado_uno = (total_activo + (total_pasivo + total_patrimonio))
        resultado_dos = (total_ingreso + total_egreso)
        sheet.write(i, 1, 'Resumen   de   Balance   General', merge_format6)
        sheet.write(i + 1, 0, 'Total Activo:', merge_format3)
        sheet.write_number(i + 1, 2, total_activo, number_format1)
        sheet.write(i + 2, 0, 'Total Pasivo:', merge_format3)
        sheet.write_number(i + 2, 2, total_pasivo, number_format1)
        sheet.write(i + 3, 0, 'Total Patrimonio Neto:', merge_format3)
        sheet.write_number(i + 3, 2, total_patrimonio, number_format1)
        sheet.write(i + 4, 0, 'Diferencia: {Activo-(Pasivo+P.Neto)}:',
                    merge_format3)
        sheet.write_number(i + 4, 2, resultado_uno, number_format1)

        sheet.write(i + 6, 0, 'Total Ingreso:',
                    merge_format3)
        sheet.write_number(i + 6, 2, total_ingreso, number_format1)
        sheet.write(i + 7, 0, 'Total Egreso:',
                    merge_format3)
        sheet.write_number(i + 7, 2, total_egreso, number_format1)
        sheet.write(i + 8, 0, 'Resultado:',
                    merge_format3)
        sheet.write_number(i + 8, 2, resultado_dos, number_format1)

        workbook.close()
        fp.seek(0)
        return request.make_response(fp.read(), [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition('balance_general.xlsx'))])
