'''This module is about disposing graphical elements in the user interface'''

# ------------------------------------------------------------------------------
from appy.px import Px

# ------------------------------------------------------------------------------
# A "layout" defines how to dispose, in the user interface, parts of some
# logical element. This element, named a "layouted object", can be a field or a
# page. 

# ------------------------------------------------------------------------------
class Cell:
    '''Represents a cell in a row within a layout (see appy.ui.layout.Layout)'''

    def __init__(self, content, align, isHeader=False):
        self.align = align
        self.width = None
        self.content = None
        self.colspan = 1
        if isHeader:
            self.width = content
        else:
            self.content = [] # The list of widgets to render in the cell
            self.decodeContent(content)

    def __repr__(self):
        return '<Cell %s>' % self.content

    def decodeContent(self, content):
        digits = '' # We collect the digits that will give the colspan
        for char in content:
            if char.isdigit():
                digits += char
            else: # It is a letter corresponding to a macro
                self.content.append(Layout.pxs.get(char, char))
        # Manage the colspan
        if digits:
            self.colspan = int(digits)

    def renderContent(self, value, layout, layoutTarget):
        '''Renders p_value (one element among self.content) for a given
           p_layoutTarget (a field or object) on some p_layout.'''
        # The name of the PX is the layout or p_value
        name = layout if value == 'f' else value
        r = layoutTarget
        if isinstance(name, tuple):
            for part in name:
                r = getattr(r, part)
        else:
            r = getattr(r, name)
        return r

# ------------------------------------------------------------------------------
class Row:
    '''Represents a a row within a layout (see appy.ui.layout.Layout)'''

    def __init__(self, content, valign, isHeader=False):
        self.valign = valign
        self.cells = []
        self.decodeCells(content, isHeader)
        # Compute the row length
        length = 0
        for cell in self.cells:
            length += cell.colspan
        self.length = length

    def __repr__(self):
        return '<Row %s (%d)>' % (str(self.cells), self.length)

    def decodeCells(self, content, isHeader):
        '''Decodes the given chunk of layout string p_content containing
           column-related information (if p_isHeader is True) or cell content
           (if p_isHeader is False) and produces a list of Cell instances.'''
        cellContent = ''
        for char in content:
            if char in Layout.cellDelimiters:
                align = Layout.cellDelimiters[char]
                self.cells.append(Cell(cellContent, align, isHeader))
                cellContent = ''
            else:
                cellContent += char
        # Manage the last cell if any
        if cellContent:
            self.cells.append(Cell(cellContent, 'left', isHeader))

