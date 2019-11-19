# ~license~
#  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import random, hashlib, binascii

from appy.px import Px
from appy.model.fields import Field

#  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class PasswordGenerator:
    '''Class used to generate passwords'''

    # No "0" or "1" that could be interpreted as letters "O" or "l"
    passwordDigits = '23456789'

    # No letters i, l, o (nor lowercase nor uppercase) that could be misread
    passwordLetters = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ'

    @classmethod
    def get(k, minLength=8, maxLength=9):
        '''Generates and r_eturns a password whose length is between p_minLength
           and p_maxLength.'''
        # Compute the actual length of the challenge to encode
        length = random.randint(minLength, maxLength)
        r = ''
        for i in range(length):
            j = random.randint(0, 1)
            chars = (j == 0) and k.passwordDigits or k.passwordLetters
            # Choose a char
            r += chars[random.randint(0,len(chars)-1)]
        return r

#  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Password(Field):
    '''Field allowing to edit and store a password'''

    view = cell = Px('''<x>******</x>''')
    edit = Px('''
     <x for="confirm in (False, True)"
        var2="placeholder=field.getPlaceholder(o, confirm);
              inputId=confirm and ('%s_confirm' % name) or name">
      <input type="password" id=":inputId" name=":inputId"
             style=":'width: %s' % field.width"
             maxlength=":field.maxChars" placeholder=":placeholder"/>
      <br if="not confirm"/>
     </x>''')

    def __init__(self, validator=None, multiplicity=(0,1), show=True,
      page='main', group=None, layouts=None, move=0, readPermission='read',
      writePermission='write', width='15em', height=None, maxChars=None,
      colspan=1, master=None, masterValue=None, focus=False, historized=False,
      mapping=None, generateLabel=None, label=None, sdefault='', scolspan=1,
      swidth=None, sheight=None, persist=True, placeholder=None, view=None,
      cell=None, edit=None, xml=None, translations=None, minLength=8):
        # The minimum length for this password
        self.minLength = minLength
        # Call the base constructor
        Field.__init__(self, validator, multiplicity, None, None, show, page,
          group, layouts, move, False, True, None, False, readPermission,
          writePermission, width, height, maxChars, colspan, master,
          masterValue, focus, historized, mapping, generateLabel, label,
          sdefault, scolspan, swidth, sheight, persist, False, view, cell, edit,
          xml, translations)
        # A potential placeholder (see homonym attribute in string.py)
        self.placeholder = placeholder

    def getPlaceholder(self, o, confirm):
        '''Returns a placeholder for the field if defined'''
        if confirm:
            # Set a specific label as placeholder for the input field allowing
            # to confirm the password.
            r = o.translate('password_confirm')
        else:
            # Define the placeholder for the base field
            r = self.getAttribute(o, 'placeholder') or ''
            # Use the field label if a placeholder must be set but no label is
            # explicitly defined.
            r = o.translate(self.labelId) if r is True else r
        return r

    def validateValue(self, o, password):
        '''Is p_password valid ?'''
        # Password must have a minimum length
        if len(password) < self.minLength:
            return o.translate('password_too_short', mapping={'nb': 8})
        # Ensure the "confirm" value is filled and is the same as p_password
        if o.req['%s_confirm' % self.name] != password:
            return o.translate('passwords_mismatch')

    def encrypt(self, password, prefix=True, salt=None):
        '''Encrypt clear p_password with the SSHA scheme. If p_prefix is True,
           the password is prefixed with the SSHA scheme ("${SSHA}"). If p_salt
           is not given, it will be computed.'''
        if salt is None:
            # Generate a salt made of 7 chars
            salt = ''
            for n in range(7):
                salt += chr(random.randrange(256))
            salt = salt.encode()
        # Use SHA-1 algorithm to encrypt the password
        r = hashlib.sha1(password.encode() + salt).digest() + salt
        # Base64-encode the result
        r = binascii.b2a_base64(r)[:-1]
        # Prefix the result with the SSHA prefix when appropriate
        if prefix:
            r = b'{SSHA}' + r
        return r

    def check(self, o, password):
        '''Return True if the clear p_password corresponds the password as
           encrypted for this field on p_o.'''
        # Get the encrypted password
        encrypted = o.values.get(self.name)
        if not encrypted: return
        # Remove the scheme prefix
        encrypted = encrypted[6:]
        # Base64-decode it
        try:
            base = binascii.a2b_base64(encrypted)
        except binascii.Error:
            # Not valid base64
            return
        # Encrypt p_password and compare it with the encrypted password
        return self.encrypt(password, prefix=False, salt=base[20:]) == encrypted

    def generate(self, maxLength=9):
        '''Generate a password of at most m_maxLength chars'''
        return PasswordGenerator.get(self.minLength, maxLength)

    def set(self, o, password=None, log=True, maxLength=9):
        '''Sets a p_password on p_o for this password field. If p_password is
           not given, a password will be generated, made of at most p_maxLength
           chars. This method returns the generated password (or simply
           p_password if no generation occurred).'''
        if newPassword is None:
            # Generate one
            password = self.generate(maxLength)
            msgPart = 'generated'
        else:
            msgPart = 'changed'
        self.store(o, password)
        # Log the operation when requested
        if log: self.log('password %s for %s.' % (msgPart, login))
        return password

    def store(self, o, value):
        '''Encrypts the clear password given in p_value'''
        if self.persist: o.values[self.name] = self.encrypt(value)
#  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
