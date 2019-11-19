# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from DateTime import DateTime

# Errors - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
NON_SSO_USER = 'Non-SSO user "%s" prevents access to the SSO user having the ' \
  'same login.'
INVALID_ROLE = 'Role "%s" mentioned in a HTTP header is not among ' \
  'grantable roles.'
INVALID_GROUP = 'Group "%s" mentioned in a HTTP header was not found.'
SSO_REACTIVATED = '%s reactivated after a new visit via the SSO reverse proxy.'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Config:
    '''When a Appy server is placed behind a reverse proxy performing
       single sign-on (SSO), use this class to tell Appy how and where to
       retrieve, within every HTTP request from the reverse proxy, information
       about the currently logged user: login, groups and roles.'''
    ssoAttributes = {'loginKey': None, 'emailKey':'email', 'nameKey': 'name',
                     'firstNameKey': 'firstName', 'fullNameKey': 'title'}
    otherPrerogative = {'role': 'group', 'group': 'role'}
    # The connection to a SSO server can't really be tested
    testable = False

    def __init__(self):
        # One can give a name to the SSO reverse proxy that will call us
        self.name = ''
        # The HTTP header key that contains the user login
        self.loginKey = ''
        # Keys storing first and last names
        self.firstNameKey = ''
        self.nameKey = ''
        self.fullNameKey = ''
        # Key storing the user email
        self.emailKey = ''
        # If header values are encoded in a specific way, one can provide a
        # function allowing to decode them.
        self.decodeFunction = None
        # Is SSO enabled ?
        self.enabled = True
        # Keys storing user's global roles. If no key is provided, we suppose
        # that roles are not provided by the SSO server and will be managed
        # locally by the Appy app.
        self.roleKey = ''
        # Among (rolesKey, value) HTTP headers, all may not be of interest,
        # for 2 reasons:
        # 1. the "roleKey" may be the same as the "groupKey" (see below);
        # 2. the reverse proxy may send us all roles the currently logged user
        #    has; all those roles may not concern our application.
        # This is why you can define, in "roleRex", a regular expression. The
        # header value will be ignored if this regular expression produces no
        # match. In the case there is a match, note that, if "roleRex" does not
        # have any matching group, the role name will be the complete HTTP
        # header value. Else, the role name will be the first matching group.
        self.roleRex = None
        # For more complex cases, you can define a "roleFunction": a custom
        # fonction that will receive the match object produced by "roleRex" and
        # must return the role name. Funny additional subtlety: if this
        # function returns a tuple (name, None) instead, "name" will be
        # considered a group login, not a role name. This is useful for reverse
        # proxies that send us similar keys for groups and roles.
        self.roleFunction = None
        # Once a role has been identified among HTTP headers via "roleKey" and
        # "roleRex", and has possibly been treated by "roleFunction", its name
        # can be different from the one used in the Appy application. A role
        # mapping can thus be defined.
        self.roleMapping = {}
        # Key storing user's groups. If no key is provided, we suppose
        # that groups are not provided by the SSO server and will be managed
        # locally by the Appy app.
        self.groupKey = ''
        # Regular expression applied to the group value (similar to "roleRex")
        self.groupRex = None
        # If a "group function" is specified, it will receive the match object
        # produced by "groupRex" and must return the group name, or
        # (name, None), similarly to "roleFunction" (in this case, it means
        # that a role name is returned instead of a group login).
        self.groupFunction = None
        # Group mapping (similar to role mapping). Here, we map group logins.
        self.groupMapping = {}
        # If you specify a function in the following attribute, it will be
        # called after a user has been linked to a group. The function receives,
        # as args, the user and the group.
        self.afterLinkGroup = None
        # For SSO-authenticated users, a specific single-logout URL may be used
        # instead of the classic Appy logout URL.
        self.logoutUrl = None
        # The "synchronization interval" is an integer value representing a
        # number of minutes. Every time a SSO user performs a request on your
        # app, we will not automatically update the corresponding local User
        # instance from HTTP headers' info. We will only do it if this number of
        # minutes has elapsed since the last time we've done it.
        self.syncInterval = 10
        # "encoding" determines the encoding of the header values. Normally, it
        # is defined in header key CONTENT_TYPE. You can force another value
        # here.
        self.encoding = None
        # If the reverse proxy adds some prefix to app URLs, specify it here.
        # For example, if the app is locally available at localhost:8080/ and
        # is publicly available via www.proxyserver.com/myApp, specify "myApp"
        # as URL prefix.
        self.urlPrefix = None
        # In some cases, Appy must know the complete URL allowing to access the
        # app via the reverse proxy. No trailing slash please.
        self.appUrl = None
        # Prior to being deployed behind a SSO server, the Appy app may have
        # managed its users locally. If attribute "convertLocalUsers" is False
        # (the default), when a SSO user having the same login as a local user
        # arrives, Appy will not log him in because a local user exists with
        # this login. If it is set to True, the local user will be automatically
        # converted to a SSO user (excepted if it is a special user: anon,
        # admin,...).
        self.convertLocalUsers = False
        # If you place a function in the following attribute "userOnEdit", it
        # will be called everytime the local copy of a SSO user will be created
        # or updated. Such a local copy is created when a SSO hits the app for
        # the first time; it is then updated on a regular basis, depending on
        # "synInterval" (see above). "userOnEdit" will be called with 2 args:
        # the User instance and boolean "created", True if the user has just
        # been created or False if it is an update.
        self.userOnEdit = None

    def init(self, tool): pass

    def __repr__(self):
        name = self.name or 'SSO reverse proxy'
        return '%s with login key=%s' % (name, self.loginKey)

    def extractEncoding(self, headers):
        '''What is the encoding of retrieved page?'''
        # Encoding can have a forced value
        if self.encoding: return self.encoding
        if 'CONTENT_TYPE' in headers:
            res = None
            for elem in headers['CONTENT_TYPE'].split(';'):
                elem = elem.strip()
                if elem.startswith('charset='): return elem[8:].strip()
        # This is the default encoding according to HTTP 1.1
        return 'iso-8859-1'

    def getUserParams(self, req):
        '''Formats the user-related data from the request (HTTP headers), as a
           dict of params usable for creating or updating the corresponding
           Appy user.'''
        res = {}
        headers = req._orig_env
        encoding = self.extractEncoding(headers)
        decodeFunction = self.decodeFunction
        for keyAttr, appyName in self.ssoAttributes.iteritems():
            if not appyName: continue
            # Get the name of the HTTP header corresponding to "keyAttr"
            keyName = getattr(self, keyAttr)
            if not keyName: continue
            # Get the value for this header if found in the request
            value = headers.get('HTTP_%s' % keyName, None)
            if value:
                # Apply standard character decoding
                value = value.decode(encoding)
                # Apply specific decoding if any
                if decodeFunction: value = decodeFunction(value)
                res[appyName] = value.encode('utf-8')
        return res

    def extractUserLogin(self, guard):
        '''Identify the user from HTTP headers'''
        # Check if SSO is enabled
        if not self.enabled: return
        # If the user we identify exists but as a user from another
        # authentication source:
        # - if it is a local user and self.convertLocalUsers is True, we
        #   convert it to a SSO user;
        # - else, we have a problem: we log a warning and force an
        #   identification failure.
        login = headers and headers.get('HTTP_%s' % self.loginKey, None)
        if login:
            user = tool.search1('User', noSecurity=True, login=login)
            if user and (user.source != 'sso'):
                # Convert it when relevant
                if self.convertLocalUsers:
                    user.convertTo('sso')
                else:
                    # Force an identification failure
                    if warn:
                        tool.log(NON_SSO_USER % login, type='warning',
                                 noUser=True)
                    return
        return login

    def convertUserPrerogatives(self, type, prerogatives, encoding='utf-8'):
        '''Converts SSO p_prerogatives to Appy roles and groups'''
        # p_prerogatives may contain "main" and "secondary" prerogatives.
        # Indeed, when extracting roles we may find groups, and vice versa.
        res = set()
        secondary = set()
        # A comma-separated list of prerogatives may be present
        for value in prerogatives:
            # Ignore empty values
            value = value.strip()
            if not value: continue
            # Get a standardized utf-8-encoded string
            value = value.decode(encoding).encode('utf-8')
            # Apply a regular expression if specified
            rex = getattr(self, '%sRex' % type)
            if rex:
                match = rex.match(value)
                if not match: continue
                # Apply a function if specified
                fun = getattr(self, '%sFunction' % type)
                if fun:
                    value = fun(self, match)
                    if isinstance(value, tuple):
                        # "value" is from the secondary prerogative type
                        value = value[0]
                        # Apply the secondary prerogative mapping if any
                        other = self.otherPrerogative[type]
                        mapping = getattr(self, '%sMapping' % other)
                        if value in mapping:
                            value = mapping[value]
                        secondary.add(value)
                        continue
                else:
                    value = match.group(1)
            # Apply a mapping if specified
            mapping = getattr(self, '%sMapping' % type)
            if value in mapping:
                value = mapping[value]
            # Add the prerogative to the result
            res.add(value)
        return res, secondary
        
    def extractUserPrerogatives(self, type, req):
        '''Extracts, from p_req, user groups or roles, depending on p_type'''
        # Do we care about getting this type or prerogative ?
        key = getattr(self, '%sKey' % type)
        if not key: return None, None
        # Get HTTP headers
        headers = getattr(req, '_orig_env', None)
        if not headers: return None, None
        # Get the HTTP request encoding
        encoding = self.extractEncoding(headers)
        # Extract the value for the "key" header
        headerValue = headers.get('HTTP_%s' % key, None)
        if not headerValue: return None, None
        # We have prerogatives. Convert them to Appy roles and groups.
        return self.convertUserPrerogatives(type, headerValue.split(','),
                                            encoding=encoding)

    def setRoles(self, tool, user, roles):
        '''Grants p_roles to p_user. Ensure those role are grantable.'''
        grantable = tool.o.getProductConfig().grantableRoles
        for role in roles:
            if role in grantable:
                user.addRole(role)
            else:
                tool.log(INVALID_ROLE % role, type='warning', noUser=True)

    def setGroups(self, tool, user, groups):
        '''Puts p_user into p_groups. Ensure those p_groups exist.'''
        for login in groups:
            if login.startswith('*'):
                # "login" is a pattern of groups. Query all groups and link the
                # user to those matching the pattern.
                suffix = login[1:]
                for group in tool.search('Group', noSecurity=True):
                    if group.login.endswith(suffix):
                        group.link('users', user)
                        if self.afterLinkGroup:
                            self.afterLinkGroup(user, group)
            else:
                # "login" is the login of a single group
                group = tool.search1('Group', noSecurity=True, login=login)
                if group:
                    group.link('users', user)
                    if self.afterLinkGroup:
                        self.afterLinkGroup(user, group)
                else:
                    tool.log(INVALID_GROUP % login, type='warning', noUser=True)

    def extractUserInfo(self, source, isRequest=True):
        '''By default, this method extracts, from HTTP headers present in the
           request (p_source), user data (name, login...), roles and groups.

           If p_isRequest is False, p_source is an already extracted list of
           prerogatives.'''
        if isRequest:
            req = source
            # Extract simple user attributes
            params = self.getUserParams(req)
            # Extract user global roles and groups
            roles, groups2 = self.extractUserPrerogatives('role', req)
            groups, roles2 = self.extractUserPrerogatives('group', req)
        else:
            params = None
            roles, groups2 = self.convertUserPrerogatives('role', source)
            groups, roles2 = self.convertUserPrerogatives('group', source)
        # Merge found roles
        if roles or roles2:
            if roles and roles2:
                roles = roles.union(roles2)
            elif roles2:
                roles = roles2
        # Merge found groups
        if groups or groups2:
            if groups and groups2:
                groups = groups.union(groups2)
            elif groups2:
                groups = groups2
        return params, roles, groups

    def updateUser(self, tool, req, user):
        '''Updates the local p_user with data from request headers'''
        # The last sync date for this user is now
        user.syncDate = DateTime()
        # Update basic user attributes and recompute the user title
        params, roles, groups = self.extractUserInfo(req)
        for name, value in params.iteritems(): setattr(user, name, value)
        user.updateTitle()
        # Update global roles (when roles are provided by the SSO server)
        if self.roleKey:
            existing = user.roles
            # Remove roles not granted anymore
            for role in existing:
                if not roles or (role not in roles): user.delRole(role)
            # Add roles not already granted
            if roles:
                for role in roles:
                    if role not in existing: user.addRole(role)
        # Update groups (when groups are provided by the SSO server). Unlink any
        # existing group and re-link extracted groups.
        if self.groupKey:
            user.groups = None
            self.setGroups(tool, user, groups)
        # Reactivate the user if the local copy was noted as deactivated. We
        # trust SSO.
        if user.state == 'inactive':
            msg = SSO_REACTIVATED % user.login
            user.log(msg, noUser=True)
            user.do('reactivate', noSecurity=True, doHistory=False, comment=msg)

    def createUser(self, tool, login, source, isRequest=True, userParams=None):
        '''Creates the local User copy of a SSO user, from user info as present
           in the request (p_source, if p_isRequest is True), or via an already
           extracted list of prerogatives (p_source) if p_isRequest is False. In
           this latter case, p_userParams is a dict containing user parameters
           (login, name, first name, etc).'''
        # Extract info about the user to create
        params, roles, groups = self.extractUserInfo(source, isRequest)
        if userParams:
            if params: userParams.update(params)
            params = userParams
        user = tool.create('users', noSecurity=True, login=login,
                           source='sso', **params)
        # The last sync date for this user is now
        user.syncDate = DateTime()
        # Set user global roles and groups (if in use)
        if self.roleKey: self.setRoles(tool, user, roles)
        if self.groupKey: self.setGroups(tool, user, groups)
        # Custom User initialization
        if self.userOnEdit: self.userOnEdit(user, created=True)
        if isRequest:
            tool.log('SSO user "%s" (%s) created (1st visit here).' % \
                     (login, user.title), noUser=True)
        return user

    def getUser(self, tool, login, createIfNotFound=True):
        '''Returns a local User instance corresponding to a SSO user'''
        # Check if SSO is enabled
        if not self.enabled: return
        # Do we already have a local User instance for this user ?
        req = tool.request
        user = tool.search1('User', noSecurity=True, login=login)
        if user:
            # Update the user only if we have not done it since "syncInterval"
            # minutes. The user may not have "syncDate" initialized yet.
            mustUpdate = False
            syncDate = user.syncDate
            if not syncDate:
                mustUpdate = True
            else:
                interval = (DateTime() - syncDate) * 1440
                mustUpdate = interval > self.syncInterval
            if mustUpdate:
                self.updateUser(tool, req, user) # Update it from HTTP headers
                # Custom User update
                if self.userOnEdit: self.userOnEdit(user, created=False)
        elif createIfNotFound:
            # Create a local User instance representing the SSO-authenticated
            # user. Collect roles and groups this user has.
            user = self.createUser(tool, login, req)
        return user

    def patchUrl(self, url):
        '''If self.urlPrefix is not empty, check its presence in p_url and
           remove it if found.'''
        if not self.enabled or not self.urlPrefix: return url
        part = '/%s/' % self.urlPrefix
        return url.replace(part, '/', 1)
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