# ------------------------------------------------------------------------------
class Layout:
    '''Represents a logical table defining how to dispose graphical parts of
       some UI element.'''

    # --------------------------------------------------------------------------
    # Defining parts of a layouted object and how they will be rendered is done
    # via a "layout string". Such a string is made of:
    # - letters, corresponding to object parts;
    # - symbols, allowing to define column or row breaks, alignment, etc.

    # Letters for a page -------------------------------------------------------
    #  e - The object h*e*ader, containing its title, breadcrumb, siblings
    #      navigation, phases and pages.
    #  s - An object's hi*s*tory
    #  w - The fields (= *w*idgets) to render on some page for some object
    #  b - The range of *b*uttons (intra-object navigation, save, edit,
    #      delete...)

    # Letters for a field ------------------------------------------------------
    #  l - "label"        The field label
    #  d - "description"  The field description
    #  h - "help"         Help for the field (typically rendered as an icon,
    #                     with a tooltip displaying online help
    #  v - "validation"   The icon that is shown when a validation error occurs
    #                     (typically only used on "edit" layouts)
    #  r - "required"     The icon that is specified that the field is required
    #                     (if relevant; typically only used on "edit" layouts)
    #  f - "field"        The field value, or input for entering a value.
    #  c - "changes"      The button for displaying changes to a field

    # This dict defines the PXs to use to render every part as defined by the
    # hereabove letters.
    pxs = {
      # Page-related elements
      'e': 'pxHeader', 's': ('history', 'view'), 'w': 'pxFields',
      'b': 'pxButtons',
      # Field-related elements
      'l': 'pxLabel', 'd': 'pxDescription', 'h': 'pxHelp', 'v': 'pxValidation',
      'r': 'pxRequired', 'c': 'pxChanges'
    }

    # Symbols to use within a layout string ------------------------------------
    # A row delimiter is to be used at the end of a row. The symbol used defines
    # alignment for the previously defined row.
    rowDelimiters =  {'-':'middle', '=':'top', '_':'bottom'}
    rowDelms = ''.join(rowDelimiters.keys())
    # A cell delimiter is to be used at the end of a cell. The symbol used
    # defines alignment for the previouly defined cell.
    cellDelimiters = {'|': 'center', ';': 'left', '!': 'right'}
    cellDelms = ''.join(cellDelimiters.keys())

    # Base layout attributes
    baseAttributes = ('style', 'css_class', 'cellpadding', 'cellspacing',
                      'width', 'align')

    # A layout can be derived from another one. The following dict defines the
    # letters to remove to define a simpler layout (view, search) from a more
    # complex layout (edit).
    derivedRepls = {'view': 'hrvd', 'search': 'hrvd'}

    # PX rendering this layout instance, known in the context as "table".
    # Indeed, the variable named "layout" is already used to represent the
    # current layout *type*. If the layouted object is a page, the "layout
    # target" (where to look for sub-PXs) will be the object whose page is
    # shown; if the layouted object is a field, the layout target will be this
    # field.

    # Warning: when the layout type is "cell", the cell width and alignment must
    # not be defined by the cell layout, but by the outer column layout.

    pxRender = Px('''
     <table var="layoutCss=table.css_class;
                 inTd=(layout == 'cell') and bool(column)|False"
       cellpadding=":table.cellpadding"
       cellspacing=":table.cellspacing"
       width=":not inTd and table.width or ''"
       align=":not inTd and ui.Language.flip(table.align, dir) or ''"
       class=":tagCss and ('%s %s' % (tagCss, layoutCss)).strip() or layoutCss"
       style=":table.style" id=":tagId" name=":tagName">
      <!-- The table header row -->
      <tr if="table.headerRow" valign=":table.headerRow.valign">
       <th for="cell in table.headerRow.cells" width=":cell.width"
           align=":ui.Language.flip(cell.align, dir)">
       </th>
      </tr>
      <!-- The table content -->
      <tr for="row in table.rows" valign=":row.valign">
       <td for="cell in row.cells" colspan=":cell.colspan"
           align=":ui.Language.flip(cell.align, dir)"
           class=":not loop.cell.last and 'cellGap' or ''">
        <x for="c in cell.content">
         <x>::cell.renderContent(c, layout, layoutTarget)</x>
         <img if="not loop.c.last" src=":url('space.gif')"/>
        </x>
       </td>
      </tr>
     </table>''')

    def __init__(self, layoutString=None, style=None, css_class='',
                 cellpadding=0, cellspacing=0, width='100%', align='left',
                 other=None, derivedType=None):
        if other:
            # We need to create a Table instance from another Table instance,
            # given in p_other. In this case, we ignore previous params.
            if derivedType is not None:
                # We will not simply mimic p_other. If p_derivedType is:
                # - "view", p_other is an "edit" layout, and we must create the
                #           corresponding "view" layout;
                # - "search", p_derivedFrom is a "view" layout.
                self.layoutString = Layout.derive(other.layoutString,
                                                  derivedType)
            else:
                self.layoutString = other.layoutString
            source = 'other.'
        else:
            source = ''
            self.layoutString = layoutString
        # Initialise simple params, either from the true params, either from
        # the p_other Table instance.
        for param in Layout.baseAttributes:
            setattr(self, param, '%s%s' % (source, param))
        # The following attribute will store a special Row instance used for
        # defining column properties.
        self.headerRow = None
        # The content rows will be stored hereafter.
        self.rows = []
        self.decodeRows(self.layoutString)

    @staticmethod
    def derive(layout, derivedType):
        '''Returns a layout derived from p_layout'''
        res = layout
        for letter in Layout.derivedRepls[derivedType]:
            res = res.replace(letter, '')
        # Strip the derived layout
        res = res.lstrip(Layout.rowDelms); res = res.lstrip(Layout.cellDelms)
        return res

    def addCssClasses(self, css_class):
        '''Adds a single or a group of p_css_class.'''
        if not self.css_class: self.css_class = css_class
        else:
            self.css_class += ' ' + css_class
            # Ensures that every class appears once
            self.css_class = ' '.join(set(self.css_class.split()))

    def isHeaderRow(self, rowContent):
        '''Determines if p_rowContent specified the table header row or a
           content row.'''
        # Find the first char that is a number or a letter
        for char in rowContent:
            if char not in Layout.cellDelimiters:
                return char.isdigit()
        return True

    def decodeRows(self, layoutString):
        '''Decodes the given p_layoutString and produces a list of Row
           instances.'''
        # Split the p_layoutString with the row delimiters
        rowContent = ''
        for char in layoutString:
            if char in Layout.rowDelimiters:
                valign = Layout.rowDelimiters[char]
                if self.isHeaderRow(rowContent):
                    if not self.headerRow:
                        self.headerRow = Row(rowContent, valign, isHeader=True)
                else:
                    self.rows.append(Row(rowContent, valign))
                rowContent = ''
            else:
                rowContent += char
        # Manage the last row if any
        if rowContent:
            self.rows.append(Row(rowContent, 'middle'))

    def removeElement(self, elem):
        '''Removes given p_elem from myself'''
        toRemove = Layout.pxs[elem]
        for row in self.rows:
            for cell in row.cells:
                if toRemove in cell.content:
                    cell.content.remove(toRemove)
        if elem in self.layoutString:
            self.layoutString = self.layoutString.replace(elem, '')

    def setRequired(self, required):
        '''Adds or remove the p_required part'''
        if not required:
            self.removeElement('r')
        else:
            # Add it. Do not update editLayout.layoutString, too tricky.
            content = self.rows[0].cells[0].content
            content.insert(1, Layout.pxs['r'])

    def __repr__(self): return '<Layout %s>' % self.layoutString

