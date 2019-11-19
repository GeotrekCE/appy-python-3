# ~license~
# ------------------------------------------------------------------------------
import string
try:
    import ldap
except ImportError:
    # For people that do not care about ldap
    ldap = None
from appy.utils import sequenceTypes

# ------------------------------------------------------------------------------
class Config:
    '''Parameters for authenticating users to an LDAP server. This class is
       used by Appy apps. For a pure, appy-independent LDAP connector,
       see the class LdapConnector below.'''
    ldapAttributes = { 'loginAttribute': None, 'emailAttribute': 'email',
                       'fullNameAttribute': 'title',
                       'firstNameAttribute': 'firstName',
                       'lastNameAttribute': 'name' }
    # This config can be tested by trying to connect to the defined LDAP server
    # with the given "admin" credentials.
    testable = True

    def __init__(self):
        self.server = '' # Name of the LDAP server
        self.port = None # Port for this server
        self.protocol = 'ldap' # or ldaps
        # Login and password of the technical power user that the Appy
        # application will use to connect to the LDAP. Sometimes the full user
        # DN must be given.
        self.adminLogin = ''
        self.adminPassword = ''
        # LDAP attribute to use as login for authenticating users. Can also be:
        # "mail", "sAMAccountName", "cn", "nid", "uid"...
        self.loginAttribute = 'dn'
        # When a login is transmitted to the LDAP server, a transform can be
        # applied: upper, lower or capitalize.
        self.loginTransform = 'lower'
        # LDAP attributes for storing email
        self.emailAttribute = None
        # LDAP attribute for storing full name (first + last name)
        self.fullNameAttribute = None
        # Alternately, LDAP attributes for storing 1st & last names separately
        self.firstNameAttribute = None
        self.lastNameAttribute = None
        # Beyond the hereabove-defined attributes, you can specify here a
        # dict mapping additional LDAP attributes to attributes of the Appy User
        # class or its app-specific sub-class.
        self.customAttributes = {}
        # LDAP classes defining the users stored in the LDAP
        self.userClasses = ('top', 'person')
        # Based on "userClasses" above, a filter will be created to query users.
        # If you want to specify a more precise filter, specify it here. The
        # complete filter will be a logical AND between the base filter created
        # from "userClasses" and "userFilter". For example, to retrieve only
        # users having an email and those not being of a given class, you could
        # write something like:
        #         ldap.userFilter='(mail=*)(!(objectClass=Computer))'
        # (of course, the precise expression depends on the attributes and
        #  values as defined in your LDAP).
        self.userFilter = ''
        # Base DN where to find users in the LDAP. Several base DNs can be
        # specified, in a list or tuple.
        self.baseDn = ''
        self.scope = 'SUBTREE' # Scope of the search within self.baseDn
        # Is this server connection enabled ?
        self.enabled = True
        # The "user map" allows to put LDAP users into groups or assign them
        # roles. This dict will be used every time a local User will be created.
        # It can be while synchronizing all users (see m_synchronizeUsers
        # below) or when the user logs in for the first time (see m_getUser
        # below). This dict will NOT be used subsequently, when updating the
        # User instance. Every key must be a user login. Every value is an
        # appy.Object instance having the optional attributes:
        # "groups": a list of group IDs (logins);
        # "roles":  a list of global role names.
        self.userMap = {}
        # If the following attribute is True, when successfully authenticating a
        # user from this LDAP, if the corresponding User instance is a local
        # one, it will be converted to a distant copy, excepted if it is a
        # special user.
        self.convertLocalUsers = True

    def init(self, tool):
        '''Lazy initialization'''
        # Standardize attributes
        if not isinstance(self.baseDn, sequenceTypes):
            self.baseDn = [self.baseDn]

    def test(self, tool):
        '''Connects to the LDAP server to check the connection'''
        connector = LdapConnector(self.getServerUri(), tool=tool)
        success, msg = connector.connect(self.adminLogin, self.adminPassword)
        return success and 'OK' or 'KO'

    def __repr__(self):
        '''Short string representation of this ldap config, for logging and
           debugging purposes.'''
        return self.getServerUri()

    def getServerUri(self):
        '''Returns the complete URI for accessing the LDAP, ie
           "ldap[s]://some.ldap.server:389".'''
        port = self.port or 389
        return '%s://%s:%d' % (self.protocol, self.server, port)

    def getUserFilterValues(self, login=None):
        '''Gets the filter values required to perform a query for finding user
           corresponding to p_login in the LDAP, or all users if p_login is
           None.'''
        res = login and [(self.loginAttribute, login)] or []
        for userClass in self.userClasses:
            res.append( ('objectClass', userClass) )
        return res

    def getUserAttributes(self):
        '''Gets the attributes we want to get from the LDAP for characterizing
           a user.'''
        res = []
        for name in self.ldapAttributes.iterkeys():
            attrName = getattr(self, name)
            if attrName: res.append(attrName)
        # Add custom attributes
        for name in self.customAttributes.iterkeys():
            if name not in res: res.append(name)
        return res

    def setAppyValue(self, ldapName, ldapData, appyName, appyData):
        '''Convert LDAP value found at key p_ldapName in p_ldapData to an
           Appy-compliant value and store it, if found, in p_appyData at key
           p_appyName.'''
        value = ldapData.get(ldapName)
        if not value: return
        # Convert the value when relevant
        if isinstance(value, list): value = value[0]
        appyData[appyName] = value

    def getUserParams(self, ldapData):
        '''Formats the user-related p_ldapData retrieved from the LDAP, as a
           dict of params usable for creating or updating the corresponding
           Appy user.'''
        res = {}
        # Retrieve base params
        for name, appyName in self.ldapAttributes.iteritems():
            if not appyName: continue
            # Get the name of the attribute as known in the LDAP
            ldapName = getattr(self, name)
            if not ldapName: continue
            self.setAppyValue(ldapName, ldapData, appyName, res)
        # Retrieve custom params
        for ldapName, appyName in self.customAttributes.iteritems():
            if ldapData.has_key(ldapName):
                self.setAppyValue(ldapName, ldapData, appyName, res)
        return res

    def setLocalUser(self, tool, attrs, login, password=None):
        '''Creates or updates the local User instance corresponding to a LDAP
           user from the LDAP, having p_login. Its other attributes are in
           p_attrs and, when relevant, its password is in p_password. This
           method r_eturns a 2-tuple containing:
           * the local User instance;
           * the status of the operation:
             - "created" if the instance has been created,
             - "updated" if at least one data from p_attrs is different from the
               one stored on the existing User instance;
             - None else.
        '''
        # Do we already have a local User instance for this user ?
        status = None
        user = tool.search1('User', noSecurity=True, login=login)
        if user: # yes
            # Do not update it if the user is special
            if user.isSpecial(): return None, None
            # If the user is local, don't touch it or convert it to LDAP
            if user.source == 'zodb':
                if self.convertLocalUsers:
                    # Convert it to a LDAP user
                    user.convertTo('ldap')
                else:
                    return None, None
            # Update it with info about him from the LDAP
            for name, value in attrs.iteritems():
                currentValue = getattr(user, name)
                if value != currentValue:
                    setattr(user, name, value)
                    status = 'updated'
            # Update user password, if given
            if password: user.setPassword(password, log=False)
            # Recompute the title, computed from other fields
            user.updateTitle()
            user.reindex()
        else:
            # Create the user
            user = tool.create('users', noSecurity=True, login=login,
                               source='ldap', **attrs)
            if password: user.setPassword(password, log=False)
            status = 'created'
            # Put him into groups and/or grant him some roles according to
            # self.userMap.
            if login in self.userMap:
                privileges = self.userMap[login]
                # Put the user in some groups
                groups = getattr(privileges, 'groups', None)
                if groups:
                    for groupLogin in groups:
                        group = tool.search1('Group', noSecurity=True,
                                             login=groupLogin)
                        group.link('users', user)
                # Grant him some roles
                roles = getattr(privileges, 'roles', None)
                if roles:
                    for role in roles: user.addRole(role)
                tool.log('%s: automatic privileges set.' % login)
        return user, status

    def applyLoginTransform(self, login):
        '''Applies, when relevant, a transform to p_login'''
        if self.loginTransform:
            exec('r = login.%s()' % self.loginTransform)
        else:
            r = login
        return r

    def getUser(self, tool, login, password):
        '''Returns a local User instance corresponding to a LDAP user if p_login
           and p_password correspond to a valid LDAP user.'''
        # Check if LDAP is enabled
        if not self.enabled: return
        # Get a connector to the LDAP server and connect to the LDAP server
        serverUri = self.getServerUri()
        connector = LdapConnector(serverUri, tool=tool)
        success, msg = connector.connect(self.adminLogin, self.adminPassword)
        if not success: return
        # Apply a transform to p_login when required
        if login: login = self.applyLoginTransform(login)
        # Check if the user corresponding to p_login exists in the LDAP
        filter = connector.getFilter(self.getUserFilterValues(login),
                                     self.userFilter)
        params = self.getUserAttributes()
        data = None
        for baseDn in self.baseDn:
            data = connector.search(baseDn, self.scope, filter, params)
            if data: break
        if not data or not data[0][0]: return
        # The user exists. Try to connect to the LDAP with this user in order
        # to validate its password.
        userConnector = LdapConnector(serverUri, tool=tool)
        success, msg = userConnector.connect(data[0][0], password)
        if not success: return
        # The password is correct. We can create/update our local user
        # corresponding to this LDAP user.
        userParams = self.getUserParams(data[0][1])
        user, status = self.setLocalUser(tool, userParams, login, password)
        return user

    def synchronizeUsers(self, tool):
        '''Synchronizes the local User copies with this LDAP user base. Returns
           a 2-tuple containing the number of created, updated and untouched
           local copies.'''
        if not self.enabled: raise Exception('LDAP config not enabled.')
        # Get a connector to the LDAP server and connect to the LDAP server
        serverUri = self.getServerUri()
        tool.log('reading users from %s...' % serverUri)
        connector = LdapConnector(serverUri, tool=tool)
        success, msg = connector.connect(self.adminLogin, self.adminPassword)
        if not success: raise Exception('Could not connect to %s' % serverUri)
        # Query the LDAP for users. Perform several queries to avoid having
        # error ldap.SIZELIMIT_EXCEEDED.
        params = self.getUserAttributes()
        # Count the number of created, updated and untouched users
        created = updated = untouched = wrong = 0
        for letter in string.ascii_lowercase:
            # Get all the users whose login starts with "letter"
            filter = connector.getFilter(self.getUserFilterValues('%s*'%letter),
                                         self.userFilter)
            for baseDn in self.baseDn:
                data = connector.search(baseDn, self.scope, filter, params)
                if not data: continue
                for userData in data:
                    # Get the user login
                    try:
                        login = userData[1][self.loginAttribute][0]
                        login = self.applyLoginTransform(login)
                    except TypeError:
                        # The retrieved data structure is not valid
                        wrong += 1
                        continue
                    # Get the other user parameters, as Appy wants it
                    userParams = self.getUserParams(userData[1])
                    # Create or update the user
                    user, status = self.setLocalUser(tool, userParams, login)
                    if status == 'created': created += 1
                    elif status == 'updated': updated += 1
                    else: untouched += 1
        tool.log('users synchronization: %d local user(s) created, ' \
                 '%d updated, %d untouched and %d invalid entries.' % \
                 (created, updated, untouched, wrong))
        return created, updated, untouched, wrong

