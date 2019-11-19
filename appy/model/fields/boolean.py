# ~license~
# ------------------------------------------------------------------------------
from appy.px import Px
from appy.model.fields import Field
from appy.ui.layout import Layouts, Layout

# ------------------------------------------------------------------------------
class Boolean(Field):
    '''Field for storing boolean values'''
    yesNo = {'true': 'yes', 'false': 'no', True: 'yes', False: 'no'}
    trueFalse = {True: 'true', False: 'false'}

    class Layouts(Layouts):
        '''Boolean-specific layouts'''
        # Default layout (render = "checkbox") ("b" stands for "base"), followed
        # by the "grid" variant (if the field is in a group with "grid" style).
        b = Layouts(edit=Layout('f;lrv;-', width=None), view='lf', search='l-f')
        g = Layouts(edit=Layout('frvl', width=None), view='fl', search='l-f')
        d = Layouts(edit=Layout('flrv;=d', width=None), view='lf')
        # *d*escription also visible on "view"
        dv = Layouts(edit=d['edit'], view='lf-d')
        h = Layouts(edit=Layout('flhv', width=None), view='lf')
        gd = Layouts(edit=Layout('f;dv-', width=None), view='fl')
        # The "long" version of the previous layout (if the description is
        # long), with vertical alignment on top instead of middle.
        gdl = Layouts(edit=Layout('f;dv=', width=None), view='fl')
        # Centered layout, no description
        c = Layouts(edit='flrv|', view='lf|')
        # Layout for radio buttons (render = "radios")
        r = Layouts(edit='f', view='f', search='l-f')
        rl = Layouts(edit='l-f', view='lf', search='l-f')
        grl = Layouts(edit='fl', view='fl', search='l-f')

        @classmethod
        def getDefault(class_, field):
            '''Default layouts for this Boolean p_field'''
            if field.render == 'radios': return class_.r
            return class_.g if field.inGrid() else class_.b

    view = cell = Px('''
    <x>::field.getInlineEditableValue(o, value, layout)</x>
    <input type="hidden" if="masterCss"
           class=":masterCss" value=":rawValue" name=":name" id=":name"/>''')

    edit = Px('''<x var="isTrue=field.isTrue(o, name, rawValue);
                         visibleName=name + '_visible'">
     <x if="field.render == 'checkbox'">
      <input type="checkbox" name=":visibleName" id=":name"
             class=":masterCss" checked=":isTrue"
             onclick=":field.getOnChange(o, layout)"/>
     </x>
     <x if="field.render == 'radios'"
        var2="falseId='%s_false' % name;
              trueId='%s_true' % name">
      <input type="radio" name=":visibleName" id=":falseId" class=":masterCss"
             value="False" checked=":not isTrue"
             onclick=":field.getOnChange(o, layout)"/>
      <label lfor=":falseId">:_(field.labelId + '_false')</label><br/>
      <input type="radio" name=":visibleName" id=":trueId" class=":masterCss"
             value="True" checked=":isTrue"
             onclick=":field.getOnChange(o, layout)"/>
      <label lfor=":trueId">:_(field.labelId + '_true')</label>
     </x>
     <input type="hidden" name=":name" id=":'%s_hidden' % name"
            value=":isTrue and 'True' or 'False'"/>
     <script if="hostLayout">:'prepareForAjaxSave(%s,%s,%s,%s)' % \
      (q(name), q(o.id), q(o.url), q(hostLayout))</script></x>''',

     js='''
      updateHiddenBool = function(elem) {
        // Determine the value of the boolean field
        var value = elem.checked,
            hiddenName = elem.name.replace('_visible', '_hidden');
        if ((elem.type == 'radio') && elem.id.endsWith('_false')) value= !value;
        value = (value)? 'True': 'False';
        // Set this value in the hidden field
        document.getElementById(hiddenName).value = value;
      }''')

    search = Px('''
      <x var="valueId='%s_yes' % name">
       <input type="radio" value="True" name=":widgetName" id=":valueId"/>
       <label lfor=":valueId">:_(field.getValueLabel(True))</label>
      </x>
      <x var="valueId='%s_no' % name">
       <input type="radio" value="False" name=":widgetName" id=":valueId"/>
       <label lfor=":valueId">:_(field.getValueLabel(False))</label>
      </x>
      <x var="valueId='%s_whatever' % name">
       <input type="radio" value="" name=":widgetName" id=":valueId"
              checked="checked"/>
       <label lfor=":valueId">:_('whatever')</label>
      </x><br/>''')

    def __init__(self, validator=None, multiplicity=(0,1), default=None,
      defaultOnEdit=None, show=True, page='main', group=None, layouts = None,
      move=0, indexed=False, mustIndex=True, indexValue=None, searchable=False,
      readPermission='read', writePermission='write', width=None, height=None,
      maxChars=None, colspan=1, master=None, masterValue=None, focus=False,
      historized=False, mapping=None, generateLabel=None, label=None,
      sdefault=False, scolspan=1, swidth=None, sheight=None, persist=True,
      render='checkbox', inlineEdit=False, view=None, cell=None, edit=None,
      xml=None, translations=None):
        # By default, a boolean is edited via a checkbox. It can also be edited
        # via 2 radio buttons (p_render="radios").
        self.render = render
        Field.__init__(self, validator, multiplicity, default, defaultOnEdit,
          show, page, group, layouts, move, indexed, mustIndex, indexValue,
          searchable, readPermission, writePermission, width, height, None,
          colspan, master, masterValue, focus, historized, mapping,
          generateLabel, label, sdefault, scolspan, swidth, sheight, persist,
          inlineEdit, view, cell, edit, xml, translations)
        self.pythonType = bool

    def getValue(self, obj, name=None, layout=None):
        '''Never returns "None". Returns always "True" or "False", even if
           "None" is stored in the DB.'''
        value = Field.getValue(self, obj, name, layout)
        if value is None: return False
        return value

    def getValueLabel(self, value):
        '''Returns the label for p_value (True or False): if self.render is
           "checkbox", the label is simply the translated version of "yes" or
           "no"; if self.render is "radios", there are specific labels.'''
        if self.render == 'radios':
            return '%s_%s' % (self.labelId, self.trueFalse[value])
        return self.yesNo[value]

    def getFormattedValue(self, o, value, layout='view', showChanges=False,
                          language=None):
        return o.translate(self.getValueLabel(value), language=language)

    def getMasterTag(self, layout):
        '''The tag driving slaves is the hidden field'''
        return (layout == 'edit') and ('%s_hidden' % self.name) or self.name

    def getOnChange(self, o, layout, className=None):
        '''Updates the hidden field storing the actual UI value for the field'''
        r = 'updateHiddenBool(this)'
        # Call the base behaviour
        base = Field.getOnChange(self, o, layout, className=className)
        return '%s; %s' % (r, base) if base else r

    def getStorableValue(self, o, value, complete=False):
        if not self.isEmptyValue(o, value):
            exec('r = %s' % value)
            return r

    def getSearchValue(self, form):
        '''Converts the raw search value from p_form into a boolean value'''
        r = Field.getSearchValue(self, form)
        exec('r = %s' % r)
        return r

    def isSortable(self, usage):
        '''Can this field be sortable ?'''
        if usage == 'search': return Field.isSortable(self, usage)
        return True # Sortable in Ref fields

    def isTrue(self, o, name, dbValue):
        '''When rendering this field as a checkbox, must it be checked or
           not?'''
        req = o.req
        # Get the value we must compare (from request or from database)
        if name in req:
            return req[name] in ('True', 1, '1')
        return dbValue
# ------------------------------------------------------------------------------
