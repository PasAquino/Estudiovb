# -*- coding: utf-8 -*-
from odoo import fields, models, exceptions, api
from datetime import datetime, timedelta
from lxml import etree
from num2words import num2words


class AccountTextPayment(models.Model):
    _inherit = "account.move"

    def generar_texto(self, numero, moneda):
        if moneda == 2:
            new_number = round(numero, 2)
            nuevo_numero = str(new_number).split('.')
            entero = num2words(int(nuevo_numero[0]), lang='es').capitalize()
            if len(nuevo_numero[1]) == 1:
                if nuevo_numero[1] == '0':
                    decimal = num2words(int(nuevo_numero[1]), lang='es').capitalize()
                else:
                    decimal = num2words(int(nuevo_numero[1] + '0'), lang='es').capitalize()
            else:
                decimal = num2words(int(nuevo_numero[1]), lang='es').capitalize()
            letras = entero + ' con ' + decimal + ' Centavos'
        else:
            letras = num2words(numero, lang='es').capitalize()
        letras_return = letras
        return letras_return

    def agregar_punto_de_miles(self, numero, moneda):
        if moneda == 3:
            entero = int(numero)
            decimal = '{0:.2f}'.format(numero - entero)
            entero_string = '.'.join([str(int(entero))[::-1][i:i + 3] for i in range(0, len(str(int(entero))), 3)])[
                            ::-1]
            if decimal == '0.00':
                numero_con_punto = entero_string
            else:
                decimal_string = str(decimal).split('.')
                numero_con_punto = entero_string + ',' + decimal_string[1]
        else:
            numero_con_punto = '.'.join(
                [str(int(numero))[::-1][i:i + 3] for i in range(0, len(str(int(numero))), 3)])[::-1]
        num_return = numero_con_punto + '#'
        return num_return
