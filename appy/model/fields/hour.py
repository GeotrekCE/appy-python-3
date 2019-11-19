# ~license~
# ------------------------------------------------------------------------------
import time

from appy.px import Px
from appy.model.fields import Field

# ------------------------------------------------------------------------------
class Hour(Field):
    '''Field allowing to define an hour independently of a complete date'''

    view = cell = Px('''<x>:value</x>''')

    edit = Px('''
     <x var="hPart=hPart | '%s_hour' % name;
             mPart=mPart | '%s_minute' % name;
             hours=range(0,24)">
      <select name=":hPart" id=":hPart">
       <option value="">-</option>
       <option for="hour in hours"
         var2="zHour=str(hour).zfill(2)" value=":zHour"
         selected=":field.isSelected(o, hPart, 'hour', \
                                     hour, rawValue)">:zHour</option>
      </select> : 
      <select var="minutes=range(0, 60, field.minutesPrecision)"
              name=":mPart" id=":mPart">
       <option value="">-</option>
       <option for="min in minutes"
         var2="zMin=str(min).zfill(2)" value=":zMin"
         selected=":field.isSelected(o, mPart, 'minute', \
                                     min, rawValue)">:zMin</option>
      </select>
     </x>''')

    hourParts = ('hour', 'minute')

    def __init__(self, validator=None, multiplicity=(0,1), default=None,
      defaultOnEdit=None, hourFormat=None, minutesPrecision=5, show=True,
      page='main', group=None, layouts=None, move=0, indexed=False,
      mustIndex=True, indexValue=None, searchable=False, readPermission='read',
      writePermission='write', width=None, height=None, maxChars=None,
      colspan=1, master=None, masterValue=None, focus=False, historized=False,
      mapping=None, generateLabel=None, label=None, sdefault=None, scolspan=1,
      swidth=None, sheight=None, persist=True, view=None, cell=None, edit=None,
      xml=None, translations=None):
        # If no p_hourFormat is specified, the application-wide tool.hourFormat
        # is used instead.
        self.hourFormat = hourFormat
        # If "minutesPrecision" is 5, only a multiple of 5 can be encoded. If
        # you want to let users choose any number from 0 to 59, set it to 1.
        self.minutesPrecision = minutesPrecision
        Field.__init__(self, validator, multiplicity, default, defaultOnEdit,
          show, page, group, layouts, move, indexed, mustIndex, indexValue,
          searchable, readPermission, writePermission, width, height, None,
          colspan, master, masterValue, focus, historized, mapping,
          generateLabel, label, sdefault, scolspan, swidth, sheight, persist,
          False, view, cell, edit, xml, translations)

    def getFormattedValue(self, o, value, layout='view', showChanges=False,
                          language=None):
        if self.isEmptyValue(o, value): return ''
        format = self.hourFormat or o.config.ui.hourFormat
        hour, minute = [str(part).zfill(2) for part in value]
        return format.replace('%H', hour).replace('%M', minute)

    def getRequestValue(self, o, requestName=None):
        req = o.req
        name = requestName or self.name
        r = []
        empty = True
        for partName in self.hourParts:
            part = req['%s_%s' % (name, partName)] or ''
            if part: empty = False
            r.append(part)
        return None if empty else ':'.join(r)

    def getRequestSuffix(self): return '_hour'

    def getStorableValue(self, o, value, complete=False):
        if not self.isEmptyValue(o, value):
            return tuple(map(int, value.split(':')))

    def validateValue(self, o, value):
        '''Ensure p_value is complete: all parts must be there (minutes and
           seconds).'''
        if value.startswith(':') or value.endswith(':'):
            # A part is missing
            return o.translate('field_required')

    def isSelected(self, o, part, fieldPart, hourValue, dbValue):
        '''When displaying this field, must the particular p_hourValue be
           selected in the sub-field p_fieldPart corresponding to the hour
           p_part ?'''
        # Get the value we must compare (from request or from database)
        req = o.req
        if part in req:
            compValue = req[part]
            if compValue.isdigit():
                compValue = int(compValue)
        else:
            compValue = dbValue
            if compValue:
                i = 1 if fieldPart == 'minute' else 0
                compValue = dbValue[i]
        # Compare the value
        return compValue == hourValue

    # --------------------------------------------------------------------------
    # Class methods
    # --------------------------------------------------------------------------

    @classmethod
    def hourDifference(class_, h1, h2):
        '''Computes the number of hours between h1 and h2'''
        if h2 < h1:
            # h2 is the day after
            h2 += 24
        return h2 - h1

    @classmethod
    def getDuration(class_, start, end):
        '''Returns the duration, in minutes, of the interval [start, end]'''
        # Manage minutes
        minutes = end[1] - start[1]
        if minutes < 0:
            minutes += 60
            endHour = 23 if end[0] == 0 else end[0] - 1
        else:
            deltaHour = 0
            endHour = end[0]
        return ((class_.hourDifference(start[0], endHour))*60) + minutes

    @classmethod
    def formatDuration(class_, minutes, sep='h'):
        '''Returns a formatted version of this number of p_minutes'''
        modulo = minutes % 60
        hours = int(minutes / 60.0)
        r = '%d%s' % (hours, sep)
        if modulo:
            r += str(modulo).zfill(2)
        return r
# ------------------------------------------------------------------------------
