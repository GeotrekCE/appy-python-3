# ~license~
# ------------------------------------------------------------------------------
import copy
from appy.px import Px
from appy.model.fields import Field
from appy.model.utils import Object as O
from appy.ui.layout import Layout, Layouts

# ------------------------------------------------------------------------------
class Total:
    '''Represents a computation that will be executed on a series of cells
       within a List field.'''
    def __init__(self, name, field, initValue):
        self.name = name # The sub-field name
        self.field = field # field.name is prefixed with the main field name
        self.value = initValue

    def __repr__(self):
        return '<Total %s=%s>' % (self.name, str(self.value))

class Totals:
    '''If you want to add rows representing totals computed from regular List
       rows, specify it via Totals instances (see List attribute "totalRows"
       below).'''
    def __init__(self, id, label, subFields, onCell, initValue=0.0):
        # "id" must hold a short name or acronym and must be unique within all
        # Totals instances defined for a given List field.
        self.id = id
        # "label" is a i18n label that will be used to produce a longer name
        # that will be shown at the start of the total row.
        self.label = label
        # "subFields" is a list or tuple of sub-field names for which totals
        # must be computed.
        self.subFields = subFields
        # "onCell" stores a method that will be called every time a cell
        # corresponding to a field listed in self.subFields is walked in the
        # list. It will get these args:
        # * row      the current row as an Object instance;
        # * total    the Total instance (see above) corresponding to the current
        #            column;
        # * last     a boolean that is True if we are walking the last row.
        self.onCell = onCell
        # "initValue" is the initial value given to created Total instances
        self.initValue = initValue