# ------------------------------------------------------------------------------
class LdapConnector:
    '''This class manages the communication with a LDAP server'''
    def __init__(self, serverUri, tentatives=5, ssl=False, timeout=5,
                 tool=None):
        # The URI of the LDAP server, ie ldap[s]://some.ldap.server:389.
        self.serverUri = serverUri
        # The object that will represent the LDAP server
        self.server = None
        # The number of trials the connector will at most perform to the LDAP
        # server, when executing a query in it.
        self.tentatives = tentatives
        self.ssl = ssl
        # The timeout for every query to the LDAP.
        self.timeout = timeout
        # A tool from a Appy application can be given and will be used, ie for
        # logging purpose.
        self.tool = tool

    def log(self, message, type='info'):
        '''Logs via a Appy tool if available'''
        if self.tool:
            self.tool.log(message, type=type)
        else:
            print(message)

    def connect(self, login, password):
        '''Connects to the LDAP server using p_login and p_password as
           credentials. If the connection succeeds, a server object is created
           in self.server and tuple (True, None) is returned. Else, tuple
           (False, errorMessage) is returned.'''
        try:
            self.server = ldap.initialize(self.serverUri)
            self.server.simple_bind_s(login, password)
            # Tentative code
            #self.server.protocol_version = 3
            #self.server.set_option(ldap.OPT_REFERRALS, 0)
            # Note that "simple_bind_s" can return a result
            return True, None
        except AttributeError as ae:
            # When the ldap module is not there, trying to catch ldap.LDAPError
            # will raise an error.
            message = str(ae)
            self.log('Ldap connect error with login %s (%s).' % \
                     (login, message))
            return False, message
        except ldap.LDAPError as le:
            message = str(le)
            self.log('%s: connect error with login %s (%s).' % \
                     (self.serverUri, login, message))
            return False, message

    def getFilter(self, values, customPart=''):
        '''Builds and returns a LDAP filter based on p_values, a tuple of
           (name, value) expressions logically AND-ed. If p_customPart is given,
           it represents and additional expression that will be AND-ed as
           well.'''
        return '(&%s%s)' % (''.join(['(%s=%s)' % (n, v) for n, v in values]),
                            customPart)

    def search(self, baseDn, scope, filter, attributes=None):
        '''Performs a query in the LDAP at node p_baseDn, with the given
           p_scope. p_filter is a LDAP filter that constraints the search. It
           can be computed from a list of tuples (value, name) by method
           m_getFilter. p_attributes is the list of attributes that we will
           retrieve from the LDAP. If None, all attributes will be retrieved.'''
        if self.ssl: self.server.start_tls_s()
        try:
            # Get the LDAP constant corresponding to p_scope
            scope = getattr(ldap, 'SCOPE_%s' % scope)
            # Perform the query
            for i in range(self.tentatives):
                try:
                    return self.server.search_st(\
                        baseDn, scope, filterstr=filter, attrlist=attributes,
                        timeout=self.timeout)
                except ldap.TIMEOUT:
                    pass
        except ldap.LDAPError as le:
            self.log('LDAP query error %s: %s' % \
                     (le.__class__.__name__, str(le)))
# ------------------------------------------------------------------------------
