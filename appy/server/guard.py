'''A guard is responsible for authenticating and authorizing app users, be they
   humans or other apps. A guard will ensure that any action is performed in the
   respect of security rules defined: workflows, permissions, etc.'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import base64, urllib.parse
from appy.px import Px
from appy.model.user import User
from appy.model.utils import Object as O

# Errors - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
INVALID_LOGIN_TRANSFORM = 'Invalid value "%s" for attribute "loginTransform".'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Cookie:
    '''Represents the Appy authentication cookie, carrying user credentials. It
       will be set and read by an Appy app for authenticating a user.'''
    # Name of the Appy authentication cookie
    name = 'AppyAuth'

    @classmethod
    def read(class_, handler, onResponse=False):
        '''Returns the tuple (login, password, ctx) read from the authentication
           cookie read from the request. If no user is logged, its returns
           (None, None, None).'''
        # If p_onResponse, we get the cookie that has already been set on the
        # response, instead of the one coming from the request.
        if not onResponse:
            cookie = handler.req[Cookie.name]
        else:
            cookie = handler.resp.headers['Cookies'][Cookie.name]
        if not cookie: return None, None, None
        unquoted = urllib.parse.unquote(cookie).encode('utf-8')
        cookieValue = base64.decodestring(unquoted).decode('utf-8')
        if ':' not in cookieValue: return None, None, None
        # Extract the context from the cookieValue
        r, context = cookieValue.rsplit(':', 1)
        # Extract login and password
        login, password = r.split(':', 1)
        return login, password, context

    @classmethod
    def write(class_, handler, login, password, ctx):
        '''Encode p_login, p_password and p_ctx into the authentication
           cookie.'''
        r = '%s:%s:%s' % (login, password, ctx or '')
        r = base64.encodestring(r.encode('utf-8')).rstrip()
        handler.resp.setCookie(Cookie.name, urllib.parse.quote(r))

    @classmethod
    def update(class_, handler, ctx, onResponse=False):
        '''Updates the authentication context within the Appy authentication
           cookie. If p_onResponse is True, we get the cookie from the response
           headers instead of the request object.'''
        login, password, oldCtx = Cookie.read(handler, onResponse=onResponse)
        Cookie.write(handler, login, password, ctx)

    @classmethod
    def updatePassword(class_, handler, password):
        '''Updates the cookie with a new p_password'''
        login, oldPassword, ctx = Cookie.read(handler)
        Cookie.write(handler, login, password, ctx)

    @classmethod
    def disable(class_, handler):
        '''Disables the authentication cookie'''
        # Do it only if the cookie exists
        if Cookie.name in handler.req:
            handler.resp.setCookie(Cookie.name, 'deleted')

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Config:
    '''Security configuration'''
    # Allowed value for field "loginTransform"
    transformValues = ('lower', 'upper', 'capitalize')

    def __init__(self):
        # Activate or not the button on home page for asking a new password
        self.activateForgotPassword = True
        # On user log on, you may want to ask them to choose their
        # "authentication context" in a list. Such a context may have any
        # semantics, is coded as a string and will be accessible on the Handler
        # object in attribute "authContext". In order to activate authentication
        # contexts, place here an instance of a sub-class of class
        # appy.server.context.AuthenticationContext. Consult this class'
        # docstring for more information.
        self.authContext = None
        # When a login is encoded by the user, a transform can be applied (one
        # among Config.transformValues).
        self.loginTransform = None
        # When using a LDAP for authenticating users, place an instance of class
        # appy.utils.ldap.Config in the field below.
        self.ldap = None
        # When using, in front of an Appy server, a reverse proxy for
        # authentication for achieving single-sign-on (SSO), place an instance
        # of appy.server.sso.Config in the field below.
        self.sso = None

    def check(self):
        '''Check this config'''
        # Check attribute "loginTransform"
        transform = self.loginTransform
        if transform and (transform not in self.transformValues):
            raise Exception(INVALID_LOGIN_TRANSFORM % transform)
        return True

    def transformLogin(self, login):
        '''Return p_login as potentially transformed via
           p_self.loginTransform.'''
        return getattr(login, self.loginTransform)() \
               if self.loginTransform else login

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Unauthorized(Exception):
    '''Error that is raised when a security problem is encountered'''

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Guard:
    '''Implements security-related functionality'''
    Error = Unauthorized
    Cookie = Cookie
    traverse = {}

    def __init__(self, handler):
        # The handler that has instantiated this guard
        self.handler = handler
        # Unwrap some useful objects
        self.model = handler.server.model
        self.config = handler.server.config
        # Authenticate the currently logged user and get its User instance
        self.user = User.authenticate(self)
        # Info about the currently selected authentication context
        self.authContext = None
        # Cache info about this user
        self.cache()

    def cache(self):
        '''Pre-compute, for performance, heavily requested information about the
           currently logged user.'''
        u = self.user
        self.userLogin = u.login
        self.userLogins = u.getLogins(compute=True, guard=self)
        self.userRoles = u.getRoles(compute=True, guard=self)
        self.userAllowed = u.getAllowedValue(self.userRoles, self.userLogins)
        self.userLanguage = u.getLanguage() if not self.handler.fake else 'en'

    # In the remaining of this class, when talking about "the user", we mean
    # "the currently logged user".

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Security checks on classes
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def mayInstantiate(self, class_, checkInitiator=True, initiator=None,
                       raiseOnError=False):
        '''May the user create instances of p_class_ ?'''
        # This information can be defined on p_class_.python, in static
        # attribute "creators". If this attribute holds...
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # a list    | we consider it to be a list of roles, and we check that
        #           | the user has at least one of those roles;
        # a boolean | we consider that the user can create instances of this
        #           | class if the boolean is True;
        # a method  | we execute the method, and via its result, we fall again
        #           | in one of the above cases.
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # If p_class_.python does not define such an attribute, a default list
        # of roles defined in the config will be used.
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # An initiator object may dictate his own rules for instance creation
        if checkInitiator:
            # No need to check for an initiator in the context of a root class
            init = initiator or self.user.getInitiator()
            if init and getattr(init.field, 'creators', None):
                return self.user.hasRole(init.field.creators, init.o)
        # Get the Python class defined in the app
        class_ = class_.python
        # Get attribute "creators" on the class, or use the config
        creators = class_.creators if hasattr(class_, 'creators') \
                   else self.config.model.defaultCreators
        # If "creators" is a method, execute it
        if callable(creators): creators = creators(class_)
        # Manage the "boolean" case
        if isinstance(creators, bool) or not creators: return creators
        # Manage the "roles" case
        for role in self.userRoles:
            if role in creators:
                return True

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Security checks on objects
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    def allows(self, o, permission='read', raiseError=False):
        '''Has the user p_permission on p_o ?'''
        r = self.user.hasPermission(permission, o)
        if not r and raiseError: raise Unauthorized()
        return r

    def mayAct(self, o):
        '''m_mayAct allows to hide the whole set of actions for an p_o(bject).
           Indeed, beyond workflow security, it can be useful to hide controls
           like "edit" icons/buttons. For example, if a user may only edit some
           Ref fields with add=True on an object, when clicking on "edit", he
           will see an empty edit form.'''
        if hasattr(o, 'mayAct'): return o.mayAct()
        return True

    def mayDelete(self, o):
        '''May the currently logged user delete this p_o(bject) ?'''
        r = self.allows(o, 'delete')
        if not r: return
        # An additional, user-defined condition, may refine the base permission
        if hasattr(o, 'mayDelete'): return o.mayDelete()
        return True

    def mayEdit(self, o, permission='write', permOnly='specific',
                raiseError=False):
        '''May the user edit this object ? p_permission can be a field-specific
           permission. If p_permOnly is True, the additional user-defined
           condition (custom m_mayEdit) is not evaluated. If p_permOnly is
           "specific", this condition is evaluated only if the permission is
           specific (=not "write") If p_raiseError is True, if the user may not
           edit p_o, an error is raised.'''
        r = self.allows(o, permission, raiseError=raiseError)
        if not r: return
        if (permOnly == True) or \
           ((permOnly == 'specific') and (permission != 'write')): return r
        # An additional, user-defined condition, may refine the base permission
        if hasattr(o, 'mayEdit'):
            r = o.mayEdit()
            if not r and raiseError: o.raiseUnauthorized()
            return r
        return True

    def mayView(self, o, permission='read', raiseError=False):
        '''May the user view this p_o(bject) ? p_permission can be a field-
           specific permission. If p_raiseError is True, if the user may not
           view p_o, an error is raised.'''
        r = self.allows(o, permission, raiseError=raiseError)
        if not r: return
        # An additional, user-defined condition, may refine the base permission
        if hasattr(o, 'mayView'):
            r = o.mayView()
            if not r and raiseError: self.raiseUnauthorized()
            return r
        return True

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Login / logout
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    traverse['enter'] = True
    def enter(self):
        '''Perform login'''
        user = self.user
        if user.isAnon():
            # Authentication failed
            label = 'login_ko'
            success = False
            msg = 'Authentication failed with login %s.' % \
                  (self.handler.req.login or '')
        else:
            # Authentication succeeded
            label = 'login_ok'
            success = True
            msg = 'Logged in.'
        # Log the action
        self.handler.log('app', 'info', msg)
        # Redirect the user to the appropriate page
        if success:
            if user.changePasswordAtNextLogin:
                # Redirect to the page where the user can change its password
                back = '%s/edit?page=password' % user.url
                label = 'login_ok_change_password'
            else:
                # Redirect to the app's home page
                back = user.tool.computeHomePage()
                info = self.handler.req.authInfo
                # Carry custom authentication data when appropriate
                if info: back = '%s?authInfo=%s' % (back, info)
        else:
            # Stay on the same page
            back = self.handler.headers['Referer']
        # Redirect the user to the appropriate page
        self.handler.resp.goto(back, message=user.translate(label))

    traverse['leave'] = True
    def leave(self):
        '''Perform logout'''
        handler = self.handler
        # Disable the authentication cookie
        Cookie.disable(handler)
        # Log the action
        handler.log('app', 'info', 'Logged out.')
        # Redirect the user to the app's home page
        tool = handler.tool
        back = '%s/public' % tool.url if self.config.ui.discreetLogin \
                                      else self.config.server.getUrl()
        handler.resp.goto(back, message=tool.translate('logout_ok'))

    def getLogoutUrl(self, tool, user):
        '''The "logout" URL may not be the standard Appy one if the app is
           behind a SSO reverse proxy.'''
        if user.source == 'sso': return self.config.security.sso.logoutUrl
        return '%s/guard/leave' % tool.url

    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # PXs
    #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    # The login form
    pxLogin = Px('''
     <!-- Popup for reinitializing the password -->
     <div if="isAnon and config.security.activateForgotPassword"
          id="askPasswordReinitPopup" class="popup">
      <form id="askPasswordReinitForm" method="post"
            action=":'%s/askPasswordReinit' % tool.url">
       <div align="center">
        <p>:_('app_login')</p>
        <input type="text" size="35" name="rlogin" id="rlogin" value=""/>
        <br/><br/>
        <input type="button" onclick="doAskPasswordReinit()"
               value=":_('ask_password_reinit')"/>
        <input type="button" onclick="closePopup('askPasswordReinitPopup')"
               value=":_('object_cancel')"/>
       </div>
      </form>
     </div>

     <!-- The login box -->
     <div class="loginBox"
          var="cfg=config.security;
               discreet=config.ui.discreetLogin"
          style=":'display:%s' % (discreet and 'none' or 'block')">

      <!-- Allow to hide the box when relevant -->
      <img if="discreet" src=":url('close')" style="float:right"
           onclick="toggleLoginBox(false)" class="clickable"/>

      <h1>:_('app_name')</h1>
      <form id="loginForm" name="loginForm" method="post" class="login"
            action=":'%s/guard/enter' % tool.url">

       <!-- Login fields  -->
       <div><input type="text" name="login" id="login" value=""
                   placeholder=":_('app_login')" class="loginField"/></div>
       <div><input type="password" name="password" id="password"
                   placeholder=":_('app_password')" class="loginField"/></div>

       <!-- The authentication context -->
       <x var="ctx=cfg.authContext"
          if="ctx and ctx.chooseOnLogin">:ctx.pxOnLogin</x>

       <!-- Additional authentification data to carry -->
       <input type="hidden" name="authInfo" id="authInfo"
              value=":req.authInfo or ''"/>
       <!-- Must we go to some page after login ? -->
       <input type="hidden" name="goto" value=":req.get('goto', '')"/>

       <!-- The "submit" button -->
       <div><input type="submit" name="submit" var="label=_('app_connect')"
                   value=":label" alt=":label" style="margin: 12px 0 5px 0"/>
       </div>

       <!-- Forgot password ? -->
       <div class="lostPassword" if="cfg.activateForgotPassword">
         <a class="clickable"
         onclick="openPopup('askPasswordReinitPopup')">:_('forgot_password')</a>
       </div>
      </form>
     </div>''',

     js='''
       // Function triggered when the user asks password reinitialisation
       function doAskPasswordReinit() {
         // Check that the user has typed a login
         var f = document.getElementById('askPasswordReinitForm'),
             login = f.rlogin.value.replace(' ', '');
         if (!login) { f.rlogin.style.background = wrongTextInput; }
         else {
           closePopup('askPasswordReinitPopup');
           f.submit();
         }
       }''',

     css='''
      .loginBox {
         border: 2px solid #9fa8c1; padding: 35px; color: #335256;
         background-color:white; width: 260px; height: 280px;
         position: absolute; top: 50%; left: 50%; z-index: 10;
         transform: translate(-50%,-50%); -ms-transform: translate(-50%,-50%);
         box-shadow: 0 4px 8px 0 rgba(160, 104, 132, 0.2),
                     0 6px 20px 0 rgba(0, 0, 0, 0.19)
      }
      .loginBox a, .loginBox a,:visited {
         font-weight: bold; letter-spacing: 1px }
      .loginField { background-color: #6b7b9c !important;
         width: 220px !important; padding: 12px !important;
         margin: 6px 0  !important}
      .lostPassword { padding: 10px 0 }
      /* Placeholder color for the login form */
      .loginBox ::-webkit-input-placeholder {
        color: white; font-weight: bold }
      .loginBox ::-moz-placeholder {
        color: white; font-weight: bold; font-size:120% }
      .loginBox :-ms-input-placeholder {
      color: white; font-weight: bold; font-size: 120% }
     ''')
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
