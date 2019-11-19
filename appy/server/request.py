'''A "request" stores HTTP GET request parameters and/or HTTP POST form
   values.'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy.model.utils import Object
# Check https://stackoverflow.com/questions/4233218/python-how-do-i-get-key-\
#          value-pairs-from-the-basehttprequesthandler-http-post-h

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Request(Object):
    '''Represents data coming from a HTTP request'''

    @classmethod
    def create(class_, handler):
        '''Analyses various elements from an incoming HTTP request (GET
           parameters, POST form data, cookies) and creates a Request object for
           storing them. If no element is found, an empty Request is created.'''
        # Create the Request instance
        req = Request()
        # Get parameters from a GET request if any
        parts = handler.parts
        last = parts[-1] if parts else None
        if last and ('?' in last):
            lastPart, params = last.split('?', 1)
            req.parse(params)
            # As a side-effect, remove parameters from the last part
            parts[-1] = lastPart
        # Get POST form data if any
        contentType = handler.headers['Content-Type']
        if contentType:
            # Get the request length and content
            length = int(handler.headers['Content-Length'])
            content = handler.rfile.read(length).decode('utf-8')
            # Several content encodings are possible
            if contentType == 'application/x-www-form-urlencoded':
                # Form elements are encoded in a way similar to GET parameters
                req.parse(content)
            elif contentType.startswith('multipart/form-data'):
                # Form elements are encoded in a "multi-part" message, whose
                # elements are separated by some boundary text.
                boundary = contentType[contentType.index('boundary=')+9:]
                req.parseMultiPart(content, boundary)
        # Get Cookies
        cookieString = handler.headers['Cookie']
        if cookieString is not None:
            # Cookies' (name, value) pairs are separated by semicolons
            req.parse(cookieString, sep=';')
        return req

    def parse(self, params, sep='&'):
        '''Parse GET/POST p_param(eters) and add one attribute per parameter'''
        for param in params.split(sep):
            # Every param is of the form <name>=<value> or simply <name>
            if '=' in param:
                # <name>=<value>
                name, value = param.split('=', 1)
            else:
                # <name>
                name = param
                value = None
            setattr(self, name.strip(), value)

    def parseMultiPart(self, content, boundary):
        '''Parses multi-part form content and add to p_self one attribute per
           form element.'''
        for element in content.split(boundary):
            if not element: continue
            # Find the element name
            i = element.find('name="')
            if i == -1: continue
            nameStart = i + 6
            nameEnd = element.find('"', nameStart)
            name = element[nameStart:nameEnd]
            # Find the element value
            value = element[nameEnd+1:]
            if value.endswith('--'):
                value = value[:-2]
            setattr(self, name.strip(), value.strip())

    def patchFromTemplate(self, o):
        '''p_o is a temp object that is going to be edited via px "edit". If a
           template object must be used to pre-fill the web form, patch the
           request with the values retrieved on this template object.'''
        # This has sense only for temporary objects
        if not o.isTemp(): return
        id = self.template
        if not id: return
        template = o.getObject(id)
        # Some fields may be excluded from the copy
        toExclude = o.class_.getCreateExclude(o)
        # Browse fields
        for field in o.getFields('edit'):
            if field.name in toExclude: continue
            field.setRequestValue(template)
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
