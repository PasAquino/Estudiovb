# For copyright and license notices, see __manifest__.py file in module root

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Partner(models.Model):
    _inherit = 'res.partner'

    #@api.constrains('vat')
    #def verificar_duplicados(self):
    #    ruc = list(map(lambda x: x.vat, self))
    #    rucs = self.env['res.partner'].search([('vat', '=', ruc[0]), ('type', '!=', 'delivery')])
    #    if len(rucs) > 1:
    #        raise ValidationError(
    #                        'Ya se encuentra cargado un registro con ese RUC/CI. Verifique datos')

    #    if self.country_id == self.env.ref('base.py'):
    #        if not self.parent_id:
    #            if not self.vat:
    #                raise ValidationError(
    #                    'Debe cargar el RUC/CI. Verifique datos')
    #            if self.vat == '99999901-0' or self.vat == '77777701-0' or not self.vat:
    #                a = 1
    #            else:
    #                rucs = self.env['res.partner'].search([('vat', '=', self.vat)])
    #                if len(rucs) > 1:
    #                    raise ValidationError(
    #                        'Ya se encuentra cargado un registro con ese RUC/CI. Verifique datos')

    @api.constrains('vat')
    def check_ruc(self):
        for record in self:
            if record.country_id == record.env.ref('base.py'):
                if record.vat != '99999901-0' or record.vat == '77777701-0':
                    for rec in self:
                        if rec.vat:
                            count = 0
                            for i in rec.vat:
                                if i == '-':
                                    count = count + 1
                            if count == 1:
                                if not record._check_ruc(rec.vat):
                                    raise ValidationError(_("El RUC es invalido"))

    def _check_ruc(self, ruc):
        """ Chequea validez de RUC calculando el digito verificador
        """
        if not ruc:
            return True

        if ruc.find('-') < 0:
            # no tiene guion, ya es invalido.
            return False

        # obtengo el numero antes del guion y el dv despues del guion
        numero = ruc[:ruc.find('-')]
        dv = ruc[ruc.find('-')+1:]

        # verifico que los dos sean numeros, sino ya es invalido
        try:
            numero = int(numero)
            dv = int(dv)
        except ValueError:
            return False

        # verifico que el dv sea igual al calculado
        return dv == self._calc_dv(numero)

    @staticmethod
    def _calc_dv(ruc):
        """
            Función que calcula el dígito verificador en Python
            autor: Blas Isaias Fernández Cáceres
            https://github.com/BlasFerna/py-ruc-calc
        """
        # Convierte el argumento en string
        # luego invierte los valores
        ruc_str = str(ruc)[::-1]

        # variable total que almacena el resultado
        v_total = 0

        basemax = 11

        # el factor de chequeo actual,
        # inicializa en 2
        k = 2

        for i in range(0, len(ruc_str)):
            if k > basemax:
                k = 2
            # multiplicación de cada valor por el factor de chequeo actual(k)
            v_total += int(ruc_str[i]) * k
            # se incrementa el valor de la variable k
            k += 1

        # resto de la división entre el resultado y el valor de la
        # variable basemax
        resto = v_total % basemax

        if resto > 1:
            # si el resto es mayor que uno, entonces el valor de basemax
            # es restado por el resultado de la operación anterior
            return basemax - resto
        else:
            return 0

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        if not args:
            args = []
        if name:
            domain = ['|', '|', ('phone', operator, name),
                      ('mobile', operator, name), ('vat', operator, name)
                      ]
            partners = self.search(domain + args, limit=limit, )
            res = partners.name_get()
            if limit:
                limit_rest = limit - len(partners)
            else:
                limit_rest = limit
            if limit_rest or not limit:
                args += [('id', 'not in', partners.ids)]
                res += super().name_search(
                    name, args=args, operator=operator, limit=limit_rest)
            return res
        return super().name_search(
            name, args=args, operator=operator, limit=limit
        )