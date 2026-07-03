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


class WizardReportIVABook(models.TransientModel):
    _name = "vat.book.wizard"

    tipo = fields.Selection(
        [('xlsx', 'XLSX'),
         ('pdf', 'PDF')],
        string="Tipo de archivo",
        default='pdf')
    fecha_de_hoy = fields.Datetime(
        string='Fecha de hoy',
        default=lambda self: fields.datetime.now())
    fecha_inicio = fields.Date(
        string="Fecha desde")
    fecha_fin = fields.Date(
        string="Fecha hasta")
    company_id = fields.Many2one(
        'res.company',
        'Company',
        required=True,
        index=True,
        default=lambda self: self.env.company)
    tipo_informe = fields.Selection(
        [('venta', 'Venta'),
         ('compra', 'Compra')],
        string="Tipo")
    state = fields.Selection(
       [('cancel', 'Cancelado'),
        ('posted', 'Publicado'),
        ('cancel, posted', 'Todos')],
       string="Estado",
       default='posted'
    )
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
        data['form'] = self.read(['fecha_inicio',
                                  'fecha_fin',
                                  'tipo'])[0]
        return self._print_report(data)

    def _print_report(self, data):
        data['form'].update(self.read(['fecha_inicio',
                                       'fecha_fin',
                                       'tipo'])[0])
        if self.tipo == 'pdf':
            return self.env.ref('py_ctrm_account_report.report_libro_iva_id').report_action(self, data=data)
        else:
            return {
                'type': 'ir.actions.act_url',
                'url': '/getLibroIVA/' + str(self.id),
                'target': 'current'
            }

    def print_report_xlsx(self):
        data = {}
        data['form'] = self.read(['fecha_inicio',
                                  'fecha_fin',
                                  'tipo'])[0]
        data['form'].update(self.read(['fecha_inicio',
                                       'fecha_fin',
                                       'tipo'])[0])

        return self.env['report'].get_action(self,
                                             'py_ctrm_account_report.'
                                             'libro_iva_paraguay_report_xlsx',
                                             data=data)

    def agregar_punto_de_miles(self, numero):
        numero_con_punto = '.'.join([str(int(numero))[::-1][i:i + 3] for i in
                                     range(0, len(str(int(numero))), 3)])[::-1]
        num_return = numero_con_punto
        return num_return

    def get_datos_iva1(self, fecha_inicio, fecha_fin, tipo_informe, state):
        cr = self.env.cr
        if tipo_informe == 'compra':
            company = self.company_id.id
            estado = str(state).replace(", ", "', '")
            query = """
            SELECT
                 sum(CASE
                        WHEN aml.product_id = 2694 and am.state = 'posted' THEN (abs(aml.balance) * 11 ) - aml.balance
                        WHEN btg.name = 'IVA 10%' and am.state = 'posted' THEN abs(aml.balance) 
                        ELSE 0 END) as base_10,
                 sum(CASE
                        WHEN aml.product_id = 2694 and am.state = 'posted' THEN abs(aml.balance)
                        WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                        THEN abs(aml.balance) ELSE 0 END) as vat_10,
                 sum(CASE
                        WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                        THEN abs(aml.balance) ELSE 0 END) as base_5,
                 sum(CASE
                        WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                        THEN abs(aml.balance) ELSE 0 END) as vat_5,
                 sum(CASE
                        WHEN aml.product_id = 2694 and am.state = 'posted' THEN 0
                        WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted'
                        THEN abs(aml.balance) 
                        WHEN btg.name = 'Taxes' and am.state = 'posted'
                        THEN abs(aml.balance) 
                        ELSE 0 END) as not_taxed,
                 sum(CASE
                        WHEN aml.product_id = 2694 and am.state = 'posted' THEN (abs(aml.balance) * 11 ) - aml.balance
                        WHEN btg.name = 'IVA 10%' and am.state = 'posted'
                        THEN abs(aml.balance) ELSE 0 END) +
                 sum(CASE
                        WHEN aml.product_id = 2694 and am.state = 'posted' THEN abs(aml.balance)
                        WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                        THEN abs(aml.balance) ELSE 0 END) +
                 sum(CASE
                        WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                        THEN abs(aml.balance) ELSE 0 END) +
                 sum(CASE
                        WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                        THEN abs(aml.balance) ELSE 0 END) +
                 sum(CASE
                        WHEN aml.product_id = 2694 and am.state = 'posted' THEN 0
                        WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted'
                        THEN abs(aml.balance) 
                        WHEN btg.name = 'Taxes' and am.state = 'posted'
                        THEN abs(aml.balance) 
                        ELSE 0 END) as total,
                 hg.name as type_doc
                        FROM account_move_line aml
                        LEFT JOIN
                            account_move as am
                            ON aml.move_id = am.id
                        LEFT JOIN
                            -- nt = net tax
                            account_tax AS nt
                            ON aml.tax_line_id = nt.id
                        LEFT JOIN
                            account_move_line_account_tax_rel AS amltr
                            ON aml.id = amltr.account_move_line_id
                        LEFT JOIN
                            -- bt = base tax
                            account_tax AS bt
                            ON amltr.account_tax_id = bt.id
                        LEFT JOIN
                            account_tax_group AS btg
                            ON btg.id = bt.tax_group_id
                        LEFT JOIN
                            account_tax_group AS ntg
                            ON ntg.id = nt.tax_group_id
                        LEFT JOIN
                            res_partner AS rp
                            ON rp.id = am.partner_id
                        LEFT JOIN
                            account_tip_doc as hg
                            ON hg.id = am.tipdocgas
                        LEFT JOIN
                          account_journal as acj
                          ON acj.id = am.journal_id
                        WHERE
                            am.move_type in ('in_invoice', 'in_refund') 
                            AND hg.vatbook = 'true'
                            AND hg.tipdoc = 'purchase'
                            AND am.state in ('""" + str(estado) + """')
                            AND am.company_id = """ + str(company) + """
                            AND am.invoice_date BETWEEN '%s' and '%s'
                        group by hg.name

                      """ % (fecha_inicio, fecha_fin)
            cr.execute(query)
            compras = cr.fetchall()
            return compras
        if tipo_informe == 'venta':
            company = self.company_id.id
            estado = str(state).replace(", ", "', '")
            query = """
                         SELECT
                         
                 sum(CASE
                        WHEN btg.name = 'IVA 10%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) as base_10,
                 sum(CASE
                        WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) as vat_10,
                 sum(CASE
                        WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) as base_5,
                 sum(CASE
                        WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) as vat_5,
                 sum(CASE
                        WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted'
                        THEN (aml.balance * -1) 
                        WHEN btg.name = 'Taxes' and am.state = 'posted'
                        THEN (aml.balance * -1) 
                        ELSE 0 END) as not_taxed,
                 sum(CASE
                        WHEN btg.name = 'IVA 10%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) +
                 sum(CASE 
                        WHEN ntg.name = 'IVA 10%'  and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) + 
                 sum(CASE
                        WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) +
                 sum(CASE
                        WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) +
                 sum(CASE
                        WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted'
                        THEN (aml.balance * -1)  
                        WHEN btg.name = 'Taxes' and am.state = 'posted'
                        THEN (aml.balance * -1) 
                        ELSE 0 END) as total,
                 hg.name as type_doc
                            FROM account_move_line aml
                            LEFT JOIN
                                account_move as am
                                ON aml.move_id = am.id
                            LEFT JOIN
                                -- nt = net tax
                                account_tax AS nt
                                ON aml.tax_line_id = nt.id
                            LEFT JOIN
                                account_move_line_account_tax_rel AS amltr
                                ON aml.id = amltr.account_move_line_id
                            LEFT JOIN
                                -- bt = base tax
                                account_tax AS bt
                                ON amltr.account_tax_id = bt.id
                            LEFT JOIN
                                account_tax_group AS btg
                                ON btg.id = bt.tax_group_id
                            LEFT JOIN
                                account_tax_group AS ntg
                                ON ntg.id = nt.tax_group_id
                            LEFT JOIN
                                res_partner AS rp
                                ON rp.id = am.partner_id
                            LEFT JOIN
                              account_tip_doc as hg
                              ON hg.id = COALESCE(am.tipdocing,CASE WHEN am.move_type ='out_invoice' THEN 27 ELSE 33 END)
                            LEFT JOIN
                              account_journal as acj
                              ON acj.id = am.journal_id
                            WHERE
                                am.move_type in ('out_invoice', 'out_refund') 
                                AND hg.vatbook = 'true'
                                AND hg.tipdoc = 'sale'
                                AND am.state in ('""" + str(estado) + """')
                                and POSITION('-' IN am.name) > 0
                                AND am.company_id = """ + str(company) + """
                                AND am.invoice_date BETWEEN '%s' and '%s'
                           group by hg.name

                                  """ % (fecha_inicio, fecha_fin)
            cr.execute(query)
            ventas = cr.fetchall()
            return ventas


