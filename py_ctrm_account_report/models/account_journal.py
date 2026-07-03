# -*- coding: utf-8 -*-
from odoo import fields, models, exceptions, api


class DiarioCobros(models.Model):
    _inherit = "account.journal"

    tipo_reporte = fields.Selection([('Efectivo Gs', 'Efectivo en Guaranies'),
                                     ('Efectivo USD', 'Efectivo en Dolares'),
                                     ('Cheques', 'Cheques'),
                                     ('Tarjeta de Credito', 'Tarjeta de Credito'),
                                     ('Tarjeta de debito', 'Tarjeta de debito'),
                                     ('Retencion', 'Retencion'),
                                     ('Canje', 'Canje'),
                                     ('Diferencia de Cambio', 'Diferencia de Cambio'),
                                     ('Transferencia', 'Transferencia')],
                                    string='Tipo Reporte')
