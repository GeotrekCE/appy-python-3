'''Portlet management'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy.px import Px

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Portlet:
    '''The portlet, in the standard layout, is a zone from the UI shown as a
       column situated at the left of the screen for left-to-right languages,
       and at the right for right-to-left languages.'''

    @classmethod
    def show(class_, tool, px, layout, popup, config, handler):
        '''When must the portlet be shown ?'''
        # Do not show the portlet on 'edit' pages, if we are in the popup or if
        # there is no root class.
        if popup or (layout == 'edit') or (px.name == 'home') or \
           (config.model.rootClasses is None):
            return
        # If we are here, portlet visibility depends on the app, via method
        # "tool::showPortletAt", when defined.
        return tool.showPortletAt(handler.path) \
               if hasattr(tool, 'showPortletAt') else True

    pxLiveSearchResults = Px('''
     <div var="className=req['className'];
               klass=ztool.getAppyClass(className);
               search=ztool.getLiveSearch(klass, req['w_SearchableText']);
               zobjects=ztool.executeQuery(className, search=search, \
                                           maxResults=10).objects"
          id=":'%s_LSResults' % className">
      <p if="not zobjects" class="lsNoResult">::_('query_no_result')</p>
      <div for="zobj in zobjects" style="padding: 3px 5px">
       <a href=":zobj.absolute_url()"
          var="content=ztool.truncateValue(zobj.Title(), width=80)"
          title=":zobj.Title()">:content</a>
      </div>
      <!-- Go to the page showing all results -->
      <div if="zobjects" align=":dright" style="padding: 3px">
       <a class="clickable" style="font-size: 95%; font-style: italic"
          onclick=":'document.forms[%s].submit()' % \
            q('%s_LSForm' % className)">:_('search_results_all') + '...'</a>
      </div>
     </div>''')

    pxLiveSearch = Px('''
     <form var="formId='%s_LSForm' % className"
           id=":formId" name=":formId" action=":'%s/do' % toolUrl">
      <input type="hidden" name="action" value="SearchObjects"/>
      <input type="hidden" name="className" value=":className"/>
      <table cellpadding="0" cellspacing="0"
             var="searchLabel=_('search_button')">
       <tr valign="bottom">
        <td style="position: relative">
         <input type="text" size="14" name="w_SearchableText" autocomplete="off"
                id=":'%s_LSinput' % className" class="inputSearch"
                title=":searchLabel"
                var="jsCall='onLiveSearchEvent(event, %s, %s, %s)' % \
                             (q(className), q('auto'), q(toolUrl))"
                onkeyup=":jsCall" onfocus=":jsCall"
                onblur=":'onLiveSearchEvent(event, %s, %s)' % \
                         (q(className), q('hide'))"/>
         <!-- Dropdown containing live search results -->
         <div id=":'%s_LSDropdown' % className" class="dropdown liveSearch">
          <div id=":'%s_LSResults' % className"></div>
         </div>
        </td>
        <td><input type="image" src=":url('search')" title=":searchLabel"/></td>
       </tr>
      </table>
     </form>''')

    px = Px('''
     <x var="toolUrl=tool.url;
             queryUrl='%s/Search/results' % toolUrl;
             currentSearch=req.search;
             currentClass=req.className;
             currentPage=handler.parts[-1];
             rootClasses=handler.server.model.getRootClasses()">

      <!-- One section for every searchable root class -->
      <x for="class_ in rootClasses" if="class_.maySearch(tool, layout)"
         var2="className=class_.name">

       <!-- A separator if required -->
       <div class="portletSep" if="not loop.class_.first"></div>

       <!-- Section title (link triggers the default search) -->
       <div class="portletContent"
            var="searches=class_.getGroupedSearches(tool, _ctx_)">
        <div class="portletTitle">
         <a var="queryParam=searches.default.name if searches.default else ''"
            href=":'%s?className=%s&amp;search=%s' % \
                   (queryUrl, className, queryParam)"
            onclick="clickOn(this)"
            class=":(not currentSearch and (currentClass==className) and \
                    (currentPage == 'pxResults')) and \
                    'current' or ''">::_(className + '_plural')</a>

         <!-- Create instances of this class -->
         <x if="guard.mayInstantiate(class_, checkInitiator=False)"
            var2="create=class_.getCreateVia(tool)">
          <form if="create" class="addForm" name=":'%s_add' % className"
                var2="target=ui.LinkTarget(class_)"
                action=":'%s/new' % toolUrl" target=":target.target">
           <input type="hidden" name="className" value=":className"/>
           <input type="hidden" name="template" value=""/>
           <input type="hidden" name="insert" value=""/>
           <input type="hidden" name="popup"
           value=":'True' if (popup or (target.target!='_self')) else 'False'"/>
           <!-- Create from an empty form -->
           <input type="submit" value="" var="label=_('object_add')"
                  title=":label" class="buttonIcon button"
                  onclick=":target.getOnClick('queryResult')"
                  style=":url('add', bg=True)"/>
           <!-- Create from a pre-filled form when relevant -->
           <x if="create != 'form'"
              var2="fromRef=False; sourceField=None;
                    addFormName='%s_add' % className">:class_.pxAddFrom</x>
          </form>
         </x>
        </div>

        <!-- Searches -->
        <x if="class_.maySearchAdvanced(tool)">

         <!-- Live search -->
         <x>:ui.Portlet.pxLiveSearch</x>

         <!-- Advanced search -->
         <div var="highlighted=(currentClass == className) and \
                               (currentPage == 'search')"
              class=":highlighted and 'portletSearch current' or \
                     'portletSearch'"
              align=":dright" style="margin-bottom: 4px">
          <a var="text=_('search_title')" style="font-size: 88%"
             href=":'%s/search?className=%s' % (toolUrl, className)"
             title=":text"><x>:text</x>...</a>
         </div>
        </x>

        <!-- Predefined searches -->
        <x for="search in searches.all" var2="field=search">
         <x>:search.px if search.type == 'group' else search.view</x>
        </x>

        <!-- Portlet bottom, potentially customized by the app -->
        <x var="pxBottom=class_.getPortletBottom(tool)"
           if="pxBottom">:pxBottom</x>
       </div>
      </x>
     </x>''',

     css='''
       .portlet { width: 170px; border: none; color: white;
                  background-color: #8399b7; padding-top: 30px;
                  vertical-align: top; margin-bottom: 30px; position: relative }
       .portlet a, .portlet a:visited { color: white; padding: 0px 5px 0 0 }
       .portlet a:hover { background-color: white; color: #305e9d }
       .portletContent { padding: 0 0 0 20px; background: none; width: 180px }
       .portletContent input[type=text] { background-color: white }
       .portletTitle { font-size: 110%; padding: 5px 0; margin: 0;
                       text-transform: uppercase }
       .portletSep { border-top: 10px solid transparent }
       .portletGroup { text-transform: uppercase; padding: 5px 0 0 0;
                       margin: 0.1em 0 0.3em }
       .portletSearch { font-size: 110%; text-align: left }
       .portletCurrent { font-weight: bold }
       .portlet form { margin-left: -3px }
       .liveSearch a, .liveSearch a:visited { color: #1f549a; font-size: 120% }
       .lsSelected { background-color: #d9d7d9 }
       .lsNoResult { color: #1f549a; font-size: 120% }
     ''')
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