# ------------------------------------------------------------------------------
class ColumnLayout:
    '''A "column layout" dictates the way a table column must be rendered. Such
       a layout is of the form: <name>[*width][,|!|`|`][^].'''

    # --------------------------------------------------------------------------
    #   <name>  | is the name of the field whose content must be shown in
    #           | column's cells ;
    # --------------------------------------------------------------------------
    #   width   | is the width of the column. Any valid value for the "width"
    #           | attribute of the "td" HTML tag is accepted ;
    # --------------------------------------------------------------------------
    #   , | !   | column alignment: respectively, left, centered or right ;
    # --------------------------------------------------------------------------
    #     ^     | if present, indicates that the column header must be empty.
    # --------------------------------------------------------------------------

    def __init__(self, layoutString):
        self.layoutString = layoutString

    def get(self):
        '''Returns a list containing the separate elements that are within
           self.layoutString.'''
        consumed = self.layoutString
        lastChar = consumed[-1]
        # Must the column header be empty ?
        if lastChar == '^':
            header = False
            consumed = consumed[:-1]
        else:
            header = True
        # Determine column alignment
        lastChar = consumed[-1]
        if lastChar in Layout.cellDelimiters:
            align = Layout.cellDelimiters[lastChar]
            consumed = consumed[:-1]
        else:
            align = 'left'
        # Determine name and width
        if '*' in consumed:
            name, width = consumed.rsplit('*', 1)
        else:
            name = consumed
            width = ''
        return name, width, align, header

