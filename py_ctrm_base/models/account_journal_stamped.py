# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo import fields, models, api, _
from datetime import datetime, timedelta


class documentos_timbrados(models.Model):
    _name = "account.journal.stamped"

    name = fields.Char(string="Número de Timbrado", required=True, unique=True, size=8)
    description = fields.Char(string="Documento", required=True)
    type = fields.Selection([
        ('1', 'Factura'),
        ('2', 'Remisiones'),
        ('3', 'Retencion'),
        ('4', 'Nota de Credito'),
        ('5', 'Autofactura')],
        string="Tipo Comprobante", required=True)

    # document_type_id = fields.Many2one(
    #    'account.tip.doc',
    #    domain=[('req_timbrado', '=', True)],
    #    help='Indica el tipo de comprobante para el que aplica el timbrado',
    #    required=True,
    #    string='Comprobante Asociado'
    # )
    establishment_code = fields.Char(string='Establecimiento', size=3, required=True, default='001')
    shipping_point = fields.Char(string='Punto Expedicion', size=3, required=True, default='001')
    number_ini = fields.Integer(string='Rango Desde', size=7, required=True)
    number_max = fields.Integer(string='Rango Hasta', size=7, required=True)
    date_range_ini = fields.Date(string='Vigencia Desde', required=True)
    date_range_end = fields.Date(string='Vigencia Hasta', required=True)
    current_number = fields.Integer(string='Próximo número', size=7)
    number_used = fields.Integer(string="Ultimo numero utilizado")
    company_id = fields.Many2one('res.company', 'Compañía', required=True, index=True, default=lambda self: self.env.company)
    state = fields.Selection(
        [('draft', 'Borrador'),
         ('active', 'Activo'),
         ('no_active', 'No Activo')],
        default='draft',
        string="Estado"
    )

    def _get_company(self):
        return self.env.user.company_id

    _sql_constraints = [
        ('talonario_timbrado_uniq',
         'unique(type,establishment,expedition_point,number_ini,number_max,date_range_ini,date_range_end)',
         "Este talonario ya se encuentra registrado; favor verifique!.")]

    # _sql_constraints = [
    #     ('numero_factura_uniq', 'unique(sec,suc,nro, partner_id, timbrado, date_invoice)',
    #      "Esta factura ya se encuentra cargada en el sistema! Verifique datos."),
    # ]

    @api.constrains('state')
    def esta_activo(self):
        state = self.state
        if state:
            tal = self.env['account.journal.stamped'].search([('company_id', '=', self.company_id.id),
                                                              ('type', '=', self.type),
                                                              ('name', '=', self.name),
                                                              ('state', '=', 'active'),
                                                              ('establishment_code', '=', self.establishment_code),
                                                              ('shipping_point', '=', self.shipping_point)])
            if tal:
                for talos in tal:
                    if talos.id != self.id:
                        raise ValidationError('No se pueden tener dos talonarios del mismo tipo activos en el sistema')

    def name_get(self):
        result = []
        for inv in self:
            result.append(
                (inv.id, "%s - %s" % (inv.name, inv.description)))
        return result

    @api.constrains('number_ini')
    def first_number(self):
        if self.number_ini:
            if self.number_max:
                if self.number_ini > self.number_max:
                    raise ValidationError('Numero de inicio debe ser menor al numero final')
            else:
                raise ValidationError('Debe haber un numero de finalización de timbrado')
        else:
            raise ValidationError('Debe haber un numero de inicio')

    @api.constrains('number_max')
    def max_number(self):
        if self.number_max:
            if self.number_max < self.number_ini:
                raise ValidationError('Numero Final debe ser mayor al numero de inicio')
        else:
            raise ValidationError('Debe haber un numero de finalización de timbrado')

    @api.constrains('current_number')
    def current_numbers(self):
        if self.current_number:
            if self.current_number < self.number_ini:
                raise ValidationError('Numero actual debe ser mayor o igual que numero de inicio')
            elif self.current_number > (self.number_max + 1):
                raise ValidationError('Numero actual debe ser menor o igual que numero final')

    @api.onchange('state', 'date_range_ini', 'date_range_end', 'current_number')
    def _chec_date(self):
        if self.date_range_ini and self.date_range_end:
            d1 = datetime.strptime(str(datetime.now().date()), '%Y-%m-%d')
            # fecha = datetime.strftime(fechas, "%Y/%m/%d")
            # d1 = datetime.strptime(str(datetime.now().date()), fmt)
            d2 = datetime.strptime(str(self.date_range_end), '%Y-%m-%d')
            d3 = datetime.strptime(str(self.date_range_ini), '%Y-%m-%d')
            daysDiff = (d2 - d1).days

            dias_anti = (d3 - d1).days

            between_days = (d2 - d3).days

            if between_days < 0:
                raise ValidationError(
                    'Fecha de Expiracion de Timbrado debe ser mayor a la fecha de Inicio')

            # raise ValidationError('Timbrado ya se encuentra vencido %s' % daysDiff)
            if self.state == 'active':
                if daysDiff < 0:
                    raise ValidationError('Timbrado ya se encuentra vencido.')
                # elif dias_anti > 0:
                #     raise ValidationError('Fecha inicio de timbrado es mayor a la fecha actual')

                # and (self.fecha_inicio < datetime.now() or self.fecha_final > datetime.now()) :

    #            raise exceptions.ValidationError("No se puede Activar un documento timbrado con Fecha menor a la Fecha de Inicio o Fecha mayor a la fecha de Expiracion. Verifique Fechas o cargue el documento como inactivo")

    def validate_timbrado_all(self, today=False):
        """ Chequear la validez de todos los timbrados
            el parametro today=False es para los tests
        """
        if not today:
            today = fields.Date.today()
        for rec in self:
            if rec.date_range_ini <= today <= rec.date_range_end:
                rec.state = 'active'
            else:
                rec.state = 'no_active'
