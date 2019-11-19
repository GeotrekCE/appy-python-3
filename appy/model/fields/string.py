# -*- coding: utf-8 -*-
# ~license~

# ------------------------------------------------------------------------------
import re, random, sys

from appy import utils
from appy.px import Px
from appy.data import Countries
from appy.model.fields import Field
from appy.utils import string as sutils
from appy.ui.layout import Layouts, Layout
from appy.model.fields.multilingual import Multilingual

# ------------------------------------------------------------------------------
digit  = re.compile('[0-9]')
alpha  = re.compile('[a-zA-Z0-9]')
letter = re.compile('[a-zA-Z]')
digits = '0123456789'
letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

# ------------------------------------------------------------------------------
class String(Multilingual, Field):
    '''Represents a one-line string'''

    class Layouts(Layouts):
        '''String-specific layouts'''
        g = Layouts(edit=Layout('f;rv=', width=None), search='l-f')
        gd = Layouts(edit=Layout('f;rv=d', width=None), search='l-f')

    # Use this constant to say that there is no maximum size for a string field
    NO_MAX = sys.maxsize

    # Some predefined regular expressions that may be used as validators
    c = re.compile
    EMAIL = c('[a-zA-Z][\w\.-]*[a-zA-Z0-9]*@[a-zA-Z0-9][\w\.-]*[a-zA-Z0-9]\.' \
              '[a-zA-Z][a-zA-Z\.]*[a-zA-Z]')
    ALPHANUMERIC = c('[\w-]+')
    URL = c('(http|https):\/\/[a-z0-9]+([\-\.]{1}[a-z0-9]+)*(\.[a-z]{2,5})?' \
            '(([0-9]{1,5})?\/.*)?')

    # Default ways to render multilingual fields
    defaultLanguagesLayouts = {'edit': 'vertical', 'view': 'vertical'}

    # Python string methods to use to apply a transform
    transformMethods = {'uppercase': 'upper', 'lowercase': 'lower',
                        'capitalize': 'capitalize'}

    viewUni = cellUni = Px('''
     <span if="not value" class="smaller">-</span>
     <x if="value" var="isUrl=field.isUrl">
      <x if="isUrl" var2="value=field.getValueIf(o, name, layout)">
       <img src=":url('url')"/>
       <a target="_blank" href=":value" title=":value">:value</a>
      </x>
      <x if="not isUrl">::value</x>
     </x>
     <input type="hidden" if="masterCss and not multilingual"
            class=":masterCss" value=":rawValue" name=":name" id=":name"/>''')

    editUni = Px('''
     <input type="text"
       var="inputId='%s_%s' % (name, lg) if lg else name;
            placeholder=field.getPlaceholder(o)"
       id=":inputId" name=":inputId" size=":field.getLineWidth()"
       maxlength=":field.maxChars" placeholder=":placeholder"
       value=":field.getInputValue(inRequest, requestValue, value)"
       style=":'text-transform:%s;%s' % \
               (field.transform, field.getLineWidth(False))"
       readonly=":field.isReadonly(o)"/>''')

    search = Px('''
     <input type="text" maxlength=":field.maxChars" size=":field.swidth"
            value=":field.sdefault" name=":widgetName"
            style=":'text-transform:%s' % field.transform"/><br/>''')

    # Some predefined functions that may also be used as validators
    @staticmethod
    def _MODULO_97(o, value, complement=False):
        '''p_value must be a string representing a number, like a bank account.
           this function checks that the 2 last digits are the result of
           computing the modulo 97 of the previous digits. Any non-digit
           character is ignored. If p_complement is True, it does compute the
           complement of modulo 97 instead of modulo 97. p_obj is not used;
           it will be given by the Appy validation machinery, so it must be
           specified as parameter. The function returns True if the check is
           successful.'''
        if not value: return True
        # First, remove any non-digit char
        v = ''
        for c in value:
            if digit.match(c): v += c
        # There must be at least 3 digits for performing the check
        if len(v) < 3: return False
        # Separate the real number from the check digits
        number = int(v[:-2])
        checkNumber = int(v[-2:])
        # Perform the check
        if complement:
            return (97 - (number % 97)) == checkNumber
        else:
            # The check number can't be 0. In this case, we force it to be 97.
            # This is the way Belgian bank account numbers work. I hope this
            # behaviour is general enough to be implemented here.
            mod97 = (number % 97)
            if mod97 == 0: return checkNumber == 97
            else:          return checkNumber == mod97

    @staticmethod
    def MODULO_97(o, value): return String._MODULO_97(o, value)

    @staticmethod
    def MODULO_97_COMPLEMENT(o, value): return String._MODULO_97(o, value, True)
    BELGIAN_ENTERPRISE_NUMBER = MODULO_97_COMPLEMENT

    @staticmethod
    def BELGIAN_NISS(o, value):
        '''Returns True if the NISS in p_value is valid'''
        if not value: return True
        # Remove any non-digit from nrn
        niss = sutils.keepDigits(value)
        # NISS must be made of 11 numbers
        if len(niss) != 11: return False
        # When NRN begins with 0 or 1, it must be prefixed with number "2" for
        # checking the modulo 97 complement.
        nissForModulo = niss
        if niss.startswith('0') or niss.startswith('1'):
            nissForModulo = '2' + niss
        # Check modulo 97 complement
        return String.MODULO_97_COMPLEMENT(o, nissForModulo)

    @staticmethod
    def IBAN(o, value):
        '''Checks that p_value corresponds to a valid IBAN number. IBAN stands
           for International Bank Account Number (ISO 13616). If the number is
           valid, the method returns True.'''
        if not value: return True
        # First, remove any non-digit or non-letter char
        v = ''
        for c in value:
            if alpha.match(c): v += c
        # Maximum size is 34 chars
        if (len(v) < 8) or (len(v) > 34): return False
        # 2 first chars must be a valid country code
        if not Countries.get().exists(v[:2].upper()): return False
        # 2 next chars are a control code whose value must be between 0 and 96.
        try:
            code = int(v[2:4])
            if (code < 0) or (code > 96): return False
        except ValueError:
            return False
        # Perform the checksum
        vv = v[4:] + v[:4] # Put the 4 first chars at the end.
        nv = ''
        for c in vv:
            # Convert each letter into a number (A=10, B=11, etc)
            # Ascii code for a is 65, so A=10 if we perform "minus 55"
            if letter.match(c): nv += str(ord(c.upper()) - 55)
            else: nv += c
        return int(nv) % 97 == 1

    @staticmethod
    def BIC(o, value):
        '''Checks that p_value corresponds to a valid BIC number. BIC stands
           for Bank Identifier Code (ISO 9362). If the number is valid, the
           method returns True.'''
        if not value: return True
        # BIC number must be 8 or 11 chars
        if len(value) not in (8, 11): return False
        # 4 first chars, representing bank name, must be letters
        for c in value[:4]:
            if not letter.match(c): return False
        # 2 next chars must be a valid country code
        if not Countries.get().exists(value[4:6].upper()): return False
        # Last chars represent some location within a country (a city, a
        # province...). They can only be letters or figures.
        for c in value[6:]:
            if not alpha.match(c): return False
        return True

    def __init__(self, validator=None, multiplicity=(0,1), default=None,
      defaultOnEdit=None, show=True, page='main', group=None, layouts=None,
      move=0, indexed=False, mustIndex=True, indexValue=None, searchable=False,
      readPermission='read', writePermission='write', width=None, height=None,
      maxChars=None, colspan=1, master=None, masterValue=None, focus=False,
      historized=False, mapping=None, generateLabel=None, label=None,
      sdefault='', scolspan=1, swidth=None, sheight=None, persist=True,
      transform='none', placeholder=None, languages=('en',),
      languagesLayouts=None, inlineEdit=False, view=None, cell=None, edit=None,
      xml=None, translations=None, readonly=False):
        # Does this field store an URL ?
        self.isUrl = validator == String.URL
        # "placeholder", similar to the HTML attribute of the same name, allows
        # to specify a short hint describing the expected value of the input
        # field. It is shown inside the input field and disappears as soon as
        # the user encodes something in it. You can specify a method here, that
        # can, for example, return an internationalized value.
        self.placeholder = placeholder
        # "transform" below has a direct impact on the text entered by the user.
        # It applies a transformation on it, exactly as does the CSS
        # "text-transform" property. Allowed values are those allowed for the
        # CSS property: "none" (default), "uppercase", "capitalize" or
        # "lowercase".
        self.transform = transform
        # If attribute "readonly" is True (or stores a method returning True),
        # the rendered input field, on edit layouts, will have attribute
        # "readonly" set.
        self.readonly = readonly
        # Call the base constructors
        Multilingual.__init__(self, languages, languagesLayouts)
        Field.__init__(self, validator, multiplicity, default, defaultOnEdit,
          show, page, group, layouts, move, indexed, mustIndex, indexValue,
          searchable, readPermission, writePermission, width, height, maxChars,
          colspan, master, masterValue, focus, historized, mapping,
          generateLabel, label, sdefault, scolspan, swidth, sheight, persist,
          inlineEdit, view, cell, edit, xml, translations)
        # Default width, height and maxChars
        if width is None:
            self.width  = 30
        if height is None:
            self.height = 1
        if maxChars is None:
            self.maxChars = 256
        if self.indexed:
            self.filterPx = 'pxFilterText'
        self.swidth = self.swidth or self.width
        self.sheight = self.sheight or self.height

    def isRenderable(self, layout):
        '''A value being an URL is potentially renderable everywhere'''
        return self.isUrl or (layout != 'buttons')

    def isSortable(self, usage):
        '''Can this field be sortable ?'''
        if usage == 'search':
            r = self.indexed and not self.isMultiValued()
        else: # Usage is "ref"
            r = not self.isMultilingual(None, True)
        return r

    def getLineWidth(self, sizeAttr=True):
        '''Returns the width of the input field, either in the "size" attribute,
           (p_sizeAttr is True) or as a CSS "width" attribute (p_sizeAttr is
           False).'''
        # If the field width is expressed as a percentage, the width must be
        # specified via the CSS "width" attribute. In all other cases, it is
        # specified via the "size" tag attribute.
        width = self.width
        isPercentage = width and isinstance(width, str) and width.endswith('%')
        if sizeAttr:
            # tag attribute "size"
            return '' if isPercentage else width
        else:
            # CSS attribute "width"
            return 'width:%s' % width if isPercentage else ''

    def getUniFormattedValue(self, o, value, layout='view', showChanges=False,
                             language=None, contentLanguage=None):
        '''Returns the formatted variant of p_value. If p_contentLanguage is
           specified, p_value is the p_contentLanguage part of a multilingual
           value.'''
        return Field.getFormattedValue(self, o, value, layout, showChanges,
                                       language)

    def getUniIndexValue(self, o, value):
        '''Gets the value to index for this unilingual p_value'''
        return sutils.normalizeString(value, usage='extract') .lower() \
               if value else ''

    def getSearchValue(self, form):
        '''Potentially apply a transform to search value in p_form'''
        r = Field.getSearchValue(self, form)
        if r and self.transform:
            r = self.applyTransform(r)
        return r

    def getSortValue(self, o):
        '''Return the value of p_self on p_obj that must be used for sorting.
           While the raw p_value may be the value to use in most cases, it is
           not always true. For example, a string like "Gaëtan" could have
           "gaetan" as sort value.'''
        return sutils.normalizeText(self.getValue(o) or '',
                                    dash=False, space=False)

    def getPlaceholder(self, o):
        '''Returns a placeholder for the field if defined'''
        r = self.getAttribute(o, 'placeholder') or ''
        if r == True:
            # A placeholder must be set, but we have no value. In this case, we
            # take the field label.
            r = o.translate(self.labelId)
        return r

    def applyTransform(self, value):
        '''Applies a transform as required by self.transform on single
           value p_value.'''
        if self.transform in ('uppercase', 'lowercase'):
            # For those transforms, I will remove any accent, because, most of
            # the time, if the user wants to apply such effect, it is for ease
            # of data manipulation, so I guess without accent.
            value = sutils.normalizeString(value, usage='noAccents')
        # Apply the transform
        method = String.transformMethods.get(self.transform)
        if method:
            exec('value = value.%s()' % method)
        return value

    def getUniStorableValue(self, o, value):
        '''Manage a potential string transform and max chars'''
        isString = isinstance(value, str)
        isEmpty = Field.isEmptyValue(self, o, value)
        # Apply transform if required
        if isString and not isEmpty:
           value = self.applyTransform(value)
        # Manage maxChars
        max = self.maxChars
        if max and (len(value) > max): value = value[:max]
        return value
# ------------------------------------------------------------------------------
