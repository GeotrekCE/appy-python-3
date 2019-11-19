'''Date-related classes and functions'''

# ~license~
# ------------------------------------------------------------------------------
try:
    from DateTime import DateTime
except ImportError:
    # This module manipulates DateTime objects from the non-standard DateTime
    # module, installable via command "pip3 install DateTime"
    pass

# ------------------------------------------------------------------------------
class Date:
    '''Date-related methods'''

    @classmethod
    def toUTC(class_, d):
        '''When manipulating DateTime instances, like p_d, errors can raise when
           performing operations on dates that are not in Universal time, during
           months when changing from/to summer/winter hour. This function
           returns p_d set to UTC.'''
        return DateTime('%d/%d/%d UTC' % (d.year(), d.month(), d.day()))

    @classmethod
    def format(class_, tool, date, format=None, withHour=True, language=None):
        '''Returns p_d(ate) formatted as specified by p_format, or
           config.ui.dateFormat if not specified. If p_withHour is True, hour is
           appended, with a format specified in config.ui.hourFormat.'''
        fmt = format or tool.config.ui.dateFormat
        # Resolve Appy-specific formatting symbols used for getting translated
        # names of days or months:
        # - %dt: translated name of day
        # - %DT: translated name of day, capitalized
        # - %mt: translated name of month
        # - %MT: translated name of month, capitalized
        # - %dd: day number, but without leading '0' if < 10
        if ('%dt' in fmt) or ('%DT' in fmt):
            day = tool.translate('day_%s' % date._aday, language=language)
            fmt = fmt.replace('%dt', day.lower()).replace('%DT', day)
        if ('%mt' in fmt) or ('%MT' in fmt):
            month = tool.translate('month_%s' % date._amon, language=language)
            fmt = fmt.replace('%mt', month.lower()).replace('%MT', month)
        if '%dd' in fmt: fmt = fmt.replace('%dd', str(date.day()))
        # Resolve all other, standard, symbols
        r = date.strftime(fmt)
        # Append hour from tool.hourFormat
        if withHour and (date._hour or date._minute):
            r += ' (%s)' % date.strftime(tool.config.ui.hourFormat)
        return r

# ------------------------------------------------------------------------------
class DayIterator:
    '''Class allowing to iterate over a range of days'''

    def __init__(self, startDay, endDay, back=False):
        self.start = Date.toUTC(startDay)
        self.end = Date.toUTC(endDay)
        # If p_back is True, the iterator will allow to browse days from end to
        # start.
        self.back = back
        self.finished = False
        # Store where we are within [start, end] (or [end, start] if back)
        if not back:
            self.current = self.start
        else:
            self.current = self.end

    def __iter__(self): return self
    def __next__(self):
        '''Returns the next day'''
        if self.finished:
            raise StopIteration
        res = self.current
        # Get the next day, forward
        if not self.back:
            if self.current >= self.end:
                self.finished = True
            else:
                self.current += 1
        # Get the next day, backward
        else:
            if self.current <= self.start:
                self.finished = True
            else:
                self.current -= 1
        return res

# ------------------------------------------------------------------------------
def getLastDayOfMonth(date, hour=None):
    '''Returns a DateTime object representing the last day of date.month()'''
    day = 31
    month = date.month()
    year = date.year()
    found = False
    while not found:
        try:
            res = DateTime('%d/%d/%d %s' % (year, month, day, hour or '12:00'))
            found = True
        except DateTime.DateError:
            day -= 1
    return res

def getDayInterval(date):
    '''Returns a tuple (startOfDay, endOfDay) representing the whole day into
       which p_date occurs.'''
    day = date.strftime('%Y/%m/%d')
    return DateTime('%s 00:00' % day), DateTime('%s 23:59' % day)
# ------------------------------------------------------------------------------
