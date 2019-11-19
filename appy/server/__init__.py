'''Appy HTTP server'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import os, sys, time, socket, socketserver, logging, pathlib
from http.server import HTTPServer
from appy import utils
from appy.database import Database
from appy.model import Model
from appy.utils import url as uutils
from appy.model.utils import Object as O
from appy.server.static import Config as StaticConfig
from appy.server.handler import HttpHandler, InitHandler

# Constants  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
START_CLASSIC = ':: Starting server ::'
START_CLEAN = ':: Starting clean mode ::'
START_RUN = ':: Starting run mode (%s) ::'
READY = '%s:%s ready (process ID %d).'
STOP_CLASSIC = ':: %s:%s stopped ::'
STOP_CLEAN = ':: Clean end ::'
STOP_RUN = ':: Run end ::'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Config:
    '''HTTP server configuration for a Appy site'''
    def __init__(self):
        # The server address
        self.address = 'localhost'
        # The server port
        self.port = 8000
        # The protocol in use
        self.protocol = 'http'
        # Configuration for static content (set by m_set below)
        self.static = None

    def set(self, appFolder):
        '''Sets site-specific configuration elements'''
        appPath = pathlib.Path(appFolder)
        self.static = StaticConfig(appPath)

    def getUrl(self):
        '''Returns the base URL for this Appy server'''
        r = '%s://%s' % (self.protocol, self.address)
        if self.port != 80:
            r = '%s:%d' % (r, self.port)
        return r

    def inUse(self):
        '''Returns True if (self.address, self.port) is already in use'''
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Set option "Reuse" for this socket. This will prevent us to get a
        # "already in use" error when TCP connections are left in TIME_WAIT
        # state.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((self.address, self.port))
        except socket.error as e:
            if e.errno == 98:
                return True
        s.close()

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Server(socketserver.ThreadingMixIn, HTTPServer):
    '''Appy HTTP server'''

    # Terminate threads when the main process is terminated
    daemon_threads = True
    # Store, for every logged user, the date/time of its last access
    loggedUsers = {}

    def logStart(self, method):
        '''Logs the appropriate "ready" message, depending on p_self.mode'''
        if self.classic:
            text = START_CLASSIC
        elif self.mode == 'clean':
            text = START_CLEAN
        elif self.mode == 'run':
            text = START_RUN % method
        self.loggers.app.info(text)

    def logShutdown(self):
        '''Logs the appropriate "shutdown" message, depending on p_self.mode'''
        if self.classic:
            cfg = self.config.server
            text = STOP_CLASSIC % (cfg.address, cfg.port)
        elif self.mode == 'clean':
            text = STOP_CLEAN
        elif self.mode == 'run':
            text = STOP_RUN
        self.loggers.app.info(text)

    def __init__(self, config, mode, method=None):
        # p_config is the main app config
        self.config = config
        # Ensure the config is valid
        config.check()
        # p_mode can be:
        # ----------------------------------------------------------------------
        # "fg"     | Server start, in the foreground (debug mode)
        # "bg"     | Server start, in the background
        # "clean"  | Special mode for cleaning the database
        # "run"    | Special mode for executing a single p_method on the
        #          | application tool.
        # ----------------------------------------------------------------------
        # Modes "clean" and "run" misuse the server to perform a specific task.
        # In those modes, the server is not really started (it does not listen
        # to a port) and is shutdowned immediately after the task has been
        # performed.
        # ----------------------------------------------------------------------
        self.mode = mode
        self.classic = mode in ('fg', 'bg')
        # Initialise the loggers
        cfg = config.log
        self.loggers = O(site=cfg.getLogger('site'),
                         app=cfg.getLogger('app', mode != 'bg'))
        self.logStart(method)
        try:
            # Load the application model. As a side-effect, the app's po files
            # were also already loaded.
            self.model, poFiles = config.model.get(config, self.loggers.app)
            # Initialise the HTTP server
            cfg = config.server
            if self.classic:
                HTTPServer.__init__(self, (cfg.address, cfg.port), HttpHandler)
            # Create the initialisation handler
            handler = InitHandler(self)
            # Initialise the database. More precisely, it connects to it and
            # performs the task linked to p_self.mode.
            config.database.getDatabase(self, handler, poFiles, method=method)
            # Initialise the static configuration
            cfg.static.init(config.ui)
            # Remove the initialisation handler
            InitHandler.remove()
        except (Model.Error, Database.Error) as err:
            self.abort(err)
        except Exception:
            self.abort()
        # The current user login
        self.user = 'system'
        # The server is ready
        if self.classic:
            self.loggers.app.info(READY % (cfg.address, cfg.port, os.getpid()))

    def handle_error(self, request, client_address):
        '''Handles an exception raised while a handler processes a request'''
        self.logTraceback()

    def logTraceback(self):
        '''Logs a traceback'''
        self.loggers.app.error(utils.Traceback.get().strip())

    def shutdown(self):
        '''Normal server shutdown'''
        # Logs the shutdown
        self.logShutdown()
        # Shutdown the loggers
        logging.shutdown()
        # Shutdown the database
        database = self.database
        if database: database.close()
        # Call the base method
        if self.classic:
            HTTPServer.shutdown(self)

    def abort(self, error=None):
        '''Server shutdown following an error'''
        # Log the error, or the full traceback if requested
        if error:
            self.loggers.app.error(error)
        else:
            self.logTraceback()
        # Shutdown the loggers
        logging.shutdown()
        # If the database was already there, close it
        if hasattr(self, 'database'): self.database.close()
        # Exit
        sys.exit(1)

    def buildUrl(self, name='', base='appy', ram=False, bg=False):
        '''Builds the full URL of a static resource, like an image, a Javascript
           or a CSS file, named p_name. If p_ram is True, p_base is ignored and
           replaced with the RAM root. If p_bg is True, p_name is an image that
           is meant to be used in a "style" attribute for defining the
           background image of some XHTML tag.'''
        cfg = self.config.server
        # If no extension is found in p_name, we suppose it is a png image
        if name:
            name = '/%s' % name if '.' in name else '/%s.png' % name
        # Patch p_base if the static resource is in RAM
        if ram: base = cfg.static.ramRoot
        r = '%s/%s/%s%s' % (cfg.getUrl(), cfg.static.root, base, name)
        return r if not bg else 'background-image: url(%s)' % r

    def getUrlParams(self, params):
        '''Return the URL-encoded version of dict p_params as required by
           m_getUrl.'''
        # Manage special parameter "unique"
        if 'unique' in params:
            if params['unique']:
                params['_hash'] = '%f' % time.time()
            del(params['unique'])
        return uutils.encode(params, ignoreNoneValues=True)

    def getUrl(self, o, sub=None, relative=False, **params):
        '''Gets the URL of some p_o(bject)'''
        # Parameters are as follows.
        # ----------------------------------------------------------------------
        # sub      | If specified, it denotes a part that will be added to the
        #          | object base URL for getting one of its specific sub-pages,
        #          | like "view" or "edit".
        # ----------------------------------------------------------------------
        # relative | If True, the base URL <protocol>://<domain> will not be
        #          | part of the result.
        # ----------------------------------------------------------------------
        # params   | Every entry in p_params will be added as-is as a parameter
        #          | to the URL, excepted if the value is None or key is
        #          | "unique": in that case, its value must be boolean: if
        #          | False, the entry will be removed; if True, it will be
        #          | replaced with a parameter whose value will be based on
        #          | time.time() in order to obtain a link that has never been
        #          | visited by the browser.
        # ----------------------------------------------------------------------
        # The presence of parameter "popup=True" in the URL will open the
        # corresponding object-related page in the Appy iframe, in a
        # minimalistic way (ie, without portlet).
        # ----------------------------------------------------------------------
        # The base app URL
        r = '' if relative else self.config.server.getUrl()
        # Prefix the object ID with a dash if the object is temporary
        r = '%s/%s' % (r, o.id)
        # Manage p_sub
        r = '%s/%s' % (r, sub) if sub else r
        # Manage p_params
        if not params: return r
        return '%s?%s' % (r, self.getUrlParams(params))

    def patchUrl(self, url, **params):
        '''Modifies p_url and injects p_params into it. They will override their
           homonyms that would be encoded within p_url.'''
        if not params: return url
        # Extract existing parameters from p_url and update them with p_params
        r, parameters = uutils.split(url)
        if parameters:
            parameters.update(params)
        else:
            parameters = params
        return '%s?%s' % (r, self.getUrlParams(parameters))
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
