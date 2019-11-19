'''Appy module managing log files'''

# ------------------------------------------------------------------------------
import logging, sys, pathlib
from appy.model.utils import Object

# ------------------------------------------------------------------------------
class Config:
    '''Logging-related parameters for your app'''
    # Available attributes to dump within log entries
    logAttributes = {
      'time': 'asctime', # The current date & time
      'level': 'levelname', # The log level
      'message': 'message' # The message to log, prefixed by the user login
    }

    def __init__(self, siteDateFormat='%Y/%m/%d %H:%M:%S',
                 appDateFormat='%Y/%m/%d %H:%M:%S',
                 siteAttributes=('time', 'message'),
                 appAttributes=('time', 'level', 'message'),
                 siteMessageParts=('ip', 'port', 'command', 'protocol', 'path',
                                   'message'),
                 appMessageParts=('user', 'message'),
                 siteSep=' | ', appSep=' | '):
        '''Initializes the logging configuration options.
           - p_siteDateFormat and p_appDateFormat define the format of dates
             dumped in log messages;
           - p_siteAttributes and p_appAttributes store the list of attributes
             that will be dumped in every log entry;
           - p_siteMessageParts and p_appMessageParts store the list of
             attributes contained within composite attribute "message";
           - p_siteSep and p_appSep store the separators that will be inserted
             between attributes.
        '''
        # Create a sub-object for splitting site- and app-related configuration
        # options.
        for type in ('app', 'site'):
            sub = Object(dateFormat=eval('%sDateFormat' % type),# ~pathlib.Path~
                         attributes=eval('%sAttributes' % type),
                         messageParts=eval('%sMessageParts' % type),
                         sep=eval('%sSep' % type))
            setattr(self, type, sub)

    def set(self, siteLogFolder, appLogFolder):
        '''Sets site-specific configuration elements'''
        # self.site.path is the path to the site log file, logging all HTTP
        # traffic on the site.
        self.site.path = pathlib.Path(siteLogFolder)
        # self.app.path is the path to the app-specific log, containing messages
        # dumped by the app and some by Appy itself.
        self.app.path = pathlib.Path(appLogFolder)
        # Typically, the site and app log files have standardized names and are
        # stored in <site>/var, with database-related files:
        # * "siteLogPath"    is <site>/var/site.log
        # * "appLogPath"     is <site>/var/app.log

    def getFormatter(self, type):
        '''Gets a logging.Formatter object for log entries of p_type'''
        sub = getattr(self, type)
        # Define the list of attributes to dump in every log entry
        attributes = []
        for name in sub.attributes:
            attributes.append('%%(%s)s' % Config.logAttributes[name])
        return logging.Formatter(sub.sep.join(attributes),
                                 datefmt=sub.dateFormat)

    def getLogger(self, type, debug=False):
        '''Return the site or app logger instance (depending on p_type), that
           will output log messages to self.siteLogPath or self.appLogPath. If
           p_debug is True, we are in debug mode: an additional handler will be
           defined for producing output on stdout.'''
        logger = logging.getLogger(type)
        # Get the path to the file where to log messages
        sub = getattr(self, type)
        path = sub.path
        # Add a file handler to the logger
        created = not path.is_file()
        path = str(path)
        logger.addHandler(logging.FileHandler(path))
        if debug:
            # Add an additional handler for outputing messages to stdout as well
            logger.addHandler(logging.StreamHandler(sys.stdout))
            level = logging.DEBUG
        else:
            level = logging.INFO
        # Messages under this level will not be dumped
        logger.setLevel(level)
        # Set a formatter for log entries
        formatter = self.getFormatter(type)
        for handler in logger.handlers:
            handler.setFormatter(formatter)
        # Return the created logger
        if created: logger.info('%s created.' % path)
        return logger
# ------------------------------------------------------------------------------
