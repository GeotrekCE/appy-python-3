# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import inspect, pathlib, mimetypes, os.path, email.utils, collections
from DateTime import DateTime
import appy

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
MAP_VALUE_NOT_PATH = 'Values from the map must be pathlib.Path objects.'
PATH_NOT_FOUND     = 'Path "%s" was not found or is not a folder.'
RAM_ROOT_IN_MAP    = 'Ram root "%s" is also used as key for ' \
                     'appy.server.static.Config.map.'
BROKEN_PIPE        = 'Broken pipe while serving %s.'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Config:
    '''Configuration options for static content served by the Appy HTTP
       server.'''
    def __init__(self, appPath, root='static'):
        # The root URL for all static content. Defaults to "static". Any static
        # content will be available behind URL starting with <host>:/<root>/...
        self.root = root
        # The following attribute identifies base URLs and their corresponding
        # folders on disk. For example, the entry with key "appy" maps any URL
        # <host>:/<root>/appy/<resource> to the actual <resource> on disk, at
        # /<some>/<path>/<resource>.
        appyPath = pathlib.Path(inspect.getfile(appy)).parent
        map = collections.OrderedDict()
        map['appy'] = appyPath / 'ui' / 'static'
        map[appPath.stem] = appPath / 'static'
        self.map = map
        # The above-mentioned attributes define how to map a URL to a resource
        # on disk. A second mechanism is available, mapping URLs to "RAM"
        # resources, directly loaded in memory as strings. Such RAM resources
        # will be stored in dict Static.ram defined on class Static below.
        # Attribute "ramRoot" hereafter defines the base path, after the
        # "static" part, allowing Appy to distinguish a RAM from a disk
        # resource. It defaults to "ram".
        self.ramRoot = 'ram'
        # Let's illustrate this mechanism with an example. Suppose that:
        # * ramRoot = "ram" ;
        # * the content of appy/ui/static/appy.css is loaded in a string
        #   variable named "appyCss";
        # * dict Static.ram = {'appy.css': appyCss}
        # The content of appy.css will be returned to the browser if request via
        #                  <host>/static/ram/appy.css
        # Beyond being probably a bit more performant than serving files from
        # the disk, this approach's great advantage it to be able to compute, at
        # server startup, the content of resources. The hereabove example was
        # not randomly chosen: Appy CSS files like appy.css are actually
        # template files containing variables that need to be replaced by their
        # actual values, coming from the app's (ui) config.
        # When adding keys in Static.ram, ensure the key is a filename-like
        # name: the MIME type will be deduced from the file extension.

        # Remember the date/time this instance has been created: it will be used
        # as last modification date for RAM resources.
        self.created = DateTime()

    def check(self):
        '''Checks that every entry in p_self.map is valid'''
        for key, path in self.map.items():
            # Paths must be pathlib.Path instances
            if not isinstance(path, pathlib.Path):
                raise Exception(MAP_VALUE_NOT_PATH)
            # Paths must exist and be folders
            if not path.is_dir():
                raise Exception(PATH_NOT_FOUND % path)
        # Ensure the RAM root is not used as key in self.map
        if self.ramRoot in self.map:
            raise Exception(RAM_ROOT_IN_MAP % self.ramRoot)

    def init(self, uiConfig):
        '''Reads all CSS files from all disk locations containing static content
           (in p_self.map) and loads them in Static.ram, after having replaced
           variables with their values from the app's (ui) config.'''
        for path in self.map.values():
            for cssFile in path.glob('*.css'):
                # Read the content of this file
                with cssFile.open('rb') as f:
                    cssContent = f.read()
                    # Add it to Static.ram, with variables replaced
                    Static.ram[cssFile.name] = uiConfig.patchCss(cssContent)

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Static:
    '''Class responsible for serving static content'''

    # We will write in the socket per bunch of BYTES bytes
    BYTES = 50000

    # The dict of RAM resources (see doc in class Config hereabove)
    ram = collections.OrderedDict()

    @classmethod
    def notFound(class_, handler, config):
        '''Raise a HTTP 404 error if the resource defined by p_handler.parts was
           not found.'''
        code = 404
        path = '/%s/%s' % (config.root, '/'.join(handler.parts))
        handler.log('app', 'error', '%d@%s' % (code, path))
        handler.send_response(code)
        handler.end_headers()
        return code

    @classmethod
    def write(class_, handler, path, modified, content=None):
        '''Returns the content of file @p_path, or file p_content if not None'''
        # If the file @ p_path has not changed since the last time the browser
        # asked it, return an empty response with code 304 "Not Modified". Else,
        # return file content with a code 200 "OK".
        browserDate = handler.headers.get('If-Modified-Since')
        smodified = email.utils.formatdate(modified) # RFC 822 string
        if not browserDate or (smodified > browserDate):
            code = 200
            handler.send_response(code)
            hasContent = content is not None
            # Initialise response headers. Guess p_path's MIME type.
            mimeType, encoding = mimetypes.guess_type(path)
            mimeType = mimeType or 'application/octet-stream'
            set = handler.send_header
            set('Content-Type', mimeType)
            size = len(content) if hasContent else os.path.getsize(path)
            set('Content-Length', size)
            if encoding: set('Content-Encoding', encoding)
            # For now, disable byte serving (value "bytes" instead of "none")
            set('Accept-Ranges', 'none')
            set('Last-Modified', smodified)
            handler.end_headers()
            # Write the file content to the socket
            if hasContent:
                handler.wfile.write(content)
            else:
                f = open(path, 'rb')
                while True:
                    chunk = f.read(Static.BYTES)
                    if not chunk: break
                    try:
                        handler.wfile.write(chunk)
                    except BrokenPipeError:
                        handler.log('app', 'error', BROKEN_PIPE % path)
                f.close()
        else:
            code = 304
            handler.send_response(code)
            handler.end_headers()
        return code

    @classmethod
    def writeFromDisk(class_, handler, path):
        '''Serve a static file from disk, whose URL path is p_path'''
        # The string version of p_path
        spath = str(path)
        return class_.write(handler, spath, os.path.getmtime(spath))

    @classmethod
    def writeFromRam(class_, handler, config):
        '''Serve a static file loaded in RAM, from dict Static.ram'''
        # p_handler.parts contains something starting with ['ram', ...]
        if len(handler.parts) == 1:
            return class_.notFound(handler, config)
        # Re-join the splitted path to produce the key allowing to get the file
        # content in Static.ram.
        key = '/'.join(handler.parts[1:])
        # Indeed, Static.ram is a simple (ordered) dict, not a hierachical dict
        # of dicts. Standard Appy resources (like appy.css) stored in Static.ram
        # have keys whose names are simple filename-like keys ("appy.css"). But
        # if you want to reproduce a complete "file hierarchy" in Static.ram by
        # adding path-like information in the key, you can do it. By computing
        # keys like we did hereabove, a URL like:
        #               <host>/static/ram/a/b/c/some.css
        # can be served by defining, in Static.ram, an entry with key
        #                      "a/b/c/some.css"
        content = class_.ram.get(key)
        if content is None:
            return class_.notFound(handler, config)
        return class_.write(handler, key, config.created, content=content)

    @classmethod
    def removeParams(class_, handler):
        '''Remove potential GET parameters in the last part within
           p_handler.parts.'''
        if not handler.parts: return
        last = handler.parts[-1]
        if '?' in last:
            handler.parts[-1] = last[:last.index('?')]

    @classmethod
    def get(class_, handler):
        '''Returns the content of the static file whose splitted path is defined
           in p_handler.parts.'''
        # Unwrap the static config
        config = handler.server.config.server.static
        # The currently walked path
        path = None
        # Remove the potential GET params
        class_.removeParams(handler)
        # Walk parts
        for part in handler.parts:
            if path is None:
                # We are at the root of the search: "part" must correspond to
                # the RAM root or to a key from config.map.
                if part == config.ramRoot:
                    return class_.writeFromRam(handler, config)
                elif part in config.map:
                    path = config.map[part]
                else:
                    return class_.notFound(handler, config)
            else:
                path = path / part
                if not path.exists():
                    return class_.notFound(handler, config)
        # We have walked the complete path: ensure it is a file
        if not path or not path.is_file():
            return class_.notFound(handler, config)
        # Read the file content and return it
        return class_.writeFromDisk(handler, path)

    @classmethod
    def isFilename(class_, name):
        '''Does p_name correspond to a filename ?'''
        # Returns True if a dot is found with p_name. Ignore any content being
        # after a question mark (p_name can be part of a URL).
        qm = name.find('?')
        return '.' in name if qm == -1 else name.find('.', 0, qm) != -1
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
