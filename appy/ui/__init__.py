'''User-interface module'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import os.path, re, urllib.parse

from appy.px import Px
from appy.ui.layout import ColumnLayout
from appy.model.utils import Object as O

# Make classes from sub-packages available here  - - - - - - - - - - - - - - - -
from appy.ui.js import Quote
from appy.ui.title import Title
from appy.ui.iframe import Iframe
from appy.ui.portlet import Portlet
from appy.ui.globals import Globals
from appy.ui.navigate import Siblings
from appy.ui.includer import Includer
from appy.ui.language import Language
from appy.ui.validate import Validator

# Some elements in this module will be traversable - - - - - - - - - - - - - - -
traverse = {'Language': True}

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Config:
    '''Represents user-interface configuration for your app'''

    # Defaults fonts used in the web user interface
    fonts = "Rajdhani, sans-serif"

    # Regular expression for variables defined in CSS file templates
    cssVariable = re.compile(b'\|(\w+?)\|', re.S)

    def __init__(self):
        # The home page's background image
        self.homeBackground = 'appy/sunrise.jpg'
        # The logo within the page header
        self.headerLogo = 'appy/headerLogo.png'
        # The logo at the bottom of the portlet
        self.portletLogo = 'appy/portletLogo.png'
        # If you place a function in the following attributes, it will be called
        # with, as args, the current PX and its context, and must return True
        # whenever the corresponding UI element must be shown. If no function is
        # set, the UI element will be shown, excepted in some predefined
        # situations (ie, the header and the footer are not shown on the home
        # page).
        self.headerShow = None
        self.footerShow = None
        # Fonts in use
        self.fonts = Config.fonts
        self.fontSize = '100%'
        # Among the fonts listed above, specify here, as a tuple, those being
        # Google fonts. That way, the corresponding "CSS include" will be
        # injected into all the pages from your app.
        self.googleFonts = ('Rajdhani',)
        # If you want to add specific CSS classes to some standard Appy parts,
        # specify a function in the following attribute. The function will
        # receive, as args, the name of the concerned part, the current PX and
        # its context; it must return the name of one or more CSS classes or
        # None when no class must be added. Currently defined parts are the
        # following.
        # ----------------------------------------------------------------------
        #   body      | The page "body" tag
        #   main      | The main zone of any page, behind the user strip
        # ----------------------------------------------------------------------
        self.css = None
        # Some input fields will get this background color once they will
        # contain erroneous content.
        self.wrongTextColor = '#F9EDBE'
        # Application-wide default formats for hours and dates
        self.dateFormat = '%d/%m/%Y'
        self.hourFormat = '%H:%M'
        # Application-wide maximum results on a single page of query results
        self.maxPerPage = 30
        # Number of translations for every page on a Translation object
        self.translationsPerPage = 30
        # If users modify translations via the ui, we must now overwrite their
        # work with the current content of po files at every server restart. In
        # any other case, it is preferable to do it.
        self.loadTranslationsAtStartup = True
        # Language that will be used as a basis for translating to other
        # languages.
        self.sourceLanguage = 'en'
        # For every language code that you specify in this list, Appy will
        # produce and maintain translation files.
        self.languages = ['en']
        # If languageSelector is True, on (almost) every page, a language
        # selector will allow to switch between languages defined in
        # self.languages. Else, the browser-defined language will be used for
        # choosing the language of returned pages.
        self.languageSelector = False
        # If "forceLanguage" is set, Appy will not take care of the browser
        # language, will always use the forced language and will hide the
        # language selector, even if "languageSelector" hereabove is True.
        self.forcedLanguage = None
        # Show the link to the user profile in the user strip
        self.userLink = True
        # If you want to distinguish a test site from a production site, set the
        # "test" parameter to some text (lie "TEST SYSTEM" or
        # "VALIDATION ENVIRONMENT". This text will be shown on every page. This
        # parameter can also hold a function that will accept the tool as single
        # argument and returns the message.
        self.test = None
        # CK editor configuration. Appy integrates CK editor via CDN (see
        # http://cdn.ckeditor.com). Do not change "ckVersion" hereafter,
        # excepted if you are sure that the customized configuration files
        # config.js, contents.css and styles.js stored in
        # appy/ui/static/ckeditor will be compatible with the version you want
        # to use.
        self.ckVersion = '4.11.2'
        # ckDistribution can be "basic", "standard", "standard-all", "full" or
        # "full-all" (see doc in http://cdn.ckeditor.com).
        # CK toolbars are not configurable yet. So toolbar "Appy", defined in
        # appy/ui/static/ckeditor/config.js, will always be used.
        self.ckDistribution = 'standard'
        # The tool may be configured in write-access only for a technical
        # reason, ie, for allowing user self-registration. Indeed, in that case,
        # anonymous users must be granted the ability to add a User instance in
        # Ref tool.users. In that case, we don't want to show the icon allowing
        # to access the tool to anyone having write-access to it. For these
        # cases, a specific function may be defined here for determining
        # showability of the tool's icon in the UI. This function will receive
        # the tool as unique arg.
        self.toolShow = None
        # If the following field is True, the login/password widget will be
        # discreet. This is for sites where authentication is not foreseen for
        # the majority of visitors (just for some administrators).
        self.discreetLogin = False

    def formatDate(self, tool, date, format=None, withHour=True, language=None):
        '''Returns p_date formatted as specified by p_format, or self.dateFormat
           if not specified. If p_withHour is True, hour is appended, with a
           format specified in self.hourFormat.'''
        fmt = format or self.dateFormat
        # Resolve Appy-specific formatting symbols used for getting translated
        # names of days or months:
        # ----------------------------------------------------------------------
        #  %dt  | translated name of day
        #  %DT  | translated name of day, capitalized
        #  %mt  | translated name of month
        #  %MT  | translated name of month, capitalized
        #  %dd  | day number, but without leading '0' if < 10
        # ----------------------------------------------------------------------
        if ('%dt' in fmt) or ('%DT' in fmt):
            day = tool.translate('day_%s' % date._aday, language=language)
            fmt = fmt.replace('%dt', day.lower()).replace('%DT', day)
        if ('%mt' in fmt) or ('%MT' in fmt):
            month = tool.translate('month_%s' % date._amon, language=language)
            fmt = fmt.replace('%mt', month.lower()).replace('%MT', month)
        if '%dd' in fmt: fmt = fmt.replace('%dd', str(date.day()))
        # Resolve all other, standard, symbols
        r = date.strftime(fmt)
        # Append hour
        if withHour and (date._hour or date._minute):
            r += ' (%s)' % date.strftime(self.hourFormat)
        return r

    def getHeaderMessages(self, tool, handler):
        '''Get the permanent messages that must appear in the page header'''
        # Get the "test" message
        r = self.test
        if callable(r): r = test(tool)
        r = r or ''
        # Get the browser incompatibility message
        bi = Browser.getIncompatibilityMessage(tool, handler)
        bi = bi = '<div class="wrongBrowser">%s</div>' % bi if bi else ''
        return r + bi

    def getBackground(self, px, siteUrl, type):
        '''Return the CSS properties allowing to include this background p_image
           when appropriate.'''
        # Do not generate any background image when appropriate
        stop = (px.name != 'home') if (type == 'home') else (px.name == 'home')
        if stop: return ''
        if type == 'home':
            # This is the background image for the home page
            image = self.homeBackground
            attrs = 'background-size: cover'
        elif type == 'header':
            # This is the background logo for the page header
            image = self.headerLogo
            attrs = 'background-position: center'
        elif type == 'portlet':
            # This is the background image within the portlet
            attrs = 'background-position: 45% 90%'
            image = self.portletLogo
        return 'background-image: url(%s/static/%s); background-repeat: ' \
               'no-repeat; %s' % (siteUrl, image, attrs)

    def _show(self, elem, px, context, popup):
        ''''As a general rule, always show UI p_elem, excepted in the popup, on
            the home page or when a custom function prevents it.'''
        # Do not show it if we are in the popup or on the home page, excepted if
        # the "discreet login" mode is enabled.
        if popup or (px.name == 'home'): return
        # A custom function may determine it. If no such function is defined,
        # show it.
        fun = getattr(self, '%sShow' % elem)
        return not fun and True or fun(px, context)

    def showHeader(self, px, context, popup):
        return self._show('header', px, context, popup)

    def showFooter(self, px, context, popup):
        return self._show('footer', px, context, popup)

    def getClass(self, part, px, context):
        '''Get the CSS classes that must be defined for some UI p_part, if
           any.'''
        # Start with the standard set of Appy classes that must set on p_part
        r = 'main rel' if part == 'main' else ''
        # Add specific classes when relevant
        if self.css:
            add = self.css(part, px, context)
            if not add: return r
            r = add if not r else ('%s %s' % (r, add))
        return r

    def getFontsInclude(self):
        '''If Google Fonts are in use, return the link to the CSS include
           allowing to use it.'''
        families = '|'.join(self.googleFonts)
        return 'https://fonts.googleapis.com/css?family=%s' % families

    def patchCss(self, cssContent):
        '''p_cssContent is the content of some CSS file. Replace, in it,
           variables with their values as defined on p_self.'''
        # This function will, for every match (=every variable use found in
        # p_cssContent), return the corresponding value on p_self
        fun = lambda match: getattr(self, match.group(1).decode()).encode()
        return Config.cssVariable.sub(fun, cssContent)

    def showTool(self, tool):
        '''Show the tool icon to anyone having write access to the tool,
           excepted if a specific function is defined.'''
        if self.toolShow:
            # A specific function has been defined
            r = self.toolShow(tool)
        else:
            # No specific function: show the icon to anyone having write access
            # to the tool.
            r = tool.allows('write')
        return r

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Message:
    '''Manages the "message zone" allowing to display messages coming from the
       Appy server to the end user.'''

    @classmethod
    def consumeAll(class_, handler, unlessRedirect=False):
        '''Returns the list of messages to show to a web page'''
        # Do not consume anything if p_unlessRedirect is True and we are
        # redirecting the user.
        if unlessRedirect and ('Appy-Redirect' in handler.resp.headers): return
        # Try to get messages from the 'AppyMessage' cookie
        message = handler.req.AppyMessage
        if message:
            # Dismiss the cookie
            handler.resp.setCookie('AppyMessage', 'deleted')
            return urllib.parse.unquote(message)

    @classmethod
    def hasValidationErrors(class_, handler):
        '''Returns True if there are validaton errors collected by the
           (handler.)validator.'''
        return handler.validator and handler.validator.errors

    # The message zone
    px = Px('''
     <div var="validErrors=ui.Message.hasValidationErrors(handler)"
          class=":'messagePopup message' if popup else 'message'"
          style=":'display:none' if not validErrors else 'display:block'"
          id="appyMessage">
      <!-- The icon for closing the message -->
      <img src=":url('close')" align=":dright" class="clickable"
           onclick="this.parentNode.style.display='none'"/>
      <!-- The message content -->
      <div id="appyMessageContent">:validErrors and _('validation_error')</div>
      <div if="validErrors"
           var2="validator=handler.validator">:handler.validator.pxErrors</div>
     </div>
     <script var="messages=ui.Message.consumeAll(handler)"
             if="messages">::'showAppyMessage(%s)' % q(messages)</script>''')

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class LinkTarget:
    '''Represents information about the target of an HTML "a" tag'''

    def __init__(self, class_=None, back=None, forcePopup=False):
        '''The HTML "a" tag must lead to a page for viewing or editing an
           instance of some p_class_. If this page must be opened in a popup
           (depends on attribute p_class_.popup), and if p_back is specified,
           when coming back from the popup, we will ajax-refresh a DOM node
           whose ID is specified in p_back.'''
        # The link leads to a instance of some Python p_class_
        self.class_ = class_
        # Does the link lead to a popup ?
        toPopup = True if forcePopup else class_ and hasattr(class_, 'popup')
        # Determine the target of the "a" tag
        self.target = toPopup and 'appyIFrame' or '_self'
        # If the link leads to a popup, a "onClick" attribute must contain the
        # JS code that opens the popup.
        if toPopup:
            # Create the chunk of JS code to open the popup
            size = getattr(class_, 'popup', '350px')
            if isinstance(size, str):
                params = "%s,null" % size[:-2] # Width only
            else: # Width and height
                params = "%s, %s" % (size[0][:-2], size[1][:-2])
            # If p_back is specified, included it in the JS call
            if back: params += ",'%s'" % back
            self.onClick = "openPopup('iframePopup',null,%s)" % params
        else:
            self.onClick = ''

    def getOnClick(self, back):
        '''Gets the "onClick" attribute, taking into account p_back DOM node ID
           that was unknown at the time the LinkTarget instance was created.'''
        # If we must not come back from a popup, return an empty string
        r = self.onClick
        if not r: return r
        return r[:-1] + ",'%s')" % back

    def __repr__(self):
        return '<LinkTarget for=%s,target=%s,onClick=%s>' % \
               (self.class_.__name__, self.target, self.onClick or '-')

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Collapsible:
    '''Represents a chunk of HTML code that can be collapsed/expanded via
       clickable icons.'''

    @classmethod
    def get(class_, zone, align, req):
        '''Gets a Collapsible instance for showing/hiding some p_zone
           ("portlet" or "sidebar").'''
        icons = (align == 'left') and 'showHide' or 'showHideInv'
        return Collapsible('appy%s' % zone.capitalize(), req,
                           default='expanded', icons=icons, align=align)

    # Various sets of icons can be used. Each one has a CSS class in appy.css
    iconSets = {'expandCollapse': O(expand='expand', collapse='collapse'),
                'showHide':       O(expand='show',   collapse='hide'),
                'showHideInv':    O(expand='hide',   collapse='show')}

    # Icon allowing to collapse/expand a chunk of HTML
    px = Px('''
     <img var="coll=collapse; icons=coll.icons"
          id=":'%s_img' % coll.id" align=":coll.align" class=":coll.css"
          onclick=":'toggleCookie(%s,%s,%s,%s,%s)' % (q(coll.id), \
                    q(coll.display), q(coll.default), \
                    q(icons.expand), q(icons.collapse))"
       src=":coll.expanded and url(icons.collapse) or url(icons.expand)"/>''',

     css='''
      .expandCollapse { padding-right: 4px; cursor: pointer }
      .showHide { position: absolute; top: 10px; left: 0px; cursor: pointer }
      .showHideInv { position: absolute; top: 10px; right: 0px; cursor: pointer}
     ''')

    def __init__(self, id, req, default='collapsed', display='block',
                 icons='expandCollapse', align='left'):
        '''p_display is the value of style attribute "display" for the XHTML
           element when it must be displayed. By default it is "block"; for a
           table it must be "table", etc.'''
        self.id = id # The ID of the collapsible HTML element
        self.default = default
        self.display = display
        self.align = align
        # Must the element be collapsed or expanded ?
        self.expanded = (req[id] or default) == 'expanded'
        self.style = 'display:%s' % (self.display if self.expanded else 'none')
        # The name of the CSS class depends on the set of applied icons
        self.css = icons
        self.icons = self.iconSets[icons]

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Sidebar:
    @classmethod
    def show(class_, tool, o, layout, popup):
        '''The sidebar must be shown when p_o declares to use the sidebar. If
           it must be shown, its width is returned.'''
        if not o: return
        sidebar = getattr(o.class_.python, 'sidebar', None)
        if not sidebar: return
        if callable(sidebar): sidebar = sidebar(tool)
        if not sidebar: return
        if sidebar.show in (True, layout):
            return getattr(sidebar, 'width', '170px')

    px = Px('''
     <x var="cssJs={};
             groupedFields=o.getGroupedFields('sidebar', 'main', cssJs=cssJs)">
      <x if="cssJs">:tool.pxCssJs</x>
      <x var="layout='view'">:o.pxFields</x>
     </x>''')

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Breadcrumb:
    '''A breadcrumb allows to display the "path" to a given object, made of the
       object title, prefixed with titles of all its container objects.'''

    def __init__(self, o, popup):
        # The concerned p_o(bject)
        self.o = o
        # The "sup" part may contain custom HTML code, retrieved by app method
        # o.getSupBreadCrumb, to insert before the breadcrumb.
        self.sup = None
        # The "sub" part may contain custom HTML code, retrieved by app method
        # o.getSubBreadCrumb, to insert after the breadcrumb.
        self.sub = None
        # The breadcrumb in itself: a list of of parts, each one being an Object
        # having 2 attributes:
        # - "title" is the title of the object represented by this part;
        # - "url"   is the URL to this object.
        self.parts = None
        self.compute(popup=popup)

    def compute(self, o=None, popup=False):
        '''Computes the breadcrumb to p_self.o, or add the part corresponding to
           p_o if p_o is given. If p_popup is True, the produced URLs are a
           bit different.'''
        # If we are recursively computing the breadcrumb on p_self.o's container
        # (or its super-container, etc), "recursive" is True.
        recursive = o is not None
        o = o or self.o
        # We must compute a complete breadcrumb for p_self.o. But must a
        # breadcrumb be shown for it ?
        class_ = o.getClass()
        show = getattr(class_.python, 'breadcrumb', True)
        if callable(show): show = show(o)
        # Return an empty breadcrumb if it must not be shown
        if not show: return
        # Compute "sup" and "sub"
        if not recursive:
            if hasattr(class_, 'getSupBreadCrumb'):
                self.sup = o.getSupBreadCrumb()
            if hasattr(class_, 'getSubBreadCrumb'):
                self.sub = o.getSubBreadCrumb()
        # Compute and add the breadcrumb part corresponding to "o"
        part = O(url=o.getUrl(popup=popup), title=o.getShownValue(),
                 view=o.allows('read'))
        if self.parts is None:
            self.parts = [part]
        else:
            self.parts.insert(0, part)
        # In a popup (or if "show" specifies it), limit the breadcrumb to the
        # current object.
        if popup or (show == 'title'): return
        # Insert the part corresponding to the container if appropriate
        container = o.container
        if container and (container.id != 'tool'):
            # The tool itself can never appear in breadcrumbs
            self.compute(container)

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Button:
    '''Manages rendering of XHTML buttons'''

    @classmethod
    def getCss(class_, label, small=True, render='button'):
        '''Gets the CSS class(es) to set on a button, given its l_label, size
           (p_small or not) and rendering (p_render).'''
        # CSS for a small button. No minimum width applies: small buttons are
        # meant to be small.
        if small:
            part = (render == 'icon') and 'Icon' or 'Small'
            return 'button%s button' % part
        # CSS for a normal button. A minimum width (via buttonFixed) is defined
        # when the label is small: it produces ranges of buttons of the same
        # width (excepted when labels are too large), which is more beautiful.
        if len(label) < 15: return 'buttonFixed button'
        return 'button'

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Footer:
    '''Footer for all (non-popup) pages'''

    px = Px('''<div class="footer">
     <span class="footerContent">::_('footer_text')</span></div>''',

     css='''
      .footer { width:100%; font-size: 95%; height: 20px; padding: 0.8em 0;
                position: fixed; bottom: 0; background-color: #CBCBC9;
                border-top: 3px solid #e4e4e4; text-align:right }
      .footerContent { padding: 0 0.5em }''')

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Browser:
    '''Determines if the browser is compatible with Appy'''

    ieRex = re.compile('MSIE\s+(\d\.\d)')
    ieMin = '9' # We do not support IE below this version

    @classmethod
    def getIncompatibilityMessage(class_, tool, handler):
        '''Return an error message if the browser in use is not compatible
           with Appy.'''
        # Get the "User-Agent" request header
        agent = handler.headers.get('User-Agent')
        r = class_.ieRex.search(agent)
        if not r: return
        version = r.group(1)
        if (version < class_.ieMin) and ('ompatible' not in agent):
            # If term "compatible" is found, it means that we have a "modern" IE
            # but that is configured to mimick an older version. Because we have
            # set a "X-UA-Compatible" directive in all Appy pages, normally,
            # this kind of IE should not apply this old compatibility mode with
            # Appy apps, so we do not display the warning in that case.
            mapping = {'version': version, 'min': class_.ieMin}
            return tool.translate('wrong_browser', mapping=mapping)

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Columns:
    '''Create special UI objects containing information about rendering objects
       in table columns.'''

    # Standard columns
    standard = O(
      number     = O(special=True, field='_number', width='15px',
                     align='left', header=False),
      checkboxes = O(special=True, field='_checkboxes', width='10px',
                     align='center', header=True)
    )

    # Error messages
    FIELD_NOT_FOUND = 'field "%s", used in a column specifier, not found.'

    @classmethod
    def get(class_, tool, modelClass, columnLayouts, dir='ltr',
            addNumber=False, addCheckboxes=False):
        '''Extracts and returns, from a list of p_columnLayouts, info required
           for displaying columns of field values for modelClass's instances.
        '''
        # p_columnLayouts are specified for each field whose values must be
        # shown. 2 more, not-field-related, column layouts can be specified with
        # these names:
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # "_number"     | if the listed objects must be numbered by Appy, this
        #               | string represents the column containing that number;
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # "_checkboxes" | if Appy must show checkboxes for the listed objects,
        #               | this string represents the column containing the
        #               | checkboxes.
        #- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # If columns "_number" and "_checkboxes" are not among p_columnLayouts
        # but are required (by p_addNumber and p_addCheckboxes), they are added
        # to the result. Specifying them within p_columnLayouts allows to give
        # them a precise position among all columns. When automatically added,
        # they will appear before any other column (which is desirable in most
        # cases).
        r = []
        numberFound = checkboxesFound = False
        for info in columnLayouts:
            name, width, align, header = ColumnLayout(info).get()
            # It that a special column name ?
            special = True
            if name == '_number': numberFound = True
            elif name == '_checkboxes': checkboxesFound = True
            else: special = False
            align = Language.flip(align, dir)
            # For non-special columns, get the corresponding field
            if not special:
                field = modelClass.fields.get(name)
                if not field:
                    self.log(class_.FIELD_NOT_FOUND % name, type='warning')
                    continue
            else:
                # Let the column name in attribute "field"
                field = name
            r.append(O(special=special, field=field, width=width, align=align,
                       header=header))
        # Add special columns if required and not present
        if addCheckboxes and not checkboxesFound:
            r.insert(0, class_.standard.checkboxes)
        if addNumber and not numberFound:
            r.insert(0, class_.standard.number)
        return r
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
