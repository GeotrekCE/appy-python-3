# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy.ui import Language
from appy.ui.layout import ColumnLayout
from appy.model.utils import Object as O

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class ColSet:
    '''Represents a named set of columns to show when displaying Search results
       or tied objects from a Ref.'''
    FIELD_NOT_FOUND = 'field "%s", used in a column specifier, not found.'

    # Standard column specifiers
    standardColSpecs = O(
      number =     O(special=True, field='_number', width='15px',
                     align='left', header=False),
      checkboxes = O(special=True, field='_checkboxes', width='10px',
                     align='center', header=True)
    )

    @staticmethod
    def getColSpecs(class_, columnLayouts, dir,
                    addNumber=False, addCheckboxes=False):
        '''Extracts and returns, from a list of p_columnLayouts, info required
           for displaying columns of field values for instances of p_class_,
           either in a result screen or for a Ref field.
        '''
        # p_columnLayouts are specified for each field whose values must be
        # shown. 2 more, not-field-related, column layouts can be specified with
        # these names:
        # ----------------------------------------------------------------------
        # "_number"     | if the listed objects must be numbered by Appy, this
        #               | string represents the column containing that number;
        # ----------------------------------------------------------------------
        # "_checkboxes" | if Appy must show checkboxes for the listed objects,
        #               | this string represents the column containing the
        #               | checkboxes.
        # ----------------------------------------------------------------------
        # If columns "_number" and "_checkboxes" are not among p_columnLayouts
        # but are required (by p_addNumber and p_addCheckboxes), they are added
        # to the result. Specifying them within p_columnLayouts allows to give
        # them a precise position among all columns. When automatically added,
        # they will appear before any other column (which is desirable in most
        # cases).
        r = []
        numberFound = checkboxesFound = False
        for info in columnLayouts:
            name, width, align, header = ColumnLayout(info).get()
            # It that a special column name ?
            special = True
            if name == '_number': numberFound = True
            elif name == '_checkboxes': checkboxesFound = True
            else: special = False
            align = Language.flip(align, dir)
            # For non-special columns, get the corresponding field
            if not special:
                field = class_.fields.get(name)
                if not field:
                    self.log(ColSet.FIELD_NOT_FOUND % name, type='warning')
                    continue
            else:
                # Let the column name in attribute "field"
                field = name
            r.append(O(special=special, field=field, width=width,
                       align=align, header=header))
        # Add special columns if required and not present
        if addCheckboxes and not checkboxesFound:
            r.insert(0, ColSet.standardColSpecs.checkboxes)
        if addNumber and not numberFound:
            r.insert(0, ColSet.standardColSpecs.number)
        return r

    def __init__(self, identifier, label, columns, specs=False):
        # A short identifier for the set
        self.identifier = identifier
        # The i18n label to use for giving a human-readable name to the set
        self.label = label
        # The list/tuple of columns, expressed as strings. Every string must
        # contain a field name, but can be completed (after a char *) by column
        # width and alignment, as in "state*100px|". The "width" part, just
        # after the *, can hold anything that can be set in a "width" HTML
        # attribute. The last char represents the alignment:
        #   ";"   left-aligned (the default);
        #   "|"   centered;
        #   "!"   right-aligned.
        if not specs:
            self.columns = columns
        else:
            # "specs" is the internal representation of "columns". Do not
            # specify "specs=True". It will contain a list of Object instances
            # instead of strings. Every such instance has splitted string info
            # into fields "field", "width" and "align".
            self.specs = columns
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
