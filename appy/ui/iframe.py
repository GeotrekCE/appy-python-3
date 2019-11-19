'''Global elements to include in HTML pages'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy.ui.js import Quote
from appy.ui.includer import Includer

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Iframe:
    '''Represents the unique Appy iframe popup'''

    view = '''
     <div id="iframePopup" class="popup"
          onmousedown="dragStart(event)" onmouseup="dragStop(event)"
          onmousemove="dragIt(event)"
          onmouseover="dragPropose(event)" onmouseout="dragStop(event)">
      <img align="%s" src="%s" class="clickable"
           onclick="closePopup('iframePopup',null,true)"/>
      <iframe id="appyIFrame" name="appyIFrame" frameborder="0"></iframe>
     </div>'''

    # HTML page to render for closing the popup
    back = "<html><head>%s</head><body><script>backFromPopup(%s)</script>" \
           "</body></html>"

    @classmethod
    def goBack(class_, tool, initiator=None):
        '''Returns a HTML page allowing to close the iframe popup and refresh
           the base page.'''
        # The initiator may force to go back to some URL
        if initiator and initiator.backFromPopupUrl:
            backUrl = Quote.js(initiator.backFromPopupUrl)
        else:
            backUrl = 'null'
        # Include appy.js and call a Javascript function that will do the job
        return class_.back % (Includer.js(tool.buildUrl('appy.js')), backUrl)
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
