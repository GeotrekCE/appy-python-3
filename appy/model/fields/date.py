# ~license~
# ------------------------------------------------------------------------------
import time

from DateTime import DateTime

from appy.px import Px
from appy.utils import dates
from appy.model.fields import Field
from appy.model.fields.hour import Hour

# ------------------------------------------------------------------------------
def getDateFromIndexValue(indexValue):
    '''p_indexValue is the internal representation of a date as stored in the
       zope Date index (see "_convert" method in DateIndex.py in
       Products.pluginIndexes/DateIndex). This function produces a DateTime
       based on it.'''
    # p_indexValue represents a number of minutes
    minutes = indexValue % 60
    indexValue = (indexValue-minutes) / 60 # The remaining part, in hours
    # Get hours
    hours = indexValue % 24
    indexValue = (indexValue-hours) / 24 # The remaining part, in days
    # Get days
    day = indexValue % 31
    if day == 0: day = 31
    indexValue = (indexValue-day) / 31 # The remaining part, in months
    # Get months
    month = indexValue % 12
    if month == 0: month = 12
    year = (indexValue - month) / 12
    utcDate = DateTime('%d/%d/%d %d:%d UTC' % (year,month,day,hours,minutes))
    return utcDate.toZone(utcDate.localZone())

# ------------------------------------------------------------------------------
class Date(Field):

    view = cell = Px('''<x>:value</x>''')

    # PX for selecting hour and minutes, kindly provided by field Hour
    pxHour = Hour.edit

    edit = Px('''
     <x var="years=field.getSelectableYears()">
      <!-- Day -->
      <select if="field.showDay" var2="days=range(1,32); part='%s_day' % name"
              name=":part" id=":part">
       <option value="">-</option>
       <option for="day in days" var2="zDay=str(day).zfill(2)" value=":zDay"
         selected=":field.isSelected(o, part, 'day', \
                                     day, rawValue)">:zDay</option>
      </select> 

      <!-- Month -->
      <select var="months=range(1,13); part='%s_month' % name"
              name=":part" id=":part">
       <option value="">-</option>
       <option for="month in months"
         var2="zMonth=str(month).zfill(2)" value=":zMonth"
         selected=":field.isSelected(o, part, 'month', \
                                     month, rawValue)">:zMonth</option>
      </select> 

      <!-- Year -->
      <select var="part='%s_year' % name" name=":part" id=":part">
       <option value="">-</option>
       <option for="year in years" value=":year"
         selected=":field.isSelected(o, part, 'year', \
                                     year, rawValue)">:year</option>
      </select>

      <!-- The icon for displaying the calendar popup -->
      <x if="field.calendar">
       <input type="hidden" id=":name" name=":name"/>
       <img id=":'%s_img' % name" src=":url('calendar.gif')"/>
       <script>::field.getJsInit(name, years)</script>
      </x>

      <!-- Hour and minutes -->
      <x if="field.format == 0">:field.pxHour</x>
     </x>''')

    search = Px('''<table var="years=range(field.startYear, field.endYear+1)">
       <!-- From -->
       <tr var="fromName='%s_from' % name;
                dayFromName='%s_from_day' % name;
                monthFromName='%s_from_month' % name">
        <td width="10px">&nbsp;</td>
        <td><label>:_('search_from')</label></td>
        <td>
         <select id=":dayFromName" name=":dayFromName">
          <option value="">--</option>
          <option for="value in [str(v).zfill(2) for v in range(1, 32)]"
                  value=":value">:value</option>
         </select> / 
         <select id=":monthFromName" name=":monthFromName">
          <option value="">--</option>
          <option for="value in [str(v).zfill(2) for v in range(1, 13)]"
                  value=":value">:value</option>
         </select> / 
         <select id=":widgetName" name=":widgetName">
          <option value="">--</option>
          <option for="value in range(field.startYear, field.endYear+1)"
                  value=":value">:value</option>
         </select>
         <!-- The icon for displaying the calendar popup -->
         <x if="field.calendar">
          <input type="hidden" id=":fromName" name=":fromName"/>
          <img id=":'%s_img' % fromName" src=":url('calendar.gif')"/>
          <script>::field.getJsInit(fromName, years)</script>
         </x>
         <!-- Hour and minutes when relevant -->
         <x if="(field.format == 0) and field.searchHour"
            var2="hPart='%s_from_hour' % name;
                  mPart='%s_from_minute' % name">:field.pxHour</x>
        </td>
       </tr>

       <!-- To -->
       <tr var="toName='%s_to' % name;
                dayToName='%s_to_day' % name;
                monthToName='%s_to_month' % name;
                yearToName='%s_to_year' % name">
        <td></td>
        <td><label>:_('search_to')</label>&nbsp;&nbsp;&nbsp;&nbsp;</td>
        <td height="20px">
         <select id=":dayToName" name=":dayToName">
          <option value="">--</option>
          <option for="value in [str(v).zfill(2) for v in range(1, 32)]"
                  value=":value">:value</option>
         </select> / 
         <select id=":monthToName" name=":monthToName">
          <option value="">--</option>
          <option for="value in [str(v).zfill(2) for v in range(1, 13)]"
                  value=":value">:value</option>
         </select> / 
         <select id=":yearToName" name=":yearToName">
          <option value="">--</option>
          <option for="value in range(field.startYear, field.endYear+1)"
                  value=":value">:value</option>
         </select>
         <!-- The icon for displaying the calendar popup -->
         <x if="field.calendar">
          <input type="hidden" id=":toName" name=":toName"/>
          <img id=":'%s_img' % toName" src=":url('calendar.gif')"/>
          <script>::field.getJsInit(toName, years)</script>
         </x>
         <!-- Hour and minutes when relevant -->
         <x if="(field.format == 0) and field.searchHour"
            var2="hPart='%s_to_hour' % name;
                  mPart='%s_to_minute' % name">:field.pxHour</x>
        </td>
       </tr>
      </table>''')

    # Required CSS and Javascript files for this type
    cssFiles = {'edit': ('jscalendar/calendar-blue.css',)}
    jsFiles = {'edit': ('jscalendar/calendar.js',
                        'jscalendar/lang/calendar-en.js',
                        'jscalendar/calendar-setup.js')}
    # Possible values for "format"
    WITH_HOUR = 0
    WITHOUT_HOUR = 1
    dateParts = ('year', 'month', 'day')
    hourParts = ('hour', 'minute')

    def __init__(self, validator=None, multiplicity=(0,1), default=None,
      defaultOnEdit=None, format=WITH_HOUR, dateFormat=None, hourFormat=None,
      calendar=True, startYear=time.localtime()[0]-10,
      endYear=time.localtime()[0]+10, reverseYears=False, minutesPrecision=5,
      show=True, page='main', group=None, layouts=None, move=0, indexed=False,
      mustIndex=True, indexValue=None, searchable=False, readPermission='read',
      writePermission='write', width=None, height=None, maxChars=None,
      colspan=1, master=None, masterValue=None, focus=False, historized=False,
      mapping=None, generateLabel=None, label=None, sdefault=None, scolspan=1,
      swidth=None, sheight=None, persist=True, view=None, cell=None, edit=None,
      xml=None, translations=None, showDay=True, searchHour=False):
        self.format = format
        self.calendar = calendar
        self.startYear = startYear
        self.endYear = endYear
        # If reverseYears is True, in the selection box, available years, from
        # self.startYear to self.endYear will be listed in reverse order.
        self.reverseYears = reverseYears
        # If p_showDay is False, the list for choosing a day will be hidden.
        self.showDay = showDay
        # If no p_dateFormat/p_hourFormat is specified, the application-wide
        # tool.dateFormat/tool.hourFormat is used instead.
        self.dateFormat = dateFormat
        self.hourFormat = hourFormat
        # If "minutesPrecision" is 5, only a multiple of 5 can be encoded. If
        # you want to let users choose any number from 0 to 59, set it to 1.
        self.minutesPrecision = minutesPrecision
        # The search widget will only allow to specify start and end dates
        # without hour, event if format is WITH_HOUR, excepted if searchHour is
        # True.
        self.searchHour = searchHour
        Field.__init__(self, validator, multiplicity, default, defaultOnEdit,
          show, page, group, layouts, move, indexed, mustIndex, indexValue,
          searchable, readPermission, writePermission, width, height, None,
          colspan, master, masterValue, focus, historized, mapping,
          generateLabel, label, sdefault, scolspan, swidth, sheight, persist,
          False, view, cell, edit, xml, translations)

    def getCss(self, layout, r):
        '''CSS files are only required if the calendar must be shown'''
        if self.calendar: Field.getCss(self, layout, r)

    def getJs(self, layout, r, config):
        '''Javascript files are only required if the calendar must be shown'''
        if self.calendar: Field.getJs(self, layout, r, config)

    def getSelectableYears(self):
        '''Gets the list of years one may select for this field.'''
        res = range(self.startYear, self.endYear + 1)
        if self.reverseYears: res.reverse()
        return res

    def validateValue(self, obj, value):
        try:
            value = DateTime(value)
        except (DateTime.DateError, ValueError):
            return obj.translate('bad_date')

    def getFormattedValue(self, o, value, layout='view', showChanges=False,
                          language=None):
        if self.isEmptyValue(o, value): return ''
        # Get the applicable date format
        ui = o.config.ui
        dateFormat = self.dateFormat or ui.dateFormat
        # A problem may occur with some extreme year values. Replace the "year"
        # part "by hand".
        if '%Y' in dateFormat:
            dateFormat = dateFormat.replace('%Y', str(value.year()))
        r = ui.formatDate(o.tool, value, dateFormat, withHour=False)
        if self.format == Date.WITH_HOUR:
            r += ' %s' % value.strftime(self.hourFormat or ui.hourFormat)
        return r

    def getRequestValue(self, o, requestName=None):
        req = o.req
        name = requestName or self.name
        # Manage the "date" part
        value = ''
        for part in self.dateParts:
            # The "day" part may be hidden. Use "1" by default.
            if (part == 'day') and not self.showDay:
                valuePart = '01'
            else:
                valuePart = req['%s_%s' % (name, part)]
            if not valuePart: return
            value += valuePart + '/'
        value = value[:-1]
        # Manage the "hour" part
        if self.format == self.WITH_HOUR:
            value += ' '
            for part in self.hourParts:
                valuePart = req['%s_%s' % (name, part)]
                if not valuePart: return
                value += valuePart + ':'
            value = value[:-1]
        return value

    def searchValueIsEmpty(self, form):
        '''We consider a search value being empty if both "from" and "to" values
           are empty. At an individual level, a "from" or "to" value is
           considered not empty if at least the year is specified.'''
        # The base method determines if the "from" year is empty
        isEmpty = Field.searchValueIsEmpty
        return isEmpty(self, form) and \
               isEmpty(self, form, widgetName='%s_to_year' % self.name)

    def getRequestSuffix(self): return '_year'

    def getStorableValue(self, obj, value, complete=False):
        if not self.isEmptyValue(obj, value):
            return DateTime(value)

    def getDateFromSearchValue(self, year, month, day, hour, setMin):
        '''Gets a valid DateTime instance from date information coming from the
           request as strings in p_year, p_month, p_day and p_hour. Returns None
           if p_year is empty. If p_setMin is True, when some information is
           missing (month or day), we will replace it with the minimum value
           (=1). Else, we will replace it with the maximum value (=12, =31).'''
        if not year: return
        # Set month and day
        if not month:
            month = 1 if setMin else 12
        if not day:
            day = 1 if setMin else 31
        # Set the hour
        if hour is None:
            hour = '00:00' if setMin else '23:59'
        # The specified date may be invalid (ie, 2018/02/31): ensure to produce
        # a valid date in all cases.
        try:
            r = DateTime('%s/%s/%s %s' % (year, month, day, hour))
        except:
            base = DateTime('%s/%s/01' % (year, month))
            r = dates.getLastDayOfMonth(base, hour=hour)
        return r

    def getSearchValue(self, form):
        '''Converts the raw search values from p_form into an interval of
           dates.'''
        # Get the "from" value
        name = self.name
        year = Field.getSearchValue(self, form)
        month = form['%s_from_month' % name]
        day   = form['%s_from_day' % name]
        hour = None
        if self.searchHour:
            hour = '%s:%s' % (form['%s_from_hour' % name] or '00',
                              form['%s_from_minute' % name] or '00')
        fromDate = self.getDateFromSearchValue(year, month, day, hour, True)
        # Get the "to" value"
        year  = form['%s_to_year' % name]
        month = form['%s_to_month' % name]
        day   = form['%s_to_day' % name]
        hour = None
        if self.searchHour:
            hour = '%s:%s' % (form['%s_to_hour' % name] or '23',
                              form['%s_to_minute' % name] or '59')
        toDate = self.getDateFromSearchValue(year, month, day, hour, False)
        return fromDate, toDate

    def getIndexType(self): return 'DateIndex'

    def isSelected(self, o, part, fieldPart, dateValue, dbValue):
        '''When displaying this field, must the particular p_dateValue be
           selected in the sub-field p_fieldPart corresponding to the date
           part ?'''
        # Get the value we must compare (from request or from database)
        req = o.req
        if part in req:
            compValue = req[part]
            if compValue.isdigit():
                compValue = int(compValue)
        else:
            compValue = dbValue
            if compValue:
                compValue = getattr(compValue, fieldPart)()
        # Compare the value
        return compValue == dateValue

    def isSortable(self, usage):
        '''Can this field be sortable ?'''
        if usage == 'search': return Field.isSortable(self, usage)
        return True # Sortable in Ref fields

    def getJsInit(self, name, years):
        '''Gets the Javascript init code for displaying a calendar popup for
           this field, for an input named p_name (which can be different from
           self.name if, ie, it is a search field).'''
        # Always express the range of years in chronological order.
        years = [years[0], years[-1]]
        years.sort()
        return 'Calendar.setup({inputField: "%s", button: "%s_img", ' \
               'onSelect: onSelectDate, range:%s, firstDay: 1})' % \
               (name, name, str(years))
# ------------------------------------------------------------------------------