# ------------------------------------------------------------------------------
class Layouts(dict):
    '''Define layouts for some field'''

    # When a layouted object must be displayed, depending on the place in the
    # UI where it must appear, a specific layout will be used. This is the
    # concept of "layout type". Appy currently defines the following layout
    # types.
    types = (
      'view',    # a read-only page for an object;
      'edit',    # the editable page for an object;
      'result',  # a cell within a list of objects;
      'query',   # the top-level zone on the page displaying results of some
                 # search, typically used for rendering Pod fields allowing
                 # to export documents including these results;
      'buttons', # the series of buttons rendered on a view/edit page or
                 # besides the object title on a list of objects;
      'xml',     # similar to 'view', but in XML format, readable by a peer
                 # system, the 'view' layout being in XHTML format, readable
                 # by a human being;
      'sidebar'  # The zone in the UI situated, for left-to-right languages,
                 # at the right of the screen.
    )

    # Note that a layout will not be defined for every layout type. For example,
    # layout "xml" renders pure data, so layouting as no sense in that case.
    # Some layouts only define an alternate "place" to render an object, but
    # will use the same rendering as for layout "view". This is the case for
    # layouts "sidebar" and "query" for example.

    # Base type are those for which a Layout instance will be stored in a
    # Layouts instance.
    baseTypes = ('edit', 'view', 'search')

    # Some layouts must be explicitly specified in order to be taken into
    # account, while, for most of them, this is implicit. For example, when
    # determining visibility of a field, boolean "True" implicitly denotes any
    # layout type, excepted those listed in the following attribute.
    explicitTypes = ('buttons', 'sidebar')

    def __init__(self, edit=None, view=None, search=None):
        '''Initialise layouts based on the specified attributes'''
        # Initalise dict keys based on constructor attributes
        if edit: edit = self['edit'] = self.getLayoutFrom(edit)
        if view: view = self['view'] = self.getLayoutFrom(view)
        if search: search = self['search'] = self.getLayoutFrom(search)
        # Derive unspecified layouts from the existing ones, when possible
        if edit and not view:
            view = self['view'] = Layout(other=edit, derivedType='view')
        if view and not search:
            self['search'] = Layout(other=view, derivedType='search')

    def getLayoutFrom(self, this):
        '''Gets a Layout instance from p_this'''
        # If p_this is already a Table instance, it is simply returned. If it is
        # a layout string, a Table instance is created from it.
        return this if isinstance(this, Layout) else Layout(this)

    def isComplete(self):
        '''Returns True if p_self contains an entry for each base layout type'''
        for base in Layouts.baseTypes:
            if base not in self:
                return

    def completeFrom(self, other):
        '''Complete p_self by cloning the missing elements from p_other'''
        # p_other is supposed to be complete
        for base in Layouts.baseTypes:
            if base not in self:
                self[base] = Layout(other=other)

    def clone(self):
        '''Create a clone from p_self'''
        r = Layouts()
        r.completeFrom(self)
        return r

    def hasPart(self, part):
        '''Return True if the given layout p_part can be found at least once
           among the various p_layouts defined on p_self.'''
        for layout in self.values():
            if part in layout.layoutString: return True

    # ~~~ Default cell layout ~~~
    # Layouts for a field do not contain any entry for layout type "cell".
    # Indeed, rendering a field on such layout is, implicitly, simply rendering
    # its value ("f"). Moreover, rendering a layout renders a complete XHTML
    # table, even if it contains a single cell, like for "f". So we avoid doing
    # this for performance and conciseness reasons. But we can't complelety
    # forget cell layouts, because they are needed for inline-editing (or maybe
    # other Ajax-like functionalities in the future). Indeed, the machinery for
    # ajax-editing the field is inlaid in the XHTML table corresponding to the
    # layout. In such case, we will use a standard cell layout defined here.
    cell = Layout('f|', align='center', css_class='no')

    # --------------------------------------------------------------------------
    # Class methods
    # --------------------------------------------------------------------------

    @classmethod
    def getDefault(class_, field):
        '''Returns the default layouts for this p_field'''
        # ~~~
        # The default layout depends on:
        # - the fact that a field is required or not;
        # - the type of group into which the field is.
        # ~~~
        # This method may be overridden by child Layouts classes as possibly
        # defined on every sub-field class.
        # ~~~
        key = 'grid' if field.inGrid() else 'normal'
        return class_.defaults[key][field.required]

    @classmethod
    def getFor(class_, field, layouts):
        '''Gets a Layouts instance for this p_field, based on the value given in
           its "layouts" attribute.'''
        # Get default layouts if p_layouts is empty
        if not layouts:
            r = field.Layouts.getDefault(field)
            defaults = True
        elif isinstance(layouts, str) or isinstance(layouts, Layout):
            # This is a single layout string or instance, the "edit" one
            r = Layouts(layouts)
            defaults = False
        else:
            # p_layouts is already a Layouts instance. Complete it if necessary.
            r = layouts
            if not r.isComplete():
                r.completeFrom(field.Layouts.getDefault(field))
            defaults = False
        # Clone the layout and add special CSS classes in it when appropriate
        if field.focus:
            r = r.clone()
            r['view'].addCssClasses('focus')
            r['edit'].addCssClasses('focus')
        return r

