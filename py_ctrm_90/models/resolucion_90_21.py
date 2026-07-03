# -*- coding: utf-8 -*-
from odoo import fields, models, exceptions, api
import time, collections
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
from collections import defaultdict
import base64
import io
import logging
import xlsxwriter
from odoo import http, _
from odoo.http import request
from odoo.addons.web.controllers.main import serialize_exception, content_disposition
import operator

CANT_REGISTROS_RESOLUCION = 15000

MESES = [
    ('01', 'Enero'),
    ('02', 'Febrero'),
    ('03', 'Marzo'),
    ('04', 'Abril'),
    ('05', 'Mayo'),
    ('06', 'Junio'),
    ('07', 'Julio'),
    ('08', 'Agosto'),
    ('09', 'Septiembre'),
    ('10', 'Octubre'),
    ('11', 'Noviembre'),
    ('12', 'Diciembre'), ]


def chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]


_logger = logging.getLogger(__name__)


class Resolucion90Archivos(models.Model):
    _name = 'set.resolucion90.archivo'

    name = fields.Char(string="Name")
    archivo = fields.Binary(string="Archivo")
    anio = fields.Integer(string="Año")
    nombre = fields.Char(string="Nombre")
    mes = fields.Char(string="Mes")
    periodo = fields.Integer(string="Periodo")
    filename = fields.Char(string="Nombre archivo")
    fecha_creacion = fields.Datetime(string='Fecha', default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)


