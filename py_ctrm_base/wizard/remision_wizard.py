# -*- coding: utf-8 -*-
from odoo import fields, models, exceptions, api
from datetime import datetime, timedelta
from lxml import etree
from odoo.exceptions import ValidationError


class wizard_remision(models.TransientModel):

    _name = 'wizard.remision'
    _description = __doc__

    picking_id=fields.Many2one('stock.picking',string="Envio")
    assign_number=fields.Char(compute='get_stamp_number',string="Esta remision tendrá el numero:")
    company_id = fields.Many2one('res.company',
                                 default=1,
                                 string='Compañia')


    def _get_company(self):
        return self.env.user.company_id.id


    @api.model
    def _get_stamp_journal(self):
        journal = None
        journal = self.env['account.journal.stamped'].search(
                [['type', '=', 2], ['state', '=', 'active'],
                 ['company_id', '=', self._get_company()]])
        return journal

    stamp_journal = fields.Many2one('account.journal.stamped', string="Talonario",
                                    default=_get_stamp_journal,
                                         domain=[('type', '=', 2),
                                                 ('state', '=', 'active')])



    @api.depends('stamp_journal','stamp_journal.current_number')
    def get_stamp_number(self):
        if self.stamp_journal:
            fmt = '%Y-%m-%d'

            d1 = datetime.strptime(str(datetime.now().date()), '%Y-%m-%d')
            # fecha = datetime.strftime(fechas, "%Y/%m/%d")
            # d1 = datetime.strptime(str(datetime.now().date()), fmt)

            d2 = datetime.strptime(str(self.stamp_journal.date_range_end), '%Y-%m-%d')
            d3 = datetime.strptime(str(self.stamp_journal.date_range_ini), '%Y-%m-%d')
            daysDiff = (d2 - d1).days

            dias_anti = (d3 - d1).days
            # raise ValidationError(self.talonario_remision.suc)
            # raise ValidationError('Timbrado ya se encuentra vencido %s' % daysDiff)
            if daysDiff < 0:
                raise ValidationError('Timbrado ya se encuentra vencido.')
            elif dias_anti > 0:
                raise ValidationError('Fecha inicio de timbrado es mayor a la fecha actual')
            estab = self.stamp_journal.establishment_code
            exp_point = self.stamp_journal.shipping_point
            current_number = self.stamp_journal.current_number + 1

            nro_s = str(current_number)
            cant_nro = len(nro_s)
            if cant_nro == 1:
                nro_final = '000000' + nro_s
            elif cant_nro == 2:
                nro_final = '00000' + nro_s
            elif cant_nro == 3:
                nro_final = '0000' + nro_s
            elif cant_nro == 4:
                nro_final = '000' + nro_s
            elif cant_nro == 5:
                nro_final = '00' + nro_s
            elif cant_nro == 6:
                nro_final = '0' + nro_s
            else:
                nro_final = nro_s

            self.assign_number = str(estab) + '-' + str(exp_point) + '-' + str(nro_final)


    def procesar(self):
        for rec in self.picking_id:
            if self.stamp_journal:
                fmt = '%Y-%m-%d'

                d1 = datetime.strptime(str(datetime.now().date()), '%Y-%m-%d')
                # fecha = datetime.strftime(fechas, "%Y/%m/%d")
                # d1 = datetime.strptime(str(datetime.now().date()), fmt)

                d2 = datetime.strptime(str(self.stamp_journal.date_range_end), '%Y-%m-%d')
                d3 = datetime.strptime(str(self.stamp_journal.date_range_ini), '%Y-%m-%d')
                daysDiff = (d2 - d1).days

                dias_anti = (d3 - d1).days
                # raise ValidationError(self.talonario_remision.suc)
                # raise ValidationError('Timbrado ya se encuentra vencido %s' % daysDiff)
                if daysDiff < 0:
                    raise ValidationError('Timbrado ya se encuentra vencido.')
                elif dias_anti > 0:
                    raise ValidationError('Fecha inicio de timbrado es may(or a la fecha actual')
                estab = self.stamp_journal.establishment_code
                exp_point = self.stamp_journal.shipping_point
                nro = self.stamp_journal.current_number + 1

                nro_s = str(nro)
                cant_nro = len(nro_s)
                if cant_nro == 1:
                    nro_final = '000000' + nro_s
                elif cant_nro == 2:
                    nro_final = '00000' + nro_s
                elif cant_nro == 3:
                    nro_final = '0000' + nro_s
                elif cant_nro == 4:
                    nro_final = '000' + nro_s
                elif cant_nro == 5:
                    nro_final = '00' + nro_s
                elif cant_nro == 6:
                    nro_final = '0' + nro_s
                else:
                    nro_final = nro_s
                remision=str(estab) + '-' + str(exp_point) + '-' + str(nro_final)
                rec.write({'remision':remision,'stamp_journal_timb':self.stamp_journal.name,'stamp_journal':self.stamp_journal.id})
                self.stamp_journal.write({'number_used': self.stamp_journal.current_number,
                                           'current_number': self.stamp_journal.current_number + 1})