# Default field layouts --------------------------------------------------------
# The following layout instances, stored as static attributes on class Layouts,
# are default layouts applying to fields. You can define them as values for
# attributes "layouts" when defining fields on your classes.
# 
# These layouts are generic and apply to most fields. However, every field
# sub-class may define specific layouts. Here are some examples.
# - If you need to use generic layout named "d" as defined hereafter, while
#   defining your field, use
#                             layouts=Layouts.b
# - Class Boolean defines a specific "d" layout that is more appropriate. If you
#   want to use it, write:
#                         layouts=Boolean.Layouts.b
# Note that, because classes <SubField>.Layouts inherits from class Layouts,
# also available as Field.Layouts, if you don't know if there is a specific
# version of some layout on the sub-class, you can systematically use the layout
# as defined on <SubClass>.Layouts. But the notation is longer, so, if you
# prefer a shorter syntax, Layouts.<letter> is available, too.

# If you do not specify any layout at all in the "layouts" attribute for some
# field, default layouts will be applied: either those being defined in the
# following dict, either those as defined in method
#                          <subField>.Layout.getDefaults
# if defined.

# Fields being in groups having style "grid", and required fields, too,
# deserve specific layouts. This why there are 4 different default layouts,
# depending on these 2 combined factors.
Layouts.defaults = {
  'normal': {True: Layouts('lrv-f'), False: Layouts('lv-f')},
  'grid':   {True: Layouts(edit='frvl', search='l-f'),
             False: Layouts(edit='fvl', search='l-f')}
}

# The following naming conventions apply.
# "b"  base layout
# "d"  description (for layouts displaying the field's description)
# "h"  help (for layouts displaying the field's help icon)
# "n"  narrow (for non-100%-wide layouts)
# "w"  wide
# "g"  group (for layouts applicable to fields in groups with style="grid")
# "c"  centered
b = 'lrv-f'
d = 'lrv-d-f'
Layouts.b = Layouts(Layout(b, width=None))
Layouts.d = Layouts(d)
Layouts.h = Layouts('lhrv-f')
Layouts.n = Layouts.b
Layouts.w = Layouts(Layout(b))
# Layouts with content only (no label)
Layouts.f = Layouts(Layout('f', width=None))
Layouts.wf = Layouts(Layout('f'))
Layouts.g = Layouts(edit='frvl', search='l-f')
# The *d*escription is visible, even on the *v*iew layout
Layouts.dv = Layouts(edit=d, view='l-d-f')
# "Grid" group-related layouts
Layouts.gn = Layouts(edit=Layout('f;rvl=', width=None), search='l-f')
Layouts.gd = Layouts(Layout('frvl-d', width='99%'))
Layouts.gdn = Layouts(Layout('d2-f;rvl=', width=None))
Layouts.gh = Layouts('fhrvl')
Layouts.gdh = Layouts('fhrvl-d')

# Default layouts for pages are defined hereafter. In order to define layouts on
# a Appy class, place an instance of class Layouts (a custom one, or one of the
# layouts as defined hereafter) in static attribute "layouts" on your class.

class PageLayouts:
    # The default layouts
    defaults = Layouts(edit=Layout('w-b', width=None), view=Layout('e-w-b'))
    # With the page summary
    summary = Layouts(edit=Layout('w-b', width=None), view=Layout('e-s-w-b'))
    # Wide
    wide = Layouts(edit=Layout('w-b'), view=Layout('e-w-b'))
    # Wide + summary
    wideSummary = Layouts(edit=Layout('w-b'), view=Layout('s-w-b'))
    # Centered
    centered = Layouts(edit=Layout('w|-b|', width=None, align='center'),
                       view=Layout('e-w|-b|', align='center'))
Layouts.Page = PageLayouts
# ------------------------------------------------------------------------------
