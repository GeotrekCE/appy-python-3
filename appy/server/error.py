# ~license~

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy.px import Px
from appy.ui.js import Quote
from appy.utils import Traceback
from appy.ui.template import Template

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Error:
    '''Represents a server error'''

    # Error 404: page not found
    px404 = Px('''<div>::msg</div>
     <div if="not isAnon and not popup">
      <a href=":config.server.getUrl()">:_('app_home')</a>
     </div>''', template=Template.px, hook='content')

    # Error 403: unauthorized
    px403 = Px('''<div><img src=":url('fake')" style="margin-right: 5px"/>
                       <x>::msg</x></div>''',
     template=Template.px, hook='content')

    # Error 500: server error
    px500 = Px('''<div><img src=":url('warning')" style="margin-right: 5px"/>
                       <x>::msg</x></div>''',
     template=Template.px, hook='content')

    @classmethod
    def get(class_, code, traversal):
        '''A server error just occurred. Try to return a nice error page. If it
           fails (ie, the error is produced in the main PX template), dump a
           simple traceback.'''
        # When managing an error, ensure no database commit will occur
        handler = traversal.handler
        handler.commit = False
        # Determine the PX corresponding to the error p_code
        px = getattr(class_, 'px%d' % code, 'px500')
        # Get the last PX context or create a fresh one if there is no context
        context = traversal.context or traversal.createContext()
        # If we are called by an Ajax request, return a minimalist error page,
        # mimicking the one produced in a popup.
        if context.ajax: context.popup = True
        # For an admin, show a traceback. For normal humans, show a readable
        # error message.
        if traversal.user.hasRole('Manager'):
            content = Traceback.get(html=True)
        else:
            # For debug
            content = Traceback.get(html=True)
        context.msg = content
        try:
            return px(context)
        except Exception as err:
            return '<p>%s</p>' % content
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