class ReportIVABook(models.AbstractModel):
    _name = 'report.py_ctrm_account_report.libro_iva_report'

    def _get_report_values(self, docids, data=None):
        Model = self.env.context.get('active_model')
        docs = self.env[Model].browse(self.env.context.get('active_id'))
        cr = self.env.cr
        if docs.tipo_informe == 'compra':
            company = self.env.company.id
            estado = str(docs.state).replace(", ", "', '")
            query = """SELECT
                         am.invoice_date,
                         am.ref as move_name,
                         CASE WHEN am.state = 'cancel' THEN 'CANCELADO'
                         WHEN am.importacion_gasto is True THEN COALESCE(eca.name, rp.name)
                         ELSE  rp.name END as partner_name,
                         CASE WHEN am.state = 'cancel' THEN 'CANCELADO'
                         ELSE rp.vat END as ruc,
                         sum(CASE
                                WHEN aml.product_id = 2694 and am.state = 'posted' THEN (abs(aml.balance) * 11 ) - aml.balance   
                                WHEN btg.name = 'IVA 10%' and am.state = 'posted'THEN abs(aml.balance) 
                                ELSE 0 END) as base_10,
                         sum(CASE
                                WHEN aml.product_id = 2694 and am.state = 'posted' THEN abs(aml.balance)    
                                WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                                THEN abs(aml.balance) 
                                ELSE 0 END) as vat_10,
                         sum(CASE
                                WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                                THEN abs(aml.balance) ELSE 0 END) as base_5,
                         sum(CASE
                                WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                                THEN abs(aml.balance) ELSE 0 END) as vat_5,
                         sum(CASE
                                WHEN aml.product_id = 2694 and am.state = 'posted' THEN 0    
                                WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted' THEN abs(aml.balance) 
                                WHEN btg.name = 'Taxes' and am.state = 'posted'
                                THEN abs(aml.balance) 
                                ELSE 0 END) as not_taxed,
                         sum(CASE
                                WHEN aml.product_id = 2694 and am.state = 'posted' THEN (abs(aml.balance) * 11 ) - aml.balance   
                                WHEN btg.name = 'IVA 10%' and am.state = 'posted'
                                THEN abs(aml.balance) ELSE 0 END) +
                         sum(CASE
                                WHEN aml.product_id = 2694 and am.state = 'posted' THEN abs(aml.balance)    
                                WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                                THEN abs(aml.balance) ELSE 0 END) +
                         sum(CASE
                                WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                                THEN abs(aml.balance) ELSE 0 END) + 
                         sum(CASE
                                WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                                THEN abs(aml.balance) ELSE 0 END) +
                        sum(CASE
                                WHEN aml.product_id = 2694 and am.state = 'posted' THEN 0    
                                WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted'
                                THEN abs(aml.balance) 
                                WHEN btg.name = 'Taxes' and am.state = 'posted'
                                THEN abs(aml.balance) 
                                ELSE 0 END) as total,
                         am.py_timbrado_prov as timbrado,
                         hg.name as type_doc,
                         CASE
                                WHEN COALESCE(am.invoice_payment_term_id,1)  = 1
                                THEN 'Contado'
                                ELSE 'Crédito' END as payment_term,
                         am.id as move_id,
                         am.id,
                         am.move_type,
                         am.date,
                         am.partner_id,
                         am.journal_id,
                         am.name,
                         am.state,
                         am.company_id,   
                         hg.id as doc_id
                        FROM account_move_line aml
                        LEFT JOIN
                            account_move as am
                            ON aml.move_id = am.id
                        LEFT JOIN
                            -- nt = net tax
                            account_tax AS nt
                            ON aml.tax_line_id = nt.id
                        LEFT JOIN
                            account_move_line_account_tax_rel AS amltr
                            ON aml.id = amltr.account_move_line_id
                        LEFT JOIN
                            -- bt = base tax
                            account_tax AS bt
                            ON amltr.account_tax_id = bt.id
                        LEFT JOIN
                            account_tax_group AS btg
                            ON btg.id = bt.tax_group_id
                        LEFT JOIN
                            account_tax_group AS ntg
                            ON ntg.id = nt.tax_group_id
                        LEFT JOIN
                            res_partner AS rp
                            ON rp.id = am.partner_id
                        LEFT JOIN
                            res_partner AS eca
                            ON eca.id = am.partner_no_despachante
                        LEFT JOIN
                            account_tip_doc as hg
                            ON hg.id = am.tipdocgas
                        LEFT JOIN
                          account_journal as acj
                          ON acj.id = am.journal_id
                        WHERE
                            am.move_type in ('in_invoice', 'in_refund') 
                            AND hg.vatbook = 'true'
                            AND hg.tipdoc = 'purchase'
                            AND am.state in ('""" + str(estado) + """')
                            AND am.company_id = """ + str(company) + """
                            AND am.invoice_date BETWEEN '%s' and '%s'
                        GROUP BY
                            am.id, rp.id, hg.name,hg.id, eca.id
                        ORDER BY am.invoice_date asc, am.ref asc
              """ % (docs.fecha_inicio, docs.fecha_fin)
            cr.execute(query)
        compras = cr.fetchall()
        if docs.tipo_informe == 'venta':
            company = self.env.company.id
            estado = str(docs.state).replace(", ", "', '")
            query = """
                         SELECT
                         am.invoice_date,
                         am.name as move_name,
                         CASE WHEN am.state = 'cancel' THEN 'CANCELADO'
                         ELSE rp.name END as partner_name,
                         CASE WHEN am.state = 'cancel' THEN 'CANCELADO'
                         ELSE rp.vat END as ruc,
                         sum(CASE
                                WHEN btg.name = 'IVA 10%' and am.state = 'posted'
                                THEN (aml.balance * -1) ELSE 0 END) as base_10,
                         sum(CASE
                                WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                                THEN (aml.balance * -1) ELSE 0 END) as vat_10,
                         sum(CASE
                                WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                                THEN (aml.balance * -1) ELSE 0 END) as base_5,
                         sum(CASE
                                WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                                THEN (aml.balance * -1) ELSE 0 END) as vat_5,
                         sum(CASE
                                WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted'
                                THEN (aml.balance * -1) 
                                WHEN btg.name = 'Taxes' and am.state = 'posted'
                                THEN (aml.balance * -1) 
                                ELSE 0 END) as not_taxed,
                         sum(CASE
                                WHEN btg.name = 'IVA 10%' and am.state = 'posted'
                                THEN (aml.balance * -1) ELSE 0 END) +
                         sum(CASE
                                WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                                THEN (aml.balance * -1) ELSE 0 END) +
                         sum(CASE
                                WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                                THEN (aml.balance * -1) ELSE 0 END) +
                         sum(CASE
                                WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                                THEN (aml.balance * -1) ELSE 0 END) + 
                         sum(CASE
                                WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted'
                                THEN (aml.balance * -1) 
                                WHEN btg.name = 'Taxes' and am.state = 'posted'
                                THEN (aml.balance * -1) 
                                ELSE 0 END) as total,
                             COALESCE(am.py_timbrado_prov, stam.name)   AS timbrado,
                             hg.name as type_doc,
                             CASE
                                WHEN COALESCE(am.invoice_payment_term_id,1)  = 1
                                THEN 'Contado'
                                ELSE 'Crédito' END as payment_term,
                         am.id as move_id,
                         am.id,
                         am.move_type,
                         am.date,
                         am.partner_id,
                         am.journal_id,
                         am.name,
                         am.state,
                         am.company_id,   
                         hg.id as doc_id
                        FROM account_move_line aml
                        LEFT JOIN
                            account_move as am
                            ON aml.move_id = am.id
                        LEFT JOIN
                            -- nt = net tax
                            account_tax AS nt
                            ON aml.tax_line_id = nt.id
                        LEFT JOIN
                            account_move_line_account_tax_rel AS amltr
                            ON aml.id = amltr.account_move_line_id
                        LEFT JOIN
                            -- bt = base tax
                            account_tax AS bt
                            ON amltr.account_tax_id = bt.id
                        LEFT JOIN
                            account_tax_group AS btg
                            ON btg.id = bt.tax_group_id
                        LEFT JOIN
                            account_tax_group AS ntg
                            ON ntg.id = nt.tax_group_id
                        LEFT JOIN
                            res_partner AS rp
                            ON rp.id = am.partner_id
                        LEFT JOIN
                            account_tip_doc as hg
                            ON hg.id = COALESCE(am.tipdocing,CASE WHEN am.move_type ='out_invoice' THEN 2 ELSE 1 END)
                        LEFT JOIN
                            account_journal as acj
                            ON acj.id = am.journal_id
                        LEFT JOIN account_journal_stamped as stam
                            ON stam.id = am.timbrado_id
                        WHERE
                            am.move_type in ('out_invoice', 'out_refund') 
                            AND  hg.vatbook = 'true'
                            AND hg.tipdoc = 'sale'
                            AND am.state in ('""" + str(estado) + """')
                            AND POSITION('-' IN am.name) > 0
                            AND am.company_id = """ + str(company) + """
                            AND am.invoice_date BETWEEN '%s' and '%s'
                        GROUP BY
                            am.id, rp.id, hg.name,hg.id, stam.name
                        ORDER BY am.invoice_date asc, am.name asc
                          """ % (docs.fecha_inicio, docs.fecha_fin)
            cr.execute(query)
        ventas = cr.fetchall()
        movimientos = self.get_datos_iva(docs.fecha_inicio, docs.fecha_fin, docs.tipo_informe, docs.state)

        docargs = {
            'doc_ids': self.ids,
            'doc_model': Model,
            'docs': docs,
            'time': time,
            'lineas': compras,
            'lineas2': ventas,
            'movimientos': movimientos
        }

        return docargs

    def get_datos_iva(self, fecha_inicio, fecha_fin, tipo_informe, state):
        cr = self.env.cr
        if tipo_informe == 'compra':
            company = self.env.company.id
            estado = str(state).replace(", ", "', '")
            query = """
            SELECT
                 sum(CASE
                        WHEN aml.product_id = 2694 and am.state = 'posted' THEN (abs(aml.balance) * 11 ) - aml.balance
                        WHEN btg.name = 'IVA 10%' and am.state = 'posted' THEN abs(aml.balance) 
                        ELSE 0 END) as base_10,
                 sum(CASE
                        WHEN aml.product_id = 2694 and am.state = 'posted' THEN abs(aml.balance)
                        WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                        THEN abs(aml.balance) ELSE 0 END) as vat_10,
                 sum(CASE
                        WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                        THEN abs(aml.balance) ELSE 0 END) as base_5,
                 sum(CASE
                        WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                        THEN abs(aml.balance) ELSE 0 END) as vat_5,
                 sum(CASE
                        WHEN aml.product_id = 2694 and am.state = 'posted' THEN 0
                        WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted'
                        THEN abs(aml.balance) 
                        WHEN btg.name = 'Taxes' and am.state = 'posted'
                        THEN abs(aml.balance) 
                        ELSE 0 END) as not_taxed,
                 sum(CASE
                        WHEN aml.product_id = 2694 and am.state = 'posted' THEN (abs(aml.balance) * 11 ) - aml.balance
                        WHEN btg.name = 'IVA 10%' and am.state = 'posted'
                        THEN abs(aml.balance) ELSE 0 END) +
                 sum(CASE
                        WHEN aml.product_id = 2694 and am.state = 'posted' THEN abs(aml.balance)
                        WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                        THEN abs(aml.balance) ELSE 0 END) +
                 sum(CASE
                        WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                        THEN abs(aml.balance) ELSE 0 END) +
                 sum(CASE
                        WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                        THEN abs(aml.balance) ELSE 0 END) +
                 sum(CASE
                        WHEN aml.product_id = 2694 and am.state = 'posted' THEN 0
                        WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted'
                        THEN abs(aml.balance) 
                        WHEN btg.name = 'Taxes' and am.state = 'posted'
                        THEN abs(aml.balance) 
                        ELSE 0 END) as total,
                 hg.name as type_doc
                        FROM account_move_line aml
                        LEFT JOIN
                            account_move as am
                            ON aml.move_id = am.id
                        LEFT JOIN
                            -- nt = net tax
                            account_tax AS nt
                            ON aml.tax_line_id = nt.id
                        LEFT JOIN
                            account_move_line_account_tax_rel AS amltr
                            ON aml.id = amltr.account_move_line_id
                        LEFT JOIN
                            -- bt = base tax
                            account_tax AS bt
                            ON amltr.account_tax_id = bt.id
                        LEFT JOIN
                            account_tax_group AS btg
                            ON btg.id = bt.tax_group_id
                        LEFT JOIN
                            account_tax_group AS ntg
                            ON ntg.id = nt.tax_group_id
                        LEFT JOIN
                            res_partner AS rp
                            ON rp.id = am.partner_id
                        LEFT JOIN
                            account_tip_doc as hg
                            ON hg.id = am.tipdocgas
                        LEFT JOIN
                          account_journal as acj
                          ON acj.id = am.journal_id
                        WHERE
                            am.move_type in ('in_invoice', 'in_refund') 
                            AND hg.vatbook = 'true'
                            AND hg.tipdoc = 'purchase'
                            AND am.state in ('""" + str(estado) + """')
                            AND am.company_id = """ + str(company) + """
                            AND am.invoice_date BETWEEN '%s' and '%s'
                        group by hg.name
                       
                      """ % (fecha_inicio, fecha_fin)
            cr.execute(query)
            compras = cr.fetchall()
            return compras
        if tipo_informe == 'venta':
            company = self.env.company.id
            estado = str(state).replace(", ", "', '")
            query = """
            SELECT
                 sum(CASE
                        WHEN btg.name = 'IVA 10%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) as base_10,
                 sum(CASE
                        WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) as vat_10,
                 sum(CASE
                        WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) as base_5,
                 sum(CASE
                        WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) as vat_5,
                 sum(CASE
                        WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted'
                        THEN (aml.balance * -1) 
                        WHEN btg.name = 'Taxes' and am.state = 'posted'
                        THEN (aml.balance * -1) 
                        ELSE 0 END) as not_taxed,
                 sum(CASE
                        WHEN btg.name = 'IVA 10%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) +
                 sum(CASE
                        WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) +
                 sum(CASE
                        WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) + 
                 sum(CASE
                        WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                        THEN (aml.balance * -1) ELSE 0 END) +
                 sum(CASE
                        WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted'
                        THEN (aml.balance * -1) 
                        WHEN btg.name = 'Taxes' and am.state = 'posted'
                        THEN (aml.balance * -1) 
                        ELSE 0 END) as total,
                 hg.name as type_doc
                        FROM account_move_line aml
                        LEFT JOIN
                            account_move as am
                            ON aml.move_id = am.id
                        LEFT JOIN
                            -- nt = net tax
                            account_tax AS nt
                            ON aml.tax_line_id = nt.id
                        LEFT JOIN
                            account_move_line_account_tax_rel AS amltr
                            ON aml.id = amltr.account_move_line_id
                        LEFT JOIN
                            -- bt = base tax
                            account_tax AS bt
                            ON amltr.account_tax_id = bt.id
                        LEFT JOIN
                            account_tax_group AS btg
                            ON btg.id = bt.tax_group_id
                        LEFT JOIN
                            account_tax_group AS ntg
                            ON ntg.id = nt.tax_group_id
                        LEFT JOIN
                            res_partner AS rp
                            ON rp.id = am.partner_id
                        LEFT JOIN
                          account_tip_doc as hg
                          ON hg.id = COALESCE(am.tipdocing,CASE WHEN am.move_type ='out_invoice' THEN 2 ELSE 1 END)
                        LEFT JOIN
                          account_journal as acj
                          ON acj.id = am.journal_id
                        WHERE
                            am.move_type in ('out_invoice', 'out_refund') 
                            AND hg.vatbook = 'true'
                            AND hg.tipdoc = 'sale'
                            AND am.state in ('""" + str(estado) + """')
                            and POSITION('-' IN am.name) > 0
                            AND am.company_id = """ + str(company) + """
                            AND am.invoice_date BETWEEN '%s' and '%s'
                       group by hg.name
                        
                                  """ % (fecha_inicio, fecha_fin)
            cr.execute(query)
            ventas = cr.fetchall()
            return ventas


