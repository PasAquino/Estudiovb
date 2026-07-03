# For copyright and license notices, see __manifest__.py file in module root

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from num2words import num2words


class AccountJournal(models.Model):
    _inherit = "account.move"

    py_timbrado_prov = fields.Char(
        string='Timbrado',
        help='Numero de timbrado'
    )
    py_timbrado_prov_end = fields.Date(
        string='Validez Timbrado',
        help='Fecha de caducidad del timbrado del proveedor'
    )
    remision = fields.Char(
        string='Nro de remito'
    )
    timbrado_id = fields.Many2one(
        'account.journal.stamped',
        help="Numero de timbrado que habilita la factura",
        string='Timbrado'
    )
    move_name = fields.Char(
        string="Cambiar número",
        readonly=False,
        default=False,
        copy=False,
        help="""Forzar número de factura. Utilice este campo si
         no desea utilizar la numeración predeterminada. """,
    )

    def _add_doc(self):
        # ob=self.env['account.tip.doc']
        # doc_obj = ob.search([('tipdoc','=','GAS')])
        doc_obj = self.env['account.tip.doc'].search(
            [('tipdoc', '=', 'purchase')])
        if doc_obj:
            tipodic = [('id', 'in', doc_obj.ids)]
            # ob.browse(doc_obj)
            # [('id', 'in', doc_obj.id)]
        else:
            tipodic = [('id', '=', -1)]
        return tipodic

    tipdocgas = fields.Many2one("account.tip.doc", string="Tipo Documento",
                                domain=_add_doc)

    def _add_doc_ing(self):
        # ob=self.env['account.tip.doc']
        # doc_obj = ob.search([('tipdoc','=','GAS')])
        doc_obj = self.env['account.tip.doc'].search(
            [('tipdoc', '=', 'sale')])
        if doc_obj:
            tipodic = [('id', 'in', doc_obj.ids)]
            # ob.browse(doc_obj)
            # [('id', 'in', doc_obj.id)]
        else:
            tipodic = [('id', '=', -1)]
        return tipodic

    tipdocing = fields.Many2one("account.tip.doc", string="Tipo Documento",
                                domain=_add_doc_ing)

    def action_post(self):
        """ Este metodo se dispara con el boton Publicar
            Solo para facturas o notas de credito al cliente, Obtener el
            proximo numero de documento de la secuencia.
            Luego llamar al metodo original para que publique
        """
        if self.move_type in ['out_invoice', 'out_refund']:

            # verificar que posee RUC
            if not self.partner_id.vat:
                raise ValidationError(_('El RUC es requerido, en este caso no '
                                        'puede quedar en blanco'))

            # verificar el tipo de cliente
            # partner_type = self.partner_id.partner_type_id
            # if partner_type.applied_to != 'sale':
            #    raise ValidationError('El tipo de cliente "%s" no esta '
            #                          'habilitado para ventas' % self.name)

            # verificar si tengo cuenta por defecto y aplicarla
            # if partner_type.default_account:
            #    for line in self.invoice_line_ids:
            #        if not partner_type.default_account.reconcile:
            #            raise ValidationError(
            #                'Se quiere aplicar la cuenta %s a esta '
            #                'operacion.\nEsto no es posible porque la cuenta '
            #                'no es reconciliable.'
            #                '' % partner_type.default_account.display_name)
            #        line.account_id = partner_type.default_account

            # obtener las secuencias definidas en el diario
            if self.state == 'draft':
                if not self.move_name:
                    if (not self.name or self.name == '/'):
                        sequence_ids = self.journal_id.py_sequence_ids

                        # filtrar la secuencia por el tipo de documento
                        if self.move_type == 'out_invoice':
                            type_id = 1
                        if self.move_type == 'out_refund':
                            type_id = 4

                        seq = sequence_ids.filtered(
                            lambda x: x.py_latam_journal_id.id == self.journal_id.id)
                        # seq = sequence_ids
                        proximo = seq.number_next_actual

                        domain = [('type', '=', type_id),
                                ('establishment_code', '=', self.journal_id.establishment_code),
                                ('shipping_point', '=', self.journal_id.shipping_point),
                                ('state', '=', 'active'),
                                ('company_id', '=', self.company_id.id)]

                        timbrados = self.env['account.journal.stamped'].search(
                            domain)

                        self.timbrado_id = timbrados.id

                        # chequear numero a validar es mayor que el maximo
                        if proximo > timbrados.number_max:
                            raise ValidationError(
                                _('El timbrado ya no es valido, el numero de documento '
                                'que quiere validar esta mas alla del rango.\n'
                                'El proximo numero de factura es %s mientras que el '
                                'rango de validez del timbrado es [%s - %s]') %
                                (proximo, timbrados.number_ini,
                                timbrados.number_max))

                        # chequear numero a validar es menor que el minimo
                        if proximo < timbrados.number_ini:
                            raise ValidationError(
                                _('El timbrado no es valido. Intenta validar un numero de '
                                'documento que es menor al minimo valido para este '
                                'timbrado.\n'
                                'El proximo numero de factura es %s mientras que el '
                                'rango de validez del timbrado es [%s - %s]') %
                                (proximo, timbrados.number_ini,
                                timbrados.number_max))

                        # numero a validar es igual al maximo, invalidar timbrado
                        if proximo == timbrados.number_max:
                            self.timbrado_id.state = 'no_active'

                        self.timbrado_id.number_used = proximo
                        self.timbrado_id.current_number = proximo + 1
                        # poner el numero de documento
                        if not self.name or self.name == '/':
                            next_number = seq.next_by_id()
                            self.name = next_number

                        # llamar al metodo original
                        return super().action_post()
                    else:
                        return super().action_post()
                else:
                    self.name = self.move_name
                    # llamar al metodo original
                    return super().action_post()
        if self.state == 'draft':
            if self.move_type in ['entry']:
                if self.move_name:
                    self.name = self.move_name
                    # llamar al metodo original
                    return super().action_post()
                else:
                    return super().action_post()
        if self.state == 'draft':
            if self.move_type in ['in_invoice', 'in_refund']:
                if self.tipdocgas.req_timbrado:
                    if not self.ref:
                        raise ValidationError(
                            _('La referencia es requerida, en este caso no '
                              'puede quedar en blanco'))
                    if not self.py_timbrado_prov:
                        raise ValidationError(
                            _('El Timbrado es requerido, en este caso no '
                              'puede quedar en blanco'))
                    if not self.py_timbrado_prov_end:
                        raise ValidationError(_(
                            'La fecha del Timbrado es requerido, en este caso no '
                            'puede quedar en blanco'))
                    # chequear la longitud y tipo de timbrado

                    if len(self.py_timbrado_prov) != 8:
                        raise ValidationError(
                            _('La longitud del timbrado debe ser de '
                              'ocho digitos'))
                    try:
                        int(self.py_timbrado_prov)
                    except ValueError:
                        raise ValidationError(_('El timbrado debe ser numerico'))

                    failed = False
                    args = self.ref.split('-')
                    if len(args) != 3:
                        failed = True
                    else:
                        suc, exp, number = args
                        if len(suc) > 3 or len(suc) < 3:
                            failed = True
                        elif not suc.isdigit():
                            failed = True
                        elif len(exp) > 3 or len(exp) < 3:
                            failed = True
                        elif not number.isdigit():
                            failed = True
                        elif len(number) > 7 or len(number) < 7:
                            failed = True
                        elif not number.isdigit():
                            failed = True

                        mask = '{:>03s}-{:>03s}-{:>07s}'
                        document_number = mask.format(suc, exp, number)
                    if failed:
                        raise ValidationError(_(
                            'El numero de documento debe ser ingresado separando con el '
                            'signo menos (-) cada parte, debe tener un maximo de 3 '
                            'digitos para Codigo de Establecimiento y Punto de Expedicion '
                            'y un maximo de 7 digitos para el numero de documento. '
                            'Los siguientes son ejemplos de numeros validos:\n'
                            '* 001-001-0000001\n'
                            '* 003-001-0000087\n'
                            '* 025-045-0000885'))
                    if not (self.py_timbrado_prov_end >= self.invoice_date):
                        raise ValidationError(
                            _('La fecha de la factura no esta dentro del rango de '
                              'validez del timbrado.'))

                    # llamar al metodo original
                    return super().action_post()
                elif not self.tipdocgas.req_timbrado:
                    # llamar al metodo original
                    return super().action_post()
            return super().action_post()

