import phonenumbers
import re
from odoo.exceptions import ValidationError
from odoo import _




def is_phone_number(number):
    try:
        _number = phonenumbers.parse(number)
        return phonenumbers.is_valid_number(_number)
    except:
        return False
    

def format_phone_number(number):
    if number.startswith('00'):
        number = '+' + number[2:]
    elif bool(re.match(r"^[1-9][0-9]+", number)):
        number = '+' + number
    return number


def get_valid_number(_number):
    number = format_phone_number(_number)
    return number if is_phone_number(number) else False


def validate_number(_number):
    number = get_valid_number(_number)
    if not number:
        raise ValidationError(_('Enter valid phone number'))
    return number