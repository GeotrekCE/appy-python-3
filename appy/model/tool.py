# ~license~

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import re, urllib.parse

import appy.ui
from appy.all import *
from appy.tr import po
from appy.px import Px
from appy import Config
from appy.model.base import Base
from appy.model.user import User
from appy.data import nativeNames
from appy.utils.dates import Date
from appy.model.group import Group
from appy.ui.template import Template
from appy.model.searches import Search
from appy.model.fields import Initiator
from appy.model.page import Page as OPage
from appy.database.catalog import Catalog
from appy.model.translation import Translation

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Tool(Base):
    '''Base class for the Appy tool, a persistent instance storing configuration
       elements and more, like users, group and translations.'''

    # Make some modules and classes available and/or traversable via the tool- -
    ui = appy.ui
    Date = Date
    OPage = OPage
    Search = Search
    traverse = Base.traverse.copy()
    traverse.update({'ui': True, 'guard': True, 'Search': True})
    Initiator = Initiator
    # The tool is not indexed by default
    indexable = False

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
    #  Tool initialisation
    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
    def init(self, handler, poFiles):
        '''Ensure all required tool sub-objects are present and coherent'''
        # Get the root database object from the current request p_handler
        root = handler.connection.root

        # Create the default users if they do not exist
        for login, roles in User.defaultUsers.items():
            # Does this user exist in the database ?
            if login in root.objects:
                # Yes. Do not create it. But ensure, for "anon" and "system",
                # that they have no email.
                user = root.objects.get(login)
                if login != 'admin': user.email = None
            else:
                # No. Create it.
                user = self.create('users', secure=False, id=login, login=login,
                            password=login, roles=roles)
                self.log('User "%s" created.' % login)

        # Ensure group "admins" exists. This group is granted role "Manager",
        # the role with the highest level of prerogatives in Appy.
        if 'admins' not in root.objects:
            self.create('groups', secure=False, id='admins', login='admins',
                        title='Administrators', roles=['Manager'])
            self.log('Group "admins" created.')

        # Load Appy "po" files if we need to inject their values into
        # Translation objects. app's "po" files are already in p_poFiles.
        config = handler.server.config.ui
        load = config.loadTranslationsAtStartup
        if load: appyFiles = po.load(pot=False, languages=config.languages)

        # Ensure a Translation object exists for every supported language
        for language in config.languages:
            if language not in root.objects:
                # Create a Translation file
                tr = self.create('translations', secure=False, id=language,
                            title='%s (%s)' % (language, nativeNames[language]),
                            sourceLanguage=config.sourceLanguage)
                tr.updateFromFiles(appyFiles, poFiles)
            else:
                tr = root.objects[language]
                if load: tr.updateFromFiles(appyFiles, poFiles)

        # Call method "onInstall" on the tool when available. This hook allows
        # an app to execute code on server initialisation.
        if hasattr(self, 'onInstall'): self.onInstall()

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
    #  Page "main"
    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -

    # Methods protecting visibility of tool pages and fields
    def forToolWriters(self):
        '''Some elements are only accessible to tool writers (ie Managers)'''
        if self.allows('write'): return Show.ER_

    def pageForToolWriters(self):
        '''Some tool pages are only accessible to tool writers (ie Managers)'''
        if self.allows('write'): return 'view'

    ta = {'label': 'Tool'}
    # Storing the Appy version on the tool (in the form of a string "x.y.z")
    # allows to trigger automatic migrations at server startup.
    appyVersion = String(show='view', **ta)

    # This hidden calendar is used for searches in "calendar" mode
    def calendarPreCompute(self, first, grid):
        '''Computes pre-computed information for the tool calendar'''
        # If this calendar is used as mode for a search, get this search
        req = self.req
        ctx = self.H().context
        mode = None
        if 'uiSearch' in ctx:
            # The search and related mode are already in the PX context
            mode = ctx.mode
        elif req.has_key('search') and req.has_key('className'):
            # Get the search and its mode from request keys
            className = req['className']
            tool = self.o
            search = self.o.getSearch(className, req['search'], ui=True)
            mode = search.Calendar(tool.getAppyClass(className), className,
                                   search, ctx.popup, tool)
            mode.init(req, ctx.dir)
        # Trigger the search via the mode
        if mode: mode.search(first, grid)
        return O(mode=mode)

    def calendarAdditionalInfo(self, date, preComputed):
        '''Renders the content of a given cell in the calendar used for
           searches' calendar mode.'''
        info = preComputed.mode.dumpObjectsAt(date)
        if info: return info

    calendar = Calendar(preCompute=calendarPreCompute, show=False,
                        additionalInfo=calendarAdditionalInfo, **ta)

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
    #  Page "users"
    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -

    userPage = Page('users', show=pageForToolWriters, label='Tool_page_users')

    # Ref(User) will maybe be transformed into Ref(AppUser)
    users = Ref(User, multiplicity=(0,None), add=True, link=False,
      composite=True, back=Ref(attribute='toTool', show=False, layouts='f'),
      page=userPage, queryable=True, queryFields=('title', 'login', 'roles'),
      show=forToolWriters, showHeaders=True, actionsDisplay='inline',
      shownInfo=('title', 'name*15%|', 'login*20%|', 'roles*20%|'), **ta)

    def computeConnectedUsers(self, expr=None, context=None):
        '''Computes a table showing users that are currently connected.

           If p_expr is given, it must be an expression that will be evaluated
           on every connected user. The user will be part ofthe result only if
           the expression evaluates to True. The user is given to the expression
           as variable "user".'''
        # Get and count connected users
        users = list(self.H().server.loggedUsers.items())
        users.sort(key=lambda u: u[1], reverse=True) # Sort by last access date
        count = len(users)
        # Prepare the expression's context when relevant
        if expr:
            if context is None: context = {}
        # Compute table rows
        rows = []
        for login, access in users:
            user = self.search1('User', noSecurity=True, login=login)
            if not user: continue # Could have been deleted in the meanwhile
            if expr:
                # Update the p_expr's context with the current user
                context['user'] = user
                # Evaluate it
                if not eval(expr, context): continue
            rows.append('<tr><td><a href="%s">%s</a></td><td>%s</td></tr>' % \
                        (user.url, user.title, self.Date.format(access)))
        # Create an empty row if no user has been found
        if not rows:
            rows.append('<tr><td colspan="2" align="center">%s</td></tr>' %
                        self.translate('no_value'))
            count = 0
        else:
            count = len(rows)
        # Build the entire table
        r = '<table cellpadding="0" cellspacing="0" class="list compact">' \
            '<tr><th>(%d)</th><th>%s</th></tr>' % \
            (count, self.translate('last_user_access'))
        return r + '\n'.join(rows) + '</table>'

    connectedUsers = Computed(method=computeConnectedUsers, page=userPage,
                              show='view', **ta)

    def doSynchronizeExternalUsers(self):
        '''Synchronizes the local User copies with a distant LDAP user base'''
        cfg = self.config.security.ldap
        if not cfg: raise Exception('LDAP config not found.')
        counts = cfg.synchronizeUsers(self)
        msg = 'LDAP users: %d created, %d updated, %d untouched, ' \
              '%d invalid entries.' % counts
        return True, msg

    def showSynchronizeUsers(self):
        '''Show this button only if a LDAP connection exists and is enabled'''
        cfg = self.config.security.ldap
        if cfg and cfg.enabled: return 'view'

    synchronizeExternalUsers = Action(action=doSynchronizeExternalUsers,
      show=showSynchronizeUsers, confirm=True, page=userPage, **ta)

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
    #  Page "groups"
    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -

    # Ref(Group) will maybe be transformed into Ref(AppGroup)
    groups = Ref(Group, multiplicity=(0,None), add=True, link=False,
      composite=True, back=Ref(attribute='toTool', show=False,layouts='f'),
      page=Page('groups', show=pageForToolWriters, label='Tool_page_groups'),
      show=forToolWriters, queryable=True, queryFields=('title', 'login'),
      showHeaders=True, actionsDisplay='inline',
      shownInfo=('title', 'login*20%|', 'roles*20%|'), **ta)

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
    #  Page "translations"
    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -

    pt = Page('translations', show=pageForToolWriters,
              label='Tool_page_translations')

    # Ref(Translation) will maybe be transformed into Ref(AppTranslation)
    translations = Ref(Translation, multiplicity=(0,None), add=False,
      link=False, composite=True, show='view', page=pt, actionsDisplay='inline',
      back=Ref(attribute='toTool', show=False, layouts='f'), **ta)

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
    #  Page "pages"
    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -

    pp = Page('pages', show=lambda o: o.allows('write'),
              label='Tool_page_pages')

    pages = Ref(OPage, multiplicity=(0,None), add=True, link=False,
      composite=True, show='view', actionsDisplay='inline', page=pp,
      back=Ref(attribute='toTool', show=False, layouts='f'), **ta)

    homeText = Rich(page=pp, **ta)

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
    #  Main methods
    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -

    def computeHomePage(self):
        '''Compute the page that is shown to the user when he hits the app'''
        # Get the currently logged user
        user = self.user
        if user.isAnon() and self.config.ui.discreetLogin:
            return '%s/public' % self.url
        # If the user must change its password, redirect him to this page
        if user.changePasswordAtNextLogin:
            return '%s/edit?page=passwords' % user.url
        # If the app defines a tool method names "getHomePage", call it
        r = None
        if hasattr(self, 'getHomePage'):
            r = self.getHomePage()
        if not r:
            # Bring Managers to tool/view, lead others to user/home
            if user.hasRole('Manager'):
                r = '%s/view' % self.url
            else:
                r = user.url
        # Did the user come to its home page for authenticating, and must he,
        # afterwards, be redirected to some other page ?
        goto = self.req.goto
        if goto:
            goto = urllib.parse.quote(goto)
            sep = '&' if '?' in r else '?'
            r += '%sgoto=%s' % goto
            self.say(self.translate('please_authenticate'))
        return r

    def computeHomeObject(self, user, popup=False):
        '''The concept of "home object" is the object where the user must "be",
           even if he is "nowhere". For example, if the user is on a search
           screen, there is no contextual object (the tool excepted). In this
           case, if we have a home object for him, we will use it as contextual
           object, and its portlet menu will nevertheless appear: the user will
           not have the feeling of being lost.'''
        # If we are in the popup, we do not want any home object in the way
        if popup: return
        if hasattr(self, 'getHomeObject'):
            # If the app defines a method "getHomeObject", call it
            r = self.getHomeObject()
        else:
            # For managers, the home object is the tool. For others, there is
            # no default home object.
            if user.hasRole('Manager'): return self

    def getPageTitle(self, o):
        '''Returns content for tag html > head > title'''
        # Return the app name in some cases
        if not o or (o == self): return self.translate('app_name')
        # The page title is based on p_o's title
        r = o.getShownValue()
        # Ensure this is a string
        r = r if isinstance(r, str) else str(r)
        # Remove <br/> tags
        if '<br/>' in r: r = r[:r.index('<br/>')]
        # Add the page title if found
        if 'page' in self.req:
            label = '%s_page_%s' % (obj.class_.name, self.req.page)
            text = self.translate(label, blankOnError=True)
            if text:
                if r: r += ' :: '
                r += text
        return Px.truncateValue(res, width=100)

    def getGoogleAnalyticsCode(self, handler, config):
        '''If the config defines a Google Analytics ID, this method returns the
           Javascript code to be included in every page, allowing Google
           Analytics to work.'''
        # Disable Google Analytics when we are in debug mode
        if handler.server.mode == 'fg': return
        # Disable Google Analytics if no ID is found in the config.
        gaId = config.googleAnalyticsId
        if not gaId: return
        # Google Analytics must be enabled: return the chunk of Javascript
        # code specified by Google.
        code = "var _gaq = _gaq || [];\n" \
               "_gaq.push(['_setAccount', '%s']);\n" \
               "_gaq.push(['_trackPageview']);\n" \
               "(function() {\n" \
               "  var ga = document.createElement('script'); " \
               "ga.type = 'text/javascript'; ga.async = true;\n" \
               "  ga.src = ('https:' == document.location.protocol ? " \
               "'https://ssl' : 'http://www') + " \
               "'.google-analytics.com/ga.js';\n" \
               "  var s = document.getElementsByTagName('script')[0]; " \
               "s.parentNode.insertBefore(ga, s);\n" \
               "})();\n" % gaId
        return code

    def formatDate(self, date, format=None, withHour=True, language=None):
        '''Check doc in called method'''
        if not date: return
        return self.config.ui.formatDate(date, format, withHour, language)

    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -
    #  PXs
    #  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -  -

    # Hooks for defining a PX that proposes additional links or icons, before
    # and after the links/icons corresponding to top-level pages and icons.
    pxLinks = Px('')
    pxLinksAfter = Px('')

    # PX "home" is the default page shown for a standard Appy site, excepted
    # when discreet logins are enabled. In this latter case, PX "public",
    # hereafter, is more appropriate.
    home = Px('''
     <!-- If discreet logins are enabled, redirect the user to the alternative
          "public" page. -->
     <x if="cfg.discreetLogin" var2="x=tool.goto(tool.computeHomePage())"></x>

     <!-- The home text -->
     <div if="isAnon and not cfg.discreetLogin and not tool.isEmpty('homeText')"
          class="homeText">::tool.homeText</div>''',

     css='''
      .homeText { position: fixed; left: 45px; top: 25px; color: white }
      .homeText h1 { font-size: 300%; margin-left: -5px }
      .homeText h2 { font-size: 200% }
      .homeText p { font-size: 120%; margin: 0 }
      .homeText a, .homeText a:visited { color: #ffd8eb }
     ''',

     template=Template.px, hook='content', name='home')

    default = home

    # The "public" page is an alternative to "home" for anonymous users, when
    # discreet logins are enabled.
    public = Px('''
     <!-- The home text -->
     <div if="not tool.isEmpty('homeText')"
          class="homeText">::tool.homeText</div>''',
     template=Template.px, hook='content', name='public')

    # Disable tool removal
    def mayDelete(self): return
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