class DownloadXLSIVAPy(http.Controller):
    @http.route('/getLibroIVA/<int:id>', auth='public')
    def generarXLSX(self, id=None, **kw):
        record = request.env['vat.book.wizard'].browse(id)
        movimientos = record.get_datos_iva1(record.fecha_inicio, record.fecha_fin, record.tipo_informe, record.state)
        cr = record.env.cr
        if record.tipo_informe == 'compra':
            company = record.company_id.id
            state = record.state
            estado = str(state).replace(", ", "', '")
            query = """
                         SELECT
                         am.invoice_date,
                         am.ref as move_name,
                         CASE WHEN am.state = 'cancel' THEN 'CANCELADO'
                         WHEN am.importacion_gasto is True THEN COALESCE(eca.name, rp.name)
                         ELSE  rp.name END as partner_name,
                         CASE WHEN am.state = 'cancel' THEN 'CANCELADO'
                         ELSE rp.vat END as ruc,
                         sum(CASE
                                WHEN aml.product_id = 2694 and am.state = 'posted' THEN (abs(aml.balance) * 11 ) - aml.balance   
                                WHEN btg.name = 'IVA 10%' and am.state = 'posted'THEN abs(aml.balance) 
                                ELSE 0 END) as base_10,
                         sum(CASE
                                WHEN aml.product_id = 2694 and am.state = 'posted' THEN abs(aml.balance)    
                                WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                                THEN abs(aml.balance) 
                                ELSE 0 END) as vat_10,
                         sum(CASE
                                WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                                THEN abs(aml.balance) ELSE 0 END) as base_5,
                         sum(CASE
                                WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                                THEN abs(aml.balance) ELSE 0 END) as vat_5,
                         sum(CASE
                                WHEN aml.product_id = 2694 and am.state = 'posted' THEN 0    
                                WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted' THEN abs(aml.balance) 
                                WHEN btg.name = 'Taxes' and am.state = 'posted'
                                THEN abs(aml.balance) 
                                ELSE 0 END) as not_taxed,
                         sum(CASE
                                WHEN aml.product_id = 2694 and am.state = 'posted' THEN (abs(aml.balance) * 11 ) - aml.balance   
                                WHEN btg.name = 'IVA 10%' and am.state = 'posted'
                                THEN abs(aml.balance) ELSE 0 END) +
                         sum(CASE
                                WHEN aml.product_id = 2694 and am.state = 'posted' THEN abs(aml.balance)    
                                WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                                THEN abs(aml.balance) ELSE 0 END) +
                         sum(CASE
                                WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                                THEN abs(aml.balance) ELSE 0 END) + 
                         sum(CASE
                                WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                                THEN abs(aml.balance) ELSE 0 END) +
                        sum(CASE
                                WHEN aml.product_id = 2694 and am.state = 'posted' THEN 0    
                                WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted'
                                THEN abs(aml.balance) 
                                WHEN btg.name = 'Taxes' and am.state = 'posted'
                                THEN abs(aml.balance) 
                                ELSE 0 END) as total,
                         am.py_timbrado_prov as timbrado,
                         hg.name as type_doc,
                         CASE
                                WHEN COALESCE(am.invoice_payment_term_id,1)  = 1
                                THEN 'Contado'
                                ELSE 'Crédito' END as payment_term,
                         am.id as move_id,
                         am.id,
                         am.move_type,
                         am.date,
                         am.partner_id,
                         am.journal_id,
                         am.name,
                         am.state,
                         am.company_id,   
                         hg.id as doc_id
                        FROM account_move_line aml
                        LEFT JOIN
                            account_move as am
                            ON aml.move_id = am.id
                        LEFT JOIN
                            -- nt = net tax
                            account_tax AS nt
                            ON aml.tax_line_id = nt.id
                        LEFT JOIN
                            account_move_line_account_tax_rel AS amltr
                            ON aml.id = amltr.account_move_line_id
                        LEFT JOIN
                            -- bt = base tax
                            account_tax AS bt
                            ON amltr.account_tax_id = bt.id
                        LEFT JOIN
                            account_tax_group AS btg
                            ON btg.id = bt.tax_group_id
                        LEFT JOIN
                            account_tax_group AS ntg
                            ON ntg.id = nt.tax_group_id
                        LEFT JOIN
                            res_partner AS rp
                            ON rp.id = am.partner_id
                        LEFT JOIN
                            res_partner AS eca
                            ON eca.id = am.partner_no_despachante
                        LEFT JOIN
                            account_tip_doc as hg
                            ON hg.id = am.tipdocgas
                        LEFT JOIN
                          account_journal as acj
                          ON acj.id = am.journal_id
                        WHERE
                            am.move_type in ('in_invoice', 'in_refund') 
                            AND hg.vatbook = 'true'
                            AND hg.tipdoc = 'purchase'
                            AND am.state in ('""" + str(estado) + """')
                            AND am.company_id = """ + str(company) + """
                            AND am.invoice_date BETWEEN '%s' and '%s'
                        GROUP BY
                            am.id, rp.id, hg.name,hg.id, eca.id
                        ORDER BY am.invoice_date asc, am.ref asc
                      """ % (record.fecha_inicio, record.fecha_fin)
            cr.execute(query)
        compras = cr.fetchall()
        if record.tipo_informe == 'venta':
            company = record.company_id.id
            state = record.state
            estado = str(state).replace(", ", "', '")
            query = """
                                     SELECT
                                     am.invoice_date,
                                     am.name as move_name,
                                     CASE WHEN am.state = 'cancel' THEN 'CANCELADO'
                                     ELSE rp.name END as partner_name,
                                     CASE WHEN am.state = 'cancel' THEN 'CANCELADO'
                                     ELSE rp.vat END as ruc,
                                     sum(CASE
                                            WHEN btg.name = 'IVA 10%' and am.state = 'posted'
                                            THEN (aml.balance * -1) ELSE 0 END) as base_10,
                                     sum(CASE
                                            WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                                            THEN (aml.balance * -1) ELSE 0 END) as vat_10,
                                     sum(CASE
                                            WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                                            THEN (aml.balance * -1) ELSE 0 END) as base_5,
                                     sum(CASE
                                            WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                                            THEN (aml.balance * -1) ELSE 0 END) as vat_5,
                                     sum(CASE
                                            WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted'
                                            THEN (aml.balance * -1) 
                                            WHEN btg.name = 'Taxes' and am.state = 'posted'
                                            THEN (aml.balance * -1) 
                                            ELSE 0 END) as not_taxed,
                                     sum(CASE
                                            WHEN btg.name = 'IVA 10%' and am.state = 'posted'
                                            THEN (aml.balance * -1) ELSE 0 END) +
                                     sum(CASE
                                            WHEN ntg.name = 'IVA 10%' and am.state = 'posted'
                                            THEN (aml.balance * -1) ELSE 0 END) +
                                     sum(CASE
                                            WHEN btg.name = 'IVA 5%' and am.state = 'posted'
                                            THEN (aml.balance * -1) ELSE 0 END) +
                                     sum(CASE
                                            WHEN ntg.name = 'IVA 5%' and am.state = 'posted'
                                            THEN (aml.balance * -1) ELSE 0 END) +
                                     sum(CASE
                                            WHEN (btg.name is null and aml.exclude_from_invoice_tab=false ) and am.state = 'posted'
                                            THEN (aml.balance * -1) 
                                            WHEN btg.name = 'Taxes' and am.state = 'posted'
                                            THEN (aml.balance * -1) 
                                            ELSE 0 END) as total,
                                     COALESCE(am.py_timbrado_prov, stam.name)                    AS timbrado,
                                     hg.name as type_doc,
                                     CASE
                                            WHEN COALESCE(am.invoice_payment_term_id,1)  = 1
                                            THEN 'Contado'
                                            ELSE 'Crédito' END as payment_term,
                                     am.id as move_id,
                                     am.id,
                                     am.move_type,
                                     am.date,
                                     am.partner_id,
                                     am.journal_id,
                                     am.name,
                                     am.state,
                                     am.company_id,   
                                     hg.id as doc_id
                                    FROM account_move_line aml
                                    LEFT JOIN
                                        account_move as am
                                        ON aml.move_id = am.id
                                    LEFT JOIN
                                        -- nt = net tax
                                        account_tax AS nt
                                        ON aml.tax_line_id = nt.id
                                    LEFT JOIN
                                        account_move_line_account_tax_rel AS amltr
                                        ON aml.id = amltr.account_move_line_id
                                    LEFT JOIN
                                        -- bt = base tax
                                        account_tax AS bt
                                        ON amltr.account_tax_id = bt.id
                                    LEFT JOIN
                                        account_tax_group AS btg
                                        ON btg.id = bt.tax_group_id
                                    LEFT JOIN
                                        account_tax_group AS ntg
                                        ON ntg.id = nt.tax_group_id
                                    LEFT JOIN
                                        res_partner AS rp
                                        ON rp.id = am.partner_id
                                    LEFT JOIN
                                      account_tip_doc as hg
                                      ON hg.id = COALESCE(am.tipdocing,CASE WHEN am.move_type ='out_invoice' THEN 2 ELSE 1 END)
                                    LEFT JOIN
                                      account_journal as acj
                                      ON acj.id = am.journal_id
                                    LEFT JOIN account_journal_stamped as stam
                                        ON stam.id = am.timbrado_id
                                    WHERE
                                        am.move_type in ('out_invoice', 'out_refund') 
                                        AND hg.vatbook = 'true'
                                        AND hg.tipdoc = 'sale'
                                        AND am.state in ('""" + str(estado) + """')
                                        and POSITION('-' IN am.name) > 0
                                        AND am.company_id = """ + str(company) + """
                                        AND am.invoice_date BETWEEN '%s' and '%s'
                                    GROUP BY
                                        am.id, rp.id, hg.name,hg.id, stam.name
                                    ORDER BY am.invoice_date asc, am.name asc
                                  """ % (record.fecha_inicio, record.fecha_fin)
            cr.execute(query)
        ventas = cr.fetchall()
        i = 5
        fp = io.BytesIO()
        workbook = xlsxwriter.Workbook(fp, {'in_memory': True})
        sheet = workbook.add_worksheet('Libro IVA')
        bold = workbook.add_format(
            {'bold': True, 'fg_color': 'white', 'align': 'center',
             'border': 1})
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
            'align': 'left',
            'valign': 'vleft',
            'font_color': 'black',
            'border': 1})
        merge_format3 = workbook.add_format({
            'align': 'left',
            'valign': 'vleft',
            'font_color': 'black'})
        merge_format6 = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_color': 'black'})
        number_format2 = workbook.add_format({'num_format': '#,##0'})
        sheet.merge_range('A1:B1', record.company_id.name, merge_format1)
        sheet.merge_range('A2:B2', record.company_id.vat, merge_format1)
        sheet.write(0, 11, 'Fecha', merge_format1)
        sheet.write(0, 12, record.fecha_de_hoy.strftime('%d-%m-%Y'),
                    merge_format1)
        sheet.write(1, 11, 'Hora', merge_format1)
        sheet.write(1, 12, record.fecha_de_hoy.strftime('%H:%M:%S'),
                    merge_format1)
        if record.tipo_informe == 'compra':
            sheet.merge_range('A3:M3', 'LIBRO COMPRA', merge_format)
        if record.tipo_informe == 'venta':
            sheet.merge_range('A3:M3', 'LIBRO VENTA', merge_format)
        sheet.write(3, 4, 'DEL', merge_format1)
        sheet.write(3, 5, record.fecha_inicio.strftime('%d-%m-%Y'),
                    merge_format1)
        sheet.write(3, 7, 'AL', merge_format1)
        sheet.write(3, 8, record.fecha_fin.strftime('%d-%m-%Y'),
                    merge_format1)
        sheet.set_column('A:M', 14)
        sheet.write(4, 0, 'Fecha', bold)
        sheet.write(4, 1, 'Numero', bold)
        sheet.write(4, 2, 'Razon Social', bold)
        sheet.write(4, 3, 'R.U.C.', bold)
        sheet.write(4, 4, 'Gravada 10%', bold)
        sheet.write(4, 5, 'IVA 10%', bold)
        sheet.write(4, 6, 'Gravada 5%', bold)
        sheet.write(4, 7, 'IVA 5%', bold)
        sheet.write(4, 8, 'EXENTAS', bold)
        sheet.write(4, 9, 'TOTAL', bold)
        sheet.write(4, 10, 'Timbrado', bold)
        sheet.write(4, 11, 'Tipo Documento', merge_format2)
        sheet.write(4, 12, 'Contado/Credito', merge_format2)
        total1 = 0
        total2 = 0
        total3 = 0
        total4 = 0
        total5 = 0
        total6 = 0

        if record.tipo_informe == 'compra':
            for eca in compras:
                sheet.write(i, 0, eca[0].strftime('%d-%m-%Y'), merge_format3)
                sheet.write(i, 1, eca[1], merge_format3)
                sheet.write(i, 2, eca[2], merge_format3)
                sheet.write(i, 3, eca[3], merge_format3)
                sheet.write(i, 4, eca[4], number_format2)
                total1 = total1 + eca[4]
                sheet.write(i, 5, eca[5], number_format2)
                total2 = total2 + eca[5]
                sheet.write(i, 6, eca[6], number_format2)
                total3 = total3 + eca[6]
                sheet.write(i, 7, eca[7], number_format2)
                total4 = total4 + eca[7]
                sheet.write(i, 8, eca[8], number_format2)
                total5 = total5 + eca[8]
                sheet.write(i, 9, eca[9], number_format2)
                total6 = total6 + eca[9]
                sheet.write(i, 10, eca[10], merge_format6)
                sheet.write(i, 11, eca[11], merge_format3)
                sheet.write(i, 12, eca[12], merge_format3)
                i = i + 1
        if record.tipo_informe == 'venta':
            for eca in ventas:
                sheet.write(i, 0, eca[0].strftime('%d-%m-%Y'), merge_format3)
                sheet.write(i, 1, eca[1], merge_format3)
                sheet.write(i, 2, eca[2], merge_format3)
                sheet.write(i, 3, eca[3], merge_format3)
                sheet.write(i, 4, eca[4], number_format2)
                total1 = total1 + eca[4]
                sheet.write(i, 5, eca[5], number_format2)
                total2 = total2 + eca[5]
                sheet.write(i, 6, eca[6], number_format2)
                total3 = total3 + eca[6]
                sheet.write(i, 7, eca[7], number_format2)
                total4 = total4 + eca[7]
                sheet.write(i, 8, eca[8], number_format2)
                total5 = total5 + eca[8]
                sheet.write(i, 9, eca[9], number_format2)
                total6 = total6 + eca[9]
                sheet.write(i, 10, eca[10], merge_format6)
                sheet.write(i, 11, eca[11], merge_format3)
                sheet.write(i, 12, eca[12], merge_format3)
                i = i + 1
        sheet.write(i, 0, 'TOTAL:', merge_format3)
        sheet.write(i, 4, total1, number_format2)
        sheet.write(i, 5, total2, number_format2)
        sheet.write(i, 6, total3, number_format2)
        sheet.write(i, 7, total4, number_format2)
        sheet.write(i, 8, total5, number_format2)
        sheet.write(i, 9, total6, number_format2)

        i = i + 4
        sheet.write(i, 6, 'RESUMEN', merge_format1)
        i = i + 1
        sheet.write(i, 3, 'Tipo Documento', merge_format2)
        sheet.write(i, 4, 'Gravada 10%', bold)
        sheet.write(i, 5, 'IVA 10%', bold)
        sheet.write(i, 6, 'Gravada 5%', bold)
        sheet.write(i, 7, 'IVA 5%', bold)
        sheet.write(i, 8, 'EXENTAS', bold)
        sheet.write(i, 9, 'TOTAL', bold)
        i = i + 1
        for m in movimientos:
            sheet.write(i, 3, m[6], merge_format3)
            sheet.write(i, 4, m[0], number_format2)
            sheet.write(i, 5, m[1], number_format2)
            sheet.write(i, 6, m[2], number_format2)
            sheet.write(i, 7, m[3], number_format2)
            sheet.write(i, 8, m[4], number_format2)
            sheet.write(i, 9, m[5], number_format2)
            i = i + 1

        workbook.close()
        fp.seek(0)
        return request.make_response(fp.read(),
                                     [('Content-Type',
                                       'application/vnd.'
                                       'openxmlformats-officedocument.'
                                       'spreadsheetml.sheet'),
                                      ('Content-Disposition',
                                       content_disposition(
                                           'libro_iva.xlsx'))])