class WizardReport9021(models.TransientModel):
    _name = "resolucion.90.21"

    name = fields.Char(string="Nombre")
    mes = fields.Selection(
        [('01', 'Enero'), ('02', 'Febrero'), ('03', 'Marzo'), ('04', 'Abril'), ('05', 'Mayo'), ('06', 'Junio'),
         ('07', 'Julio'), ('08', 'Agosto'), ('09', 'Setiembre'), ('10', 'Octubre'), ('11', 'Noviembre'),
         ('12', 'Diciembre')], string="Mes")
    tipo = fields.Selection(
        [('sale', 'Venta'),
         ('purchase', 'Compra')],
        string="Tipo")
    periodo = fields.Integer(string="Periodo")
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    archivo = fields.Binary(string="Archivo generado")

    def generar_informe(self):
        if self.tipo == 'sale':
            archivo = self.generar_ventas()
            self.archivo = archivo
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        elif self.tipo == 'purchase':
            archivo = self.generar_compras()
            self.archivo = archivo
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }

    def generar_ventas(self):
        company = self.env.company.id
        cr = self.env.cr
        query = """
                    SELECT    
                         1 AS tipo_registro,
                         rpad(CASE
                                WHEN rp.consumidor_final = True THEN '15'
                                WHEN position('-' IN rp.vat) != 0 THEN '11'
                                ELSE '12' END, 2) AS codigo_identificacion,
                         rpad(CASE
                                WHEN rp.consumidor_final = True THEN '44444401'
                                WHEN position('-' IN rp.vat) != 0 THEN substring(rp.vat,0,position('-' IN rp.vat))
                                ELSE substring(rp.vat, 0, 8) END, 20) AS numero_identificacion,
                         rpad(CASE
                                WHEN rp.consumidor_final = True THEN 'X'
                                ELSE '' END, 250) AS razon_social,
                         rpad(CASE 
                                WHEN am.move_type = 'in_refund' THEN '110'
                                ELSE hg.code_90 END, 3) AS codigo_comprobante,
                         rpad(to_char(am.invoice_date, 'dd/MM/yyyy'),10) fecha_comprobante,
                         rpad(COALESCE(am.py_timbrado_prov, stam.name), 8) AS numero_timbrado,
                         rpad(CASE 
                                WHEN am.move_type = 'in_refund' THEN am.ref
                                ELSE am.name END, 20) AS move_name,
                         rpad(cast(sum(CASE 
                                        WHEN btg.NAME = 'IVA 10%' THEN abs(round(aml.balance))
                                        ELSE 0 END) + 
                                    sum(CASE 
                                        WHEN ntg.NAME = 'IVA 10%' THEN abs(round(aml.balance)) 
                                        ELSE 0 END)as varchar), 20) AS total_base_10,
                         rpad(cast(sum(CASE 
                                        WHEN btg.NAME = 'IVA 5%' THEN abs(round(aml.balance))
                                        ELSE 0 END) + 
                                    sum(CASE 
                                        WHEN ntg.NAME = 'IVA 5%' THEN abs(round(aml.balance)) 
                                        ELSE 0 END) as varchar), 20) AS total_base_5,
                         rpad(cast(sum(CASE
                                        WHEN (btg.NAME IS NULL AND aml.exclude_from_invoice_tab=false ) THEN abs(round(aml.balance))
                                        WHEN btg.NAME = 'Taxes' THEN abs(round(aml.balance))
                                        ELSE 0 END)as varchar), 20) AS exento,      
                         rpad(cast(sum(CASE 
                                        WHEN btg.NAME = 'IVA 10%' THEN abs(round(aml.balance))
                                        ELSE 0 END) + 
                                    sum(CASE 
                                        WHEN ntg.NAME = 'IVA 10%' THEN abs(round(aml.balance)) 
                                        ELSE 0 END) +
                                    sum(CASE 
                                        WHEN btg.NAME = 'IVA 5%' THEN abs(round(aml.balance))
                                        ELSE 0 END) + 
                                    sum(CASE 
                                        WHEN ntg.NAME = 'IVA 5%' THEN abs(round(aml.balance)) 
                                        ELSE 0 END) + 
                                    sum(CASE 
                                        WHEN ( btg.NAME IS NULL AND aml.exclude_from_invoice_tab=false ) THEN abs(round(aml.balance)) 
                                        WHEN btg.NAME = 'Taxes' THEN abs(round(aml.balance)) 
                                        ELSE 0 END)as varchar), 20) AS monto_total_comprobante, 
                         rpad(CASE
                                WHEN COALESCE(am.invoice_payment_term_id,1) = 1 THEN '1'
                                ELSE '2' END, 1) AS condicion_venta,
                         rpad(CASE
                                WHEN COALESCE(am.currency_id,163) = 163 THEN 'N'
                                ELSE 'S' END, 1) AS moneda_extranjera,
                         rpad(CASE
                                WHEN compa.imputa_iva is True THEN 'S'
                                ELSE 'N' END, 1) AS imputa_iva,
                         rpad(CASE
                                WHEN compa.imputa_ire is True THEN 'S'
                                ELSE 'N' END, 1) AS imputa_ire,
                         rpad(CASE
                                WHEN compa.imputa_irp is True THEN 'S'
                                ELSE 'N' END, 1) AS imputa_irp,
                         rpad(CASE
                            WHEN am.move_type = 'in_refund' THEN am.nota_credito_asociada
                            ELSE '' END, 20) as comprobante_asociado,
                         rpad(CASE
                            WHEN am.move_type = 'in_refund' THEN am.py_timbrado_prov
                            ELSE '' END, 8) as timbrado_asociado                     
                    FROM account_move_line aml
                        LEFT JOIN account_move as am ON aml.move_id = am.id
                        LEFT JOIN res_company as compa ON am.company_id = compa.id
                        LEFT JOIN account_tax AS nt ON aml.tax_line_id = nt.id
                        LEFT JOIN account_move_line_account_tax_rel AS amltr ON aml.id = amltr.account_move_line_id
                        LEFT JOIN account_tax AS bt ON amltr.account_tax_id = bt.id
                        LEFT JOIN account_tax_group AS btg ON btg.id = bt.tax_group_id
                        LEFT JOIN account_tax_group AS ntg ON ntg.id = nt.tax_group_id
                        LEFT JOIN res_partner AS rp ON rp.id = am.partner_id
                        LEFT JOIN account_tip_doc as hg ON hg.id = am.tipdocing
                        LEFT JOIN account_journal as acj ON acj.id = am.journal_id
                        LEFT JOIN account_journal_stamped as stam ON stam.id = am.timbrado_id
                    WHERE 
                        am.move_type in ('out_invoice', 'in_refund') 
                        AND COALESCE(hg.vatbook,'true') = 'true'
                        AND am.state = 'posted'
                        AND extract(month FROM am.invoice_date) = """ + str(self.mes) + """
                        AND extract(year FROM am.invoice_date) = """ + str(self.periodo) + """
                        AND am.company_id = """ + str(company) + """
                    GROUP BY  
                        am.id,
                        rp.id,
                        hg.NAME,
                        hg.id,
                        compa.id,
                        stam.name
                        """
        cr.execute(query)
        ventas = cr.fetchall()
        nombre_mes = self.mes
        for m in MESES:
            if m[0] == self.mes:
                nombre_mes = m[1]
        cant_archivos = list(chunks(ventas, CANT_REGISTROS_RESOLUCION))
        try:
            unicode('')
        except NameError:
            unicode = str
        archivo = None
        texto = []
        for ii, ventas in enumerate(cant_archivos):
            texto.append(u'')
            for c in ventas:
                aa = list()
                for i, x in enumerate(c):
                    if i > 7 and i < 12:
                        aa.append("".join(unicode(abs(int(x)))))
                    else:
                        aa.append("".join(unicode(x)))
                texto.append("\t".join([unicode(x) for x in aa]))
        encabezado = ['CÓDIGO TIPO DE REGISTRO ',
                      'CÓDIGO TIPO DE IDENTIFICACIÓN DEL COMPRADOR',
                      'NÚMERO DE IDENTIFICACIÓN DEL COMPRADOR',
                      'NOMBRE O RAZÓN SOCIAL DEL COMPRADOR',
                      'CÓDIGO TIPO DE COMPROBANTE',
                      'FECHA DE EMISIÓN DEL COMPROBANTE',
                      'NÚMERO DE TIMBRADO',
                      'NÚMERO DEL COMPROBANTE',
                      'MONTO GRAVADO AL 10% (IVA INCLUIDO)',
                      'MONTO GRAVADO AL 5% (IVA INCLUIDO)',
                      'MONTO NO GRAVADO O EXENTO',
                      'MONTO TOTAL DEL COMPROBANTE',
                      'CÓDIGO CONDICIÓN DE VENTA',
                      'OPERACIÓN EN MONEDA EXTRANJERA',
                      'IMPUTA AL IVA',
                      'IMPUTA AL IRE ',
                      'IMPUTA AL IRP-RSP',
                      'NÚMERO DEL COMPROBANTE DE VENTA ASOCIADO',
                      'TIMBRADO DEL COMPROBANTE DE VENTA ASOCIADO'
                      ]

        texto[0] = ("\t".join(encabezado))
        contenido = ("\n".join(texto)).encode('utf-8')
        archivo = base64.b64encode(contenido)
        values_type = [('sale', 'Ventas'), ('purchase', 'Compras'), ('income', 'Ingreso'), ('egress', 'Egreso')]
        filename = str(self.env.company.vat[0:-2]) + '_REG_' + self.mes + str(self.periodo) + '_V0001_' + str(
            dict(values_type)[self.tipo]) + '.txt'
        self.name = filename
        archi = self.env['set.resolucion90.archivo']
        aviejo = archi.search([('filename', '=', filename)])
        for a in aviejo:
            a.unlink()
        datos = {
            'archivo': base64.b64encode(contenido),
            'name': str(self.periodo) + str(self.mes),
            'nombre': filename,
            'mes': nombre_mes,
            'anio': self.periodo,
            'filename': filename,
        }
        archi.create(datos)

        if not archivo:
            raise ValidationError(
                'No se han encontrado registros. '
                'Verifique que las Facturas de Compra o Notas de Credito correspondiente'
                ' al mes seleccionado se encuentren en estado Validado o Pagado')
        return archivo

    def generar_compras(self):
        company = self.env.company.id
        cr = self.env.cr
        query = """
                SELECT    
                    2 AS tipo_registro,
                    rpad('11', 2) AS codigo_identificacion,
                    rpad(CASE
                            WHEN am.move_type IN ('in_invoice', 'out_refund') and COALESCE(am.importacion_gasto, false) = 'false' THEN substring(rp.vat, 0,position('-' IN rp.vat))
                            ELSE substring(eca.vat,0,position('-' IN eca.vat)) END, 20) AS numero_identificacion,
                    rpad('', 250) AS razon_social,
                    rpad(CASE 
                            WHEN am.move_type = 'out_refund' THEN '110'
                            ELSE hg.code_90 END, 3) AS codigo_comprobante,
                    rpad(to_char(am.invoice_date, 'dd/MM/yyyy'), 10) AS fecha_comprobante,
                    rpad(COALESCE(am.py_timbrado_prov, stam.name), 8) AS numero_timbrado,
                    rpad(CASE 
                            WHEN am.move_type = 'out_refund' THEN am.name
                            ELSE am.ref END, 20) AS move_name,
                    rpad(cast(sum(CASE 
                                    WHEN btg.NAME = 'IVA 10%' THEN abs(round(aml.balance))
                                    ELSE 0 END) + 
                               sum(CASE 
                                    WHEN ntg.NAME = 'IVA 10%' THEN abs(round(aml.balance)) 
                                    ELSE 0 END)as varchar), 20) AS total_base_10,
                    rpad(cast(sum(CASE 
                                    WHEN btg.NAME = 'IVA 5%' THEN abs(round(aml.balance))
                                    ELSE 0 END) + 
                                sum(CASE 
                                    WHEN ntg.NAME = 'IVA 5%' THEN abs(round(aml.balance)) 
                                    ELSE 0 END) as varchar), 20) AS total_base_5,
                    rpad(cast(sum(CASE
                                    WHEN (btg.NAME IS NULL AND aml.exclude_from_invoice_tab=false ) THEN abs(round(aml.balance))
                                    WHEN btg.NAME = 'Taxes' THEN abs(round(aml.balance))
                                    ELSE 0 END)as varchar), 20) AS exento,      
                    rpad(cast(sum(CASE 
                                    WHEN btg.NAME = 'IVA 10%' THEN abs(round(aml.balance))
                                    ELSE 0 END) + 
                                sum(CASE 
                                    WHEN ntg.NAME = 'IVA 10%' THEN abs(round(aml.balance)) 
                                    ELSE 0 END) +
                                sum(CASE 
                                    WHEN btg.NAME = 'IVA 5%' THEN abs(round(aml.balance))
                                    ELSE 0 END) + 
                                sum(CASE 
                                    WHEN ntg.NAME = 'IVA 5%' THEN abs(round(aml.balance)) 
                                    ELSE 0 END) + 
                                sum(CASE 
                                    WHEN ( btg.NAME IS NULL AND aml.exclude_from_invoice_tab=false ) THEN abs(round(aml.balance)) 
                                    WHEN btg.NAME = 'Taxes' THEN abs(round(aml.balance)) 
                                    ELSE 0 END)as varchar), 20) AS monto_total_comprobante,
                    rpad(CASE
                            WHEN COALESCE(am.invoice_payment_term_id,1) = 1 THEN '1'
                            ELSE '2' END, 1) AS condicion_compra,
                    rpad(CASE
                            WHEN COALESCE(am.currency_id,163) = 163 THEN 'N'
                            ELSE 'S' END, 1) AS moneda_extranjera,
                    rpad(CASE
                            WHEN am.imputa_iva is True THEN 'S'
                            ELSE 'N' END, 1) AS imputa_iva,
                    rpad(CASE
                            WHEN am.imputa_ire is True THEN 'S'
                            ELSE 'N' END, 1) AS imputa_ire,
                    rpad(CASE
                            WHEN am.imputa_irp is True THEN 'S'
                            ELSE 'N' END, 1) AS imputa_irp,
                    rpad(CASE
                            WHEN am.no_imputa = 'no_imputa' THEN 'N'
                            ELSE 'S' END, 1) AS no_imputa,
                    rpad(CASE
                            WHEN am.move_type = 'out_refund' THEN am.nota_credito_asociada
                            ELSE '' END, 20) as comprobante_asociado,
                     rpad(CASE
                            WHEN am.move_type = 'out_refund' THEN stam.name
                            ELSE '' END, 8) as timbrado_asociado        
                FROM account_move_line aml
                    LEFT JOIN account_move as am ON aml.move_id = am.id
                    LEFT JOIN res_company as compa ON am.company_id = compa.id
                    LEFT JOIN account_tax AS nt ON aml.tax_line_id = nt.id
                    LEFT JOIN account_move_line_account_tax_rel AS amltr ON aml.id = amltr.account_move_line_id
                    LEFT JOIN account_tax AS bt ON amltr.account_tax_id = bt.id
                    LEFT JOIN account_tax_group AS btg ON btg.id = bt.tax_group_id
                    LEFT JOIN account_tax_group AS ntg ON ntg.id = nt.tax_group_id
                    LEFT JOIN res_partner AS rp ON rp.id = am.partner_id
                    LEFT JOIN account_tip_doc as hg ON hg.id = am.tipdocgas 
                    LEFT JOIN account_journal as acj ON acj.id = am.journal_id
                    LEFT JOIN account_journal_stamped as stam ON stam.id = am.timbrado_id
                    LEFT JOIN res_partner AS eca ON eca.id = am.partner_no_despachante
                WHERE
                    am.move_type in ('in_invoice', 'out_refund')
                    AND COALESCE(hg.vatbook,'false') = 'true'
                    AND am.state = 'posted'
                    AND COALESCE(am.factura_electronica, false) = 'false'
                    AND extract(month FROM am.invoice_date) = """ + str(self.mes) + """
                    AND extract(year FROM am.invoice_date) = """ + str(self.periodo) + """
                    AND am.company_id = """ + str(company) + """
                GROUP BY  
                    am.id,
                    rp.id,
                    hg.NAME,
                    hg.id,
                    compa.id,
                    stam.name,
                    eca.id

                        """
        cr.execute(query)
        compras = cr.fetchall()
        nombre_mes = self.mes
        for m in MESES:
            if m[0] == self.mes:
                nombre_mes = m[1]
        cant_archivos1 = list(chunks(compras, CANT_REGISTROS_RESOLUCION))
        try:
            unicode('')
        except NameError:
            unicode = str
        archivo = None
        texto = []
        for ii, compras in enumerate(cant_archivos1):
            texto.append(u'')
            for c in compras:
                aa = list()
                for i, x in enumerate(c):
                    if i > 7 and i < 12:
                        aa.append("".join(unicode(abs(int(x)))))
                    else:
                        aa.append("".join(unicode(x)))
                texto.append("\t".join([unicode(x) for x in aa]))
        encabezado = ['CÓDIGO TIPO DE REGISTRO ',
                      'CÓDIGO TIPO DE IDENTIFICACIÓN DEL PROVEEDOR/VENDEDOR',
                      'NÚMERO DE IDENTIFICACIÓN DEL PROVEEDOR/VENDEDOR',
                      'NOMBRE O RAZÓN SOCIAL DEL PROVEEDOR/VENDEDOR',
                      'CÓDIGO TIPO DE COMPROBANTE',
                      'FECHA DE EMISIÓN DEL COMPROBANTE',
                      'NÚMERO DE TIMBRADO',
                      'NÚMERO DEL COMPROBANTE',
                      'MONTO GRAVADO AL 10% (IVA INCLUIDO)',
                      'MONTO GRAVADO AL 5% (IVA INCLUIDO)',
                      'MONTO NO GRAVADO O EXENTO',
                      'MONTO TOTAL DEL COMPROBANTE',
                      'CÓDIGO CONDICIÓN DE VENTA',
                      'OPERACIÓN EN MONEDA EXTRANJERA',
                      'IMPUTA AL IVA',
                      'IMPUTA AL IRE ',
                      'IMPUTA AL IRP-RSP',
                      'NO IMPUTA',
                      'NÚMERO DEL COMPROBANTE DE VENTA ASOCIADO',
                      'TIMBRADO DEL COMPROBANTE DE VENTA ASOCIADO'
                      ]
        texto[0] = ("\t".join(encabezado))
        contenido = ("\n".join(texto)).encode('utf-8')
        archivo = base64.b64encode(contenido)
        values_type = [('sale', 'Ventas'), ('purchase', 'Compras'), ('income', 'Ingreso'), ('egress', 'Egreso')]
        filename = str(self.env.company.vat[0:-2]) + '_REG_' + self.mes + str(self.periodo) + '_V0001_' + str(
            dict(values_type)[self.tipo]) + '.txt'
        self.name = filename
        archi = self.env['set.resolucion90.archivo']
        aviejo = archi.search([('filename', '=', filename)])
        for a in aviejo:
            a.unlink()
        datos = {
            'archivo': base64.b64encode(contenido),
            'name': str(self.periodo) + str(self.mes),
            'nombre': filename,
            'mes': nombre_mes,
            'anio': self.periodo,
            'filename': filename,
        }
        archi.create(datos)

        if not archivo:
            raise ValidationError(
                'No se han encontrado registros. '
                'Verifique que las Facturas de Compra o Notas de Credito correspondiente'
                ' al mes seleccionado se encuentren en estado Validado o Pagado')
        return archivo
