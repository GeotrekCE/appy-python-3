'''A "request" stores HTTP GET request parameters and/or HTTP POST form
   values.'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import urllib.parse

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Response:
    '''Represents the response that will be sent back to the client after having
       received a HTTP request.'''

    def __init__(self, handler):
        # A link to the p_handler
        self.handler = handler
        # The HTTP code for the response
        self.code = 200
        # The message to be returned to the user
        self.message = None
        # Response headers
        if handler.fake:
            headers = {}
        else:
            headers = {'Server': handler.version_string(),
                       'Date': handler.date_time_string(),
                       'Content-type': 'text/html;charset=UTF-8',
                       'Cache-Control': 'no-cache, no-store, must-revalidate',
                       'Expires': '0'}
        self.headers = headers

    def setHeader(self, name, value):
        '''Adds (or replace) a HTTP header among response headers'''
        self.headers[name] = value

    def setCookie(self, name, value):
        '''Adds a cookie among response headers, in special key "Cookies" that
           will be converted to as many "Set-Cookie" HTTP header entries as
           there are entries at this key.

           If p_value is "deleted", the cookie is built in such a way that it
           will be immediately disabled by the browser.'''
        # Create entry "Cookies" in response headers if it does not exist
        if 'Cookies' not in self.headers:
            self.headers['Cookies'] = {}
        # Set the value for the cookie. A special value is defined if the
        # objective is to disable the cookie.
        if value == 'deleted': value = '%s; Max-Age=0' % value
        self.headers['Cookies'][name] = '%s; Path=/' % value

    def addMessage(self, message):
        '''Adds a message to p_self.message'''
        if self.message is None:
            self.message = message
        else:
            self.message = '%s<br/>%s' % (self.message, message)

    def goto(self, url=None, message=None):
        '''Redirect the user to p_url'''
        if message: self.addMessage(message)
        self.code = 303
        # Redirect to p_url or to the referer URL if no p_url has been given
        self.headers['Location'] = url or self.handler.headers['Referer']

    def build(self, code, content=None):
        '''Builds and sent the response back to the client'''
        handler = self.handler
        # 1. The status line, including the responde code
        handler.send_response_only(self.code)
        # 2. Add HTTP headers
        # 2.1. Add p_self.message as a cookie if present
        if self.message is not None:
            quoted = urllib.parse.quote(self.message)
            self.setCookie('AppyMessage', quoted)
        # 2.2. Add all headers
        for name, value in self.headers.items():
            # Manage special key containing cookies
            if name == 'Cookies':
                for key, v in value.items():
                    handler.send_header('Set-Cookie', '%s=%s' % (key, v))
            else:
                # Manage any other key
                handler.send_header(name, value)
        handler.end_headers()
        # 3. Content, as bytes
        if content:
            handler.wfile.write(content.encode('utf-8'))
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