# ------------------------------------------------------------------------------
class List(Field):
    '''A list, stored as a list of Object instances ~[Object]~. Every object in
       the list has attributes named according to the sub-fields defined in this
       List.'''
    Totals = Totals

    # List is an "outer" field, made of inner fields
    outer = True

    class List:
        '''List-specific layouts'''
        g = Layouts(edit=Layout('f;rv=', width=None), view='fl')
        gd = Layouts(edit=Layout('dv=f;', width=None), view='fl')

        @classmethod
        def getDefault(class_, field):
            '''Default layouts for this List p_field'''
            return class_.g if field.inGrid() else super().getDefault(field)

    # A 1st invisible cell containing a virtual field allowing to detect this
    # row at server level.
    pxFirstCell = Px('''<td style="display: none">
     <table var="rid='%s*-row-*%s' % (field.name, rowId)"
            id=":'%s_%s' % (o.id, rid)">
      <tr><td><input type="hidden" id=":rid" name=":rid"/></td></tr>
     </table></td>''')

    # PX for rendering a single row
    pxRow = Px('''
     <tr valign="top" style=":(rowId == -1) and 'display: none' or ''"
         class=":loop.row.odd and 'odd' or 'even'">
      <x if="not isCell">:field.pxFirstCell</x>
      <td if="showTotals"></td>
      <td for="info in subFields" if="info[1]"
          var2="x=field.updateTotals(totals, o, info, row, loop.row.last);
                field=info[1];
                minimal=isCell;
                fieldName='%s*%d' % (field.name, rowId)">:field.pxRender</td>
      <!-- Icons -->
      <td if="isEdit" align=":dright">
       <img class="clickable" src=":url('delete')" title=":_('object_delete')"
            onclick=":field.jsDeleteConfirm(q, tableId)"/>
       <img class="clickable" src=":url('arrowUp')" title=":_('move_up')"
            onclick=":'moveRow(%s,%s,this)' % (q('up'), q(tableId))"/>
       <img class="clickable" src=":url('arrowDown')" title=":_('move_down')"
            onclick=":'moveRow(%s,%s,this)' % (q('down'), q(tableId))"/>
       <input class="clickable" type="image" tabindex="0"
              src=":url('addBelow')" title=":_('object_add_below')"
              onclick=":'insertRow(%s,this); return false' % q(tableId)"/>
      </td></tr>''')

    # Display totals (on view only) when defined
    pxTotals = Px('''
     <tr for="totalRow in field.totalRows" var2="total=totals[totalRow.id]">
      <th>:_(totalRow.label)</th>
      <th for="info in subFields">:field.getTotal(total, info)</th>
     </tr>''')

    # PX for rendering the list (shared between pxView, pxEdit and pxCell)
    pxTable = Px('''
     <table var="isEdit=layout == 'edit';
                 isCell=layout == 'cell';
                 tableId='list_%s' % name" if="isEdit or value"
            id=":tableId" width=":field.width" class="grid"
            var2="subFields=field.getSubFields(o, layout);
                  totals=field.createTotals(isEdit);
                  showTotals=not isEdit and totals">
      <!-- Header -->
      <thead>
       <tr valign="middle">
        <th if="showTotals"></th>
        <th for="name, sub in subFields" if="sub"
            width=":field.widths[loop.name.nb]">
         <x var="field=sub">::field.getListHeader(_ctx_)</x></th>
        <!-- Icon for adding a new row -->
        <th if="isEdit">
         <img class="clickable" src=":url('plus')" title=":_('object_add')"
              onclick=":'insertRow(%s)' % q(tableId)"/>
        </th>
       </tr>
      </thead>

      <!-- Template row (edit only) -->
      <x var="rowId=-1" if="isEdit">:field.pxRow</x>

      <!-- Rows of data -->
      <x var="rows=field.getInputValue(inRequest, requestValue, value)"
         for="row in rows" var2="rowId=loop.row.nb">:field.pxRow</x>

      <!-- Totals -->
      <x if="showTotals">:field.pxTotals</x>
     </table>''')

    view = cell = Px('''<x>:field.pxTable</x>''')
    edit = Px('''<x>
     <!-- This input makes Appy aware that this field is in the request -->
     <input type="hidden" name=":name" value=""/><x>:field.pxTable</x>
    </x>''')

    search = ''

    def __init__(self, fields, validator=None, multiplicity=(0,1), default=None,
      defaultOnEdit=None, show=True, page='main', group=None, layouts=None,
      move=0, readPermission='read', writePermission='write', width='',
      height=None, maxChars=None, colspan=1, master=None, masterValue=None,
      focus=False, historized=False, mapping=None, generateLabel=None,
      label=None, subLayouts=Layout('f;r;v', width=None), widths=None,
      view=None, cell=None, edit=None, xml=None, translations=None,
      deleteConfirm=False, totalRows=None):
        Field.__init__(self, validator, multiplicity, default, defaultOnEdit,
         show, page, group, layouts, move, False, True, None, False,
         readPermission, writePermission, width, height, None, colspan, master,
         masterValue, focus, historized, mapping, generateLabel, label, None,
         None, None, None, True, False, view, cell, edit, xml, translations)
        self.validable = True
        # Tuples of (names, Field instances) determining the format of every
        # element in the list.
        self.fields = fields
        # Force some layouting for sub-fields, if subLayouts are given. So the
        # one who wants freedom on tuning layouts at the field level must
        # specify subLayouts=None.
        if subLayouts:
            for name, field in self.fields:
                field.layouts = field.formatLayouts(subLayouts)
        # One may specify the width of every column in the list. Indeed, using
        # widths and layouts of sub-fields may not be sufficient.
        self.computeWidths(widths)
        # When deleting a row, must we display a popup for confirming it ?
        self.deleteConfirm = deleteConfirm
        # If you want to specify additional rows representing totals, give in
        # "totalRows" a list of Totals instances (see above).
        self.totalRows = totalRows or []

    def init(self, class_, name):
        '''List-specific lazy initialisation'''
        Field.init(self, class_, name)
        for sub, field in self.fields:
            fullName = '%s_%s' % (name, sub)
            field.init(class_, fullName)
            field.name = '%s*%s' % (name, sub)

    def computeWidths(self, widths):
        '''Set given p_widths or compute default ones if not given'''
        if not widths:
            self.widths = [''] * len(self.fields)
        else:
            self.widths = widths

    def getField(self, name):
        '''Gets the field definition whose name is p_name'''
        for n, field in self.fields:
            if n == name: return field

    def getSubFields(self, o, layout):
        '''Returns the sub-fields (name, Field) that are showable among
           field.fields on the given p_layout. Fields that cannot appear in
           the result are nevertheless present as a tuple (name, None). This
           way, it keeps a nice layouting of the table.'''
        r = []
        for n, field in self.fields:
            elem = (n, None)
            if field.isShowable(o, layout):
                elem = (n, field)
            r.append(elem)
        return r

    def getRequestValue(self, o, requestName=None):
        '''Concatenates the list from distinct form elements in the request'''
        req = o.req
        name = requestName or self.name # A List may be into another List (?)
        prefix = name + '*-row-*' # Allows to detect a row of data for this List
        r = {}
        isDict = True # We manage both List and Dict
        for key in req.keys():
            if not key.startswith(prefix): continue
            # I have found a row: get its index
            row = O()
            rowId = key.split('*')[-1]
            if rowId == '-1': continue # Ignore the template row
            for subName, subField in self.fields:
                keyName = '%s*%s*%s' % (name, subName, rowId)
                if keyName + subField.getRequestSuffix() in req:
                    v = subField.getRequestValue(o, requestName=keyName)
                    setattr(row, subName, v)
            if rowId.isdigit():
                rowId = int(rowId)
                isDict = False
            r[rowId] = row
        # Produce a sorted list (List only)
        if not isDict:
            keys = list(r.keys())
            keys.sort()
            r = [r[key] for key in keys]
        # I store in the request this computed value. This way, when individual
        # subFields will need to get their value, they will take it from here,
        # instead of taking it from the specific request key. Indeed, specific
        # request keys contain row indexes that may be wrong after row deletions
        # by the user.
        if r: req[name] = r
        return r

    def setRequestValue(self, obj):
        '''Sets in the request, the field value on p_obj in its
           "request-carriable" form.'''
        value = self.getValue(obj)
        if value != None:
            req = obj.REQUEST
            name = self.name
            i = 0
            for row in value:
                req['%s*-row-*%d' % (name, i)] = ''
                for n, v in row.__dict__.items():
                    key = '%s*%s*%d' % (name, n, i)
                    req[key] = v
                i += 1

    def getStorableRowValue(self, obj, requestValue):
        '''Gets a ready-to-store Object instance representing a single row,
           from p_requestValue.'''
        res = O()
        for name, field in self.fields:
            if not hasattr(requestValue, name) and \
               not field.isShowable(obj, 'edit'):
                # Some fields, although present on "edit", may not be part of
                # the p_requestValue (ie, a "select multiple" with no value at
                # all will not be part of the POST HTTP request). If we want to
                # know if the field was in the request or not, we must then
                # check if it is showable on layout "edit".
                continue
            subValue = getattr(requestValue, name, None)
            try:
                setattr(res, name, field.getStorableValue(obj, subValue))
            except ValueError:
                # The value for this field for this specific row is incorrect.
                # It can happen in the process of validating the whole List
                # field (a call to m_getStorableValue occurs at this time). We
                # don't care about it, because later on we will have sub-field
                # specific validation that will also detect the error and will
                # prevent storing the wrong value in the database.
                setattr(res, name, subValue)
        return res

    def getStorableValue(self, obj, value, complete=False):
        '''Gets p_value in a form that can be stored in the database'''
        return [self.getStorableRowValue(obj, v) for v in value]

    def getCopyValue(self, obj):
        '''Return a (deep) copy of field value on p_obj''' 
        r = getattr(obj.aq_base, self.name, None)
        if r: return copy.deepcopy(r)

    def getCss(self, layout, r):
        '''Gets the CSS required by sub-fields if any'''
        for name, field in self.fields:
            field.getCss(layout, r)

    def getJs(self, layout, r, config):
        '''Gets the JS required by sub-fields if any'''
        for name, field in self.fields:
            field.getJs(layout, r, config)

    def jsDeleteConfirm(self, q, tableId):
        '''Gets the JS code to call when the user wants to delete a row'''
        confirm = self.deleteConfirm and 'true' or 'false'
        return 'deleteRow(%s,this,%s)' % (q(tableId), confirm)

    def subValidate(self, o, value, errors):
        '''Validates inner fields'''
        i = -1
        for row in value:
            i += 1
            for name, subField in self.fields:
                message = subField.validate(o, getattr(row, name, None))
                if message:
                    setattr(errors, '%s*%d' % (subField.name, i), message)

    def createTotals(self, isEdit):
        '''When rendering the List field, if total rows are defined, create a
           Total instance for every sub-field for which a total must be
           computed.'''
        if isEdit or not self.totalRows: return
        res = {} # Keyed by Totals.name
        for totals in self.totalRows:
            subTotals = O()
            for name in totals.subFields:
                totalObj = Total(name, self.getField(name), totals.initValue)
                setattr(subTotals, name, totalObj)
            res[totals.id] = subTotals
        return res

    def updateTotals(self, totals, obj, info, row, last):
        '''Every time a cell is encountered while rendering the List, this
           method is called to update totals when needed'''
        if not totals: return
        # Browse Totals instances
        for totalRow in self.totalRows:
            # Are there totals to update ?
            total = getattr(totals[totalRow.id], info[0], None)
            if total:
                totalRow.onCell(obj, row, total, last)

    def getTotal(self, totals, info):
        '''Get the total for the field p_info if available'''
        total = getattr(totals, info[0], None)
        if total: return total.value
        return ''
# ------------------------------------------------------------------------------
