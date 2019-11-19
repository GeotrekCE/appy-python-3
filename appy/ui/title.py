'''Object's field "title" requires a specific treatment in order to be rendered
   in the user interface.'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy.px import Px
from appy.ui.criteria import Criteria

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Title:
    '''Manages the zone, mainly within lists, rendering the title of an object
       and everything around it (sup- and sub-titles).'''

    @staticmethod
    def showSub(class_, field):
        '''Show button "details" only under field "title", if a method named
           "getSubTitle" is defined on p_class_.'''
        return (field.name == 'title') and class_.hasSubTitle()

    # Icon for hiding/showing the "sub-title" zone under an object's title
    pxSub = Px('''
     <img src=":url('toggleDetails')" class="clickable"
          onclick="toggleSubTitles()"/>''',
    
     js='''
      // Function that sets a value for showing/hiding sub-titles
      function setSubTitles(value, tag) {
        createCookie('showSubTitles', value);
        // Get the sub-titles
        var subTitles = getElementsHavingName(tag, 'subTitle');
        if (subTitles.length == 0) return;
        // Define the display style depending on p_tag
        var displayStyle = 'inline';
        if (tag == 'tr') displayStyle = 'table-row';
        for (var i=0; i < subTitles.length; i++) {
          if (value == 'True') subTitles[i].style.display = displayStyle;
          else subTitles[i].style.display = 'none';
        }
      }

      // Function that toggles the value for showing/hiding sub-titles
      function toggleSubTitles(tag) {
        // Get the current value
        var value = readCookie('showSubTitles') || 'True';
        // Toggle the value
        var newValue = (value == 'True')? 'False': 'True';
        if (!tag) tag = 'div';
        setSubTitles(newValue, tag);
      }''')

    @classmethod
    def get(class_, o, mode='link', nav='no', target=None, page='main',
            popup=False, baseUrl=None, title=None, linkTitle=None, css=None,
            selectJs=None, highlight=False, backHook=None, maxChars=None):
        '''Gets p_o's title as it must appear in lists of objects (ie in
           lists of tied objects in a Ref, in search results...).'''

        # In most cases, a title must appear as a link that leads to the object
        # view layout. In this case (p_mode == "link"):
        # ----------------------------------------------------------------------
        # p_nav       | is the navigation parameter allowing navigation between
        #             | this object and others;
        # p_target    | specifies if the link must be opened in the popup or
        #             | not;
        # p_page      | specifies which page to show on the target object view;
        # p_popup     | indicates if we are already in the popup or not;
        # p_baseUrl   | indicates a possible alternate base URL for accessing
        #             | the object;
        # p_title     | specifies, if given, an alternate content for the "a"
        #             | tag (can be a PX);
        # p_linkTitle | specifies a possible value for attribute "link" for the
        #             | "a" tag (by default this attribute is not dumped);
        # p_css       | can be the name of a CSS class to apply (also for other
        #             | modes);
        # p_maxChars  | gives an (optional) limit to the number of visible title
        #             | chars.
        # ----------------------------------------------------------------------

        # Another p_mode is "select". In this case, we are in a popup for
        # selecting objects: every title must not be a link, but clicking on it
        # must trigger Javascript code (in p_selectJs) that will select this
        # object.

        # The last p_mode is "text". In this case, we simply show the object
        # title but with no tied action (link, select).

        # If p_highlight is True, keywords will be highlighted if we are in the
        # context of a query with keywords.

        # If the class_ whose elements must be listed has an attribute
        # "uniqueLinks" being True, in "link" mode, the generated link will
        # include an additional parameter named "_hash". This parameter will
        # ensure that the link will be different every time it is generated.
        # This is useful for short-circuiting the a:visited CSS style when an
        # app wants to manage link's style in some specific way.

        # Compute CSS class
        class_ = o.class_
        handler = o.H()
        cssClass = class_.getCssFor(o, 'title')
        if css: cssClass += ' %s' % css
        # Get the title, with highlighted parts when relevant
        titleIsPx = False
        if not title:
            title = class_.getListTitle(o)
        elif isinstance(title, Px):
            title = title(handler.context)
            titleIsPx = True
        if highlight and not titleIsPx:
            title = Criteria.highlight(handler, title)
        if maxChars: title = Px.truncateText(title, width=maxChars)
        if mode == 'link':
            popup = popup or (target.target != '_self')
            params = {'page': page, 'nav': nav, 'popup': popup,
                      'unique': class_.produceUniqueLinks()}
            # Build the link URL, or patch the given p_baseUrl
            url = o.getUrl(sub='view', **params) \
                  if baseUrl is None else o.patchUrl(baseUrl, **params)
            # Define attribute "onClick"
            if target.onClick:
                onClick= ' onclick="%s"'% target.getOnClick(backHook or o.id)
            else:
                onClick = ''
            # Set a "title" parameter when relevant
            lt = linkTitle and (' title="%s"' % linkTitle) or ''
            r = '<a name="title" href="%s" class="%s" target="%s"%s%s>%s</a>' %\
                (url, cssClass, target.target, onClick, lt, title)
        elif mode == 'select':
            r = '<span class="%s clickable" onclick="%s">%s</span>' % \
                (cssClass, selectJs, title)
        elif mode == 'text':
            r = '<span class="%s">%s</span>' % (cssClass, title)
        return r
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
