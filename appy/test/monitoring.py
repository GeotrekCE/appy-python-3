# ------------------------------------------------------------------------------
import os
from appy.utils import Version

# ------------------------------------------------------------------------------
class Monitoring:
    '''Implements stuff allowing to perform monitoring on a Appy application.
       * URL <yourapp>/config/check can be called to get monitoring info;
       * Configure monitoring parameters by updating attributes of the
         Monitoring instance defined in the Config class.'''

    def __init__(self, forceComplete=False):
        # When returning a success status code, what code to return ?
        self.ok = 'OK'
        # When returning a failure status code, what code to return ?
        self.ko = 'KO'
        # Do we check the presence of LibreOffice running in server mode ?
        self.checkLo = True
        # Normally, producing a complete or summary status depends on a request
        # parameter. If p_forceComplete is True, however, we always return the
        # complete status.
        self.forceComplete = forceComplete
        # The app may define here additional version information, as a list of
        # (key, value) tuples, keys and values being strings.
        self.app = []

    def asText(self, r):
        '''Returns monitoring info p_r as pure text'''
        return '\n'.join('%s: %s' % (k, v) for k, v in r)

    def asHtml(self, r):
        '''Returns monitoring info p_r as HTML'''
        rows = ['<tr><th>%s</th><td>%s</td>' % (k, v) for k, v in r]
        return '<table class="grid">%s</table>' % '\n'.join(rows)

    def get(self, request, config, html=False):
        '''Returns monitoring-related info'''
        # The global monitoring status
        success = True
        # Check if LibreOffice is running
        if self.checkLo:
            loLine = ''
            null, out = os.popen4('ps -ef | grep "soffice"')
            for line in out.readlines():
                if "accept=socket" in line:
                    loLine = line
                    break
            if not loLine:
                success = False
        # Do we need to return complete information or only a status code ?
        status = success and self.ok or self.ko
        if ('all' not in request) and not self.forceComplete: return status
        # Return complete information
        r = [('Status', status), ('Appy version', appy.getVersion())]
        if self.checkLo:
            # Appy parameters for connecting to LibreOffice in server mode
            r.append( ('UNO-enabled Python',
                       config.unoEnabledPython or '<not specified>'))
            r.append(('LibreOffice port', str(config.libreOfficePort)))
            # Info about the running LibreOffice server
            if not loLine:
                r.append(('LibreOffice status', 'Not found'))
            else:
                r.append(('LibreOffice status', 'Running: %s' % loLine))
        # Add app-specific info when available
        if self.app: r += self.app
        # Return pure text of HTML when requested
        return html and self.asHtml(r) or self.asText(r)
# ------------------------------------------------------------------------------
