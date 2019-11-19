'''Global elements to include in HTML pages'''

# ~license~
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
from appy.ui.iframe import Iframe

#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
class Globals:
    '''Global elements to inject in most or all pages'''

    # Translated messages computed in Javascript variables in most pages
    variables = ('no_elem_selected', 'action_confirm', 'save_confirm',
                 'warn_leave_form', 'workflow_comment')

    @classmethod
    def getVariables(class_, tool):
        '''Returns Javascript variables storing translated texts used in forms
           and popups.'''
        r = ['var wrongTextInput="%s none";' % tool.config.ui.wrongTextColor]
        for label in class_.variables:
            r.append('var %s="%s";' % (label, tool.translate(label)))
        return '<script>%s</script>' % '\n'.join(r)

    # Popups must be present in every page
    popups = '''%s
     <!-- Popup for confirming an action -->
     <div id="confirmActionPopup" class="popup">
      <form id="confirmActionForm" method="post">
       <div align="center">
        <p id="appyConfirmText"></p>
        <input type="hidden" name="actionType"/>
        <input type="hidden" name="action"/>
        <div id="commentArea" align="%s"><br/>
         <span class="discreet" id="appyCommentLabel"></span>
         <textarea name="popupComment" id="popupComment"
                   cols="30" rows="3"></textarea><br/>
        </div><br/>
        <input type="button" onclick="doConfirm()" value="%s"/>
        <input type="button" value="%s"
               onclick="closePopup('confirmActionPopup', 'comment')"/>
       </div>
      </form>
     </div>
     <!-- Popup for uploading a file in a pod field -->
     <div id="uploadPopup" class="popup" align="center">
      <form id="uploadForm" name="uploadForm" enctype="multipart/form-data"
            method="post" action="%s/doPod">
       <input type="hidden" name="objectUid"/>
       <input type="hidden" name="fieldName"/>
       <input type="hidden" name="template"/>
       <input type="hidden" name="podFormat"/>
       <input type="hidden" name="action" value="upload"/>
       <input type="file" name="uploadedFile"/><br/><br/>
       <input type="submit" value="%s"/>
       <input type="button" onclick="closePopup('uploadPopup')" value="%s"/>
      </form>
     </div>
     <!-- Popup for displaying an error message -->
     <div id="alertPopup" class="popup">
      <img src="%s" align="%s" style="margin-right: 10px"/>
      <p id="appyAlertText" style="margin-bottom: 15px"></p>
      <div align="center">
       <input type="button" onclick="closePopup('alertPopup')" value="%s"/>
      </div>
     </div>%s'''

    @classmethod
    def getPopups(class_, tool, url, _, dleft, dright, popup):
        '''Returns the popups to include in every page'''
        # The "iframe" popup must not be included if we are already in a popup
        iframe = '' if popup else Iframe.view % (dright, url('close'))
        # Define variables, per popup
        vars = (
         # global Javascript variables
         class_.getVariables(tool),
         # confirmActionPopup
         dleft, _('yes'), _('no'),
         # uploadPopup
         tool.url, _('object_save'), _('object_cancel'),
         # alertPopup
         url('warningBig'), dleft, _('appy_ok'),
         # iframePopup
         iframe
        )
        return class_.popups % vars

    # Forms must be present on some pages, like view, edit and search.
    # Global Javascript message are also defined here.
    forms = '''
     <!-- Global form for editing entries within an object's history -->
     <form id="eventForm" method="post" action="">
      <input type="hidden" name="objectId"/>
      <input type="hidden" name="eventTime"/>
      <input type="hidden" name="comment"/>
     </form>
     <!-- Global form for unlocking a page -->
     <form id="unlockForm" method="post" action="do">
      <input type="hidden" name="action" value="Unlock"/>
      <input type="hidden" name="objectUid"/>
      <input type="hidden" name="pageName"/>
     </form>
     <!-- Global form for generating/freezing a document from a pod template -->
     <form id="podForm" name="podForm" method="post" target="appyIFrame"
           action="%s/doPod">
      <input type="hidden" name="objectUid"/>
      <input type="hidden" name="fieldName"/>
      <input type="hidden" name="template"/>
      <input type="hidden" name="podFormat"/>
      <input type="hidden" name="queryData"/>
      <input type="hidden" name="criteria"/>
      <input type="hidden" name="customParams"/>
      <input type="hidden" name="showSubTitles" value="True"/>
      <input type="hidden" name="checkedIds"/>
      <input type="hidden" name="checkedSem"/>
      <input type="hidden" name="mailing"/>
      <input type="hidden" name="mailText"/>
      <input type="hidden" name="action" value="generate"/>
     </form>'''

    @classmethod
    def getForms(class_, tool):
        '''Returns the forms to include in most pages, as well as translated
           Javascript messages.'''
        return class_.forms % tool.url

    @classmethod
    def getScripts(class_, tool, q, layout):
        '''Get the scripts that must be run on most pages'''
        return '<script>initSlaves(%s,%s)</script>' % (q(tool.url), q(layout))
#- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
