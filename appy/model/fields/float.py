# ~license~
# ------------------------------------------------------------------------------
from appy import utils
from appy.model.fields.integer import Integer

# ------------------------------------------------------------------------------
class Float(Integer):
    # Allowed chars for being used as decimal separators
    allowedDecimalSeps = (',', '.')
    SEP_UNALLOWED = 'Char "%s" is not allowed as decimal separator.'

    def __init__(self, validator=None, multiplicity=(0,1), default=None,
      defaultOnEdit=None, show=True, page='main', group=None, layouts=None,
      move=0, indexed=False, mustIndex=True, indexValue=None, searchable=False,
      readPermission='read', writePermission='write', width=5, height=None,
      maxChars=13, colspan=1, master=None, masterValue=None, focus=False,
      historized=False, mapping=None, generateLabel=None, label=None,
      sdefault=('',''), scolspan=1, swidth=None, sheight=None, persist=True,
      precision=None, sep=(',', '.'), tsep=' ', inlineEdit=False, view=None,
      cell=None, edit=None, xml=None, translations=None, readonly=False):
        # The precision is the number of decimal digits. This number is used
        # for rendering the float, but the internal float representation is not
        # rounded.
        self.precision = precision
        # The decimal separator can be a tuple if several are allowed, ie
        # ('.', ',')
        if type(sep) not in utils.sequenceTypes:
            self.sep = (sep,)
        else:
            self.sep = sep
        # Check that the separator(s) are among allowed decimal separators
        for sep in self.sep:
            if sep not in Float.allowedDecimalSeps:
                raise Exception(Float.SEP_UNALLOWED % sep)
        self.tsep = tsep
        Integer.__init__(self, validator, multiplicity, default, defaultOnEdit,
          show, page, group, layouts, move, indexed, mustIndex, indexValue,
          searchable, readPermission, writePermission, width, height, maxChars,
          colspan, master, masterValue, focus, historized, mapping,
          generateLabel, label, sdefault, scolspan, swidth, sheight, persist,
          inlineEdit, view, cell, edit, xml, translations, readonly)
        self.pythonType = float

    def getFormattedValue(self, obj, value, layoutType='view',
                          showChanges=False, language=None):
        return utils.formatNumber(value, sep=self.sep[0],
                                  precision=self.precision, tsep=self.tsep)

    def replaceSeparators(self, value):
        '''Replaces, in p_value, separators "sep" and "tsep" in such a way that
           p_value may become a valid Python float literal.'''
        for sep in self.sep: value = value.replace(sep, '.')
        return value.replace(self.tsep, '')
# ------------------------------------------------------------------------------
