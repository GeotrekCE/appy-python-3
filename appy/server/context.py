# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy.px import Px

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class AuthenticationContext:
    '''When an application uses an authentication context, its users, when
       logging in, must, besides their login and password, choose a context
       among possible authentication contexts. Then, your application has access
       to the chosen context via the handler attribute "authContext".

       If you want to use authentication contexts in your Appy application, you
       must create a class that inherits from this one and overrides some of its
       methods (see below). Then, in your Config instance set an instance of
       your class in attribute config.security.authContext.
    '''

    # Part of the login form for choosing the context
    pxOnLogin = Px('''
     <x>:_('login_context')</x>
     <select id="__ac_ctx" name="__ac_ctx"
             var="ctxDefault=ctx.getDefaultContext(tool)">
      <option value="">:_('choose_a_value')</option>
      <option for="opt in ctx.getContexts(tool)" value=":opt[0]"
              selected=":opt[0] == ctxDefault">:opt[1]</option>
     </select>''')

    # Zone where to display (or switch) the context when the user is logged
    pxLogged = Px('''
     <x var="showSwitchOptions=ctx._showSwitchOptions(tool)">
      <x if="showSwitchOptions"
         var2="options,present=ctx._getSwitchOptions(tool)">
       <select if="options" class="discreet"
               onchange=":'switchContext(this,%s)' % q(ztool.getSiteUrl())">
        <!-- Set this option only to be able to select a single option -->
        <option if="not present and (len(options) == 1)"></option>
        <option for="opt in options" value=":opt[0]"
                selected=":opt[0] == req.authContext">:opt[1]</option>
    
       </select>
      </x>
      <!-- Display the unswitchable authentication context -->
      <x if="not showSwitchOptions and req.authContext">&mdash;
       <x>:req.authContextName</x>
      </x>
     </x>''')

    # Methods starting with an underscore should not be overridden
    def __init__(self, chooseOnLogin=True, noContextPosition='start',
                 homeAfterSwitch=False):
        # Must the user choose its context when logging in ?
        self.chooseOnLogin = chooseOnLogin
        # When choosing a context is not mandatory (see m_isMandatory) and the
        # special entry "no context" can thus be selected, this attribute
        # indicates it must be inserted in the list of available contexts: at
        # the "start" or at the "end".
        self.noContextPosition = noContextPosition
        # Note that chooseOnLogin=False & switchContext=False (see below) is
        # useless.
        # ~~~
        # By default, after switching the context, the user stays on the same
        # page. If you want him to be redirected to its home page, set the
        # following attribute to True.
        self.homeAfterSwitch = homeAfterSwitch

    def _showSwitchOptions(self, tool):
        '''In some situations, switch options are not to be shown'''
        # On some pages, selectors can't be shown
        if not tool.o.showGlobalSelector(): return
        # No switch option if switching is not allowed
        if not self.switchContext(tool): return
        return True

    def _getSwitchOptions(self, tool):
        '''Returns a tuple (options, present), where:
           - "options" is the list of values for the "switch" widget (=the list
             of possible contexts for the user);
           - "present" is a boolean value indicating if the current
             authentication context is in this list.
        '''
        # Get the available contexts
        r = self.getContexts(tool) or []
        # Add "no context" switch option when relevant
        if not self.isMandatory(tool):
            no = ('', tool.translate('everything'))
            if self.noContextPosition == 'end':
                r.append(no)
            else: # "start"
                r.insert(0, no)
        # Is the current authentication context in this list ?
        ctx = tool.request.authContext or ''
        present = False
        for id, name in r:
            if id == ctx:
                present = True
                break
        return r, present

    def _maySwitchTo(self, tool, option):
        '''Is p_option a valid option to switch to ?'''
        options, present = self._getSwitchOptions(tool)
        if not options: return
        for id, title in options:
            if id == option: return True

    def _check(self, tool):
        '''Returns True if there is no problem with the current configuration
           related to the authentication context.'''
        # Check that the current context is among the valid switch options
        options, present = self._getSwitchOptions(tool)
        return present

    def _setOnRequest(self, tool, req, ctx):
        '''Set, on the p_req(uest) object, authentication-related attributes'''
        # The authentication context in itself (a short identifier)
        req.authContext = ctx
        # Its human-readable name
        req.authContextName = self.getName(tool, ctx)
        # The corresponding object, if any
        req.authObject = self.getObject(tool, ctx)

    def isMandatory(self, tool):
        '''When authentication contexts are activated, is the user forced to
           choose one ?'''
        return True

    def switchContext(self, tool):
        '''Is the user allowed to switch context once logged ?'''
        return True

    def getContexts(self, tool):
        '''Returns the application-specific authentication contexts, as a list
           of tuples (s_context, s_name). s_context is a short string that
           identifies the context, while s_name is a human-readable name that
           will be shown in the UI.'''

    def _setDefault(self, req, tool):
        '''Set a default context when relevant'''
        if self.chooseOnLogin: return
        # If the context was not chosen at login time, but there is a default
        # context, select it.
        default = self.getDefaultContext(tool)
        if default:
            # Update the cookie with this context
            gutils.updateCookie(req, default, onResponse=True)
            # Update authentication context attributes set on the request
            self._setOnRequest(tool, req, default)

    # This method does not need to be overridden if there is no default context
    def getDefaultContext(self, tool):
        '''Returns the default context among contexts as returned by
           m_getContexts.'''

    # This method must not be overridden
    def getName(self, tool, context):
        '''Returns the name of some given p_context'''
        for ctx, name in self.getContexts(tool):
            if ctx == context:
                return name

    def getObject(self, tool, context):
        '''If an authentication context corresponds to an object, this method
           must be overridden to return the object corresponding to the given
           p_context. Then, the object is available as attribute "authObject"
           on the request.'''
        # Overriding this method optimizes performance. Indeed, your object is
        # "loaded" once per request and is available in request.authObject: you
        # don't need to call tool.geObject(context) every time you need to get
        # it.
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
