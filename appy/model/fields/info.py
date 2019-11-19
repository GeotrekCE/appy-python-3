# ~license~
# ------------------------------------------------------------------------------
from appy.ui.layout import Layouts
from appy.model.fields import Field

# ------------------------------------------------------------------------------
class Info(Field):
    '''An info is a field whose purpose is to present information
       (text, html...) to the user.'''

    class Layouts(Layouts):
        '''Info-specific layouts'''
        b = Layouts(edit='l')
        d = Layouts(edit='l-d')
        c = Layouts(edit='l|')
        dc = Layouts(edit='l|-d|')
        vdc = Layouts(edit='l', view='l|-d|')

        @classmethod
        def getDefault(class_, field):
            '''Default layouts for this Info p_field'''
            return class_.b

    # An info only displays a label. So PX for showing content are empty.
    view = edit = cell = search = ''

    def __init__(self, validator=None, multiplicity=(1,1), show='view',
      page='main', group=None, layouts=None, move=0, readPermission='read',
      writePermission='write', width=None, height=None, maxChars=None,
      colspan=1, master=None, masterValue=None, focus=False, historized=False,
      mapping=None, generateLabel=None, label=None, view=None, edit=None,
      cell=None, xml=None, translations=None):
        Field.__init__(self, None, (0,1), None, None, show, page, group,
          layouts, move, False, True, None, False, readPermission,
          writePermission, width, height, None, colspan, master, masterValue,
          focus, historized, mapping, generateLabel, label, None, None, None,
          None, False, False, view, cell, edit, xml, translations)
        self.validable = False
# ------------------------------------------------------------------------------
