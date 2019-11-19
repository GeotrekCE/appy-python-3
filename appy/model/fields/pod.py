# ~license~
# ------------------------------------------------------------------------------
import time, os, os.path
from appy.px import Px

from appy.model.utils import Object
from appy.model.fields import Field
from appy.pod.renderer import Renderer
from appy.ui.layout import Layouts, Layout
from appy.model.fields.file import FileInfo
from appy.pod import PodError, styles_manager
from appy.utils.string import produceNiceMessage
from appy.utils.path import resolvePath, getOsTempFolder

# Error messages ---------------------------------------------------------------
POD_ERROR = 'An error occurred while generating the document. Please contact ' \
  'the system administrator.'
NO_TEMPLATE = 'Please specify a pod template in field "template".'
UNAUTHORIZED = 'You are not allowed to perform this action.'
TEMPLATE_NOT_FOUND = 'Template not found at %s.'
FREEZE_ERROR = 'Error while trying to freeze a "%s" file in pod field "%s" ' \
  '(%s).'
FREEZE_FATAL_ERROR = 'Server error. Please contact the administrator.'
RENDERED = "pod %s:%s (%s) rendered in %.2fsec."

# ------------------------------------------------------------------------------
class Mailing:
    '''Represents a mailing list as can be used by a pod field (see below)'''
    def __init__(self, id, name=None, logins=None, subject=None, body=None):
        # The mailing list ID, an element among available mailings as defined in
        # Pod.mailing.
        self.id = id
        # The mailing list name, as shown in the user interface
        self.name = name
        # The list of logins that will be used as recipients for sending
        # emails.
        self.logins = logins
        # The mail subject
        self.subject = subject
        # The mail body
        self.body = body

    def complete(self, field, obj, template, mailing, mailText, forUi):
        '''Complete the mailing information'''
        _ = obj.translate
        tool = obj.tool.o
        # Guess the name from the ID if no name is defined
        self.name = self.name or produceNiceMessage(self.id)
        mapping = None
        # Compute the mail subject when absent
        if not self.subject:
            # Give a predefined subject
            mapping = {'site': tool.getSiteUrl(),
                       'title':  obj.getValue('title', formatted='shown'),
                       'template': field.getTemplateName(obj, template)}
            self.subject = _('podmail_subject', mapping=mapping)
        if forUi:
            self.subject = '<b>%s</b>: %s</br/>' % \
                           (_('email_subject'), self.subject)
        # Compute the mail body when absent
        self.body = self.body or mailText
        if not self.body:
            # Give a predefined body
            if not mapping: mapping = {'site': tool.getSiteUrl()}
            fmt = forUi and 'html' or 'text'
            self.body = _('podmail_body', mapping=mapping, format=fmt)

    def getConfirmLabel(self, _):
        '''We misuse the "confirm" popup to allow the user to modify the mail
           body in its "comment" field. We misuse this field's label to
           integrate the mail subject in it (so the user can see it). This
           method returns this "label".'''
        return '%s<br/><b>%s</b>' % (self.subject, _('email_body'))

# ------------------------------------------------------------------------------
class Pod(Field):
    '''A pod is a field allowing to produce a (PDF, ODT, Word, RTF...) document
       from data contained in Appy class and linked objects or anything you
       want to put in it. It is the way gen uses pod.'''
    # Make some useful classes accessible here
    TableProperties = styles_manager.TableProperties
    BulletedProperties = styles_manager.BulletedProperties
    NumberedProperties = styles_manager.NumberedProperties

    allFormats = {'.odt': ('pdf', 'docx', 'odt'), '.ods': ('xlsx', 'ods')}

    # Getting a pod value is something special: disable the standard Appy
    # machinery for this.
    customGetValue = True

    class Layouts(Layouts):
        '''Pod-specific layouts'''
        # Right-aligned layouts, convenient for pod fields exporting search
        # results or multi-template pod fields.
        r = Layouts(view=Layout('fl!', css_class='podTable')) # "r"ight
        l = Layouts(view= Layout('fl;', css_class='podTable')) # "l"eft
        # "r"ight "m"ulti-template (where the global field label is not used)
        rm = Layouts(view=Layout('f!', css_class='podTable'))

    # Icon allowing to generate a given template in a given format
    pxIcon = Px('''
     <img var="iconSuffix=frozen and 'Frozen' or '';
               iconId=field.getIconId(confirm, uid, info, fmt);
               iconGetter=confirm and ('getNode(%s)'%q(iconId)) or 'this';
               js='generatePod(%s,%s,%s,%s,%s,%s,null,%s)' % \
                (iconGetter, q(uid), q(name), q(info.template), q(fmt), \
                 q(field.getSearchParams(req, layout)), gc)"
          src=":url(fmt + iconSuffix)" class="clickable" id=":iconId"
          title=":field.getIconTitle(obj, fmt, frozen)"
          onclick=":confirm and 'askConfirm(%s,%s,%s)' % (q('script'), \
            q(js,False), field.labelId) or js"/>''')

    view = cell = Px('''
     <script if="field.confirm">::field.getJsConfirmVar(obj)</script>
     <x var="uid=obj.id;
             gc=field.getCheckHook(obj, req)"
        for="info in field.getVisibleTemplates(obj)"
        var2="mailings=field.getVisibleMailings(obj, info.template);
              lineBreak=((loop.info.nb + 1) % field.maxPerRow) == 0;
              confirm=field.getConfirm(obj, info.template)">
      <x for="fmt in info.formats"
         var2="freezeAllowed=(fmt in info.freezeFormats) and \
                             (field.show != 'result');
               hasMailings=mailings and (fmt in mailings);
               dropdownEnabled=freezeAllowed or hasMailings;
               frozen=fmt in info.frozenFormats">
       <!-- A clickable icon if no freeze action is allowed and no mailing is
            available for this format -->
       <x if="not dropdownEnabled">:field.pxIcon</x>
       <!-- A clickable icon and a dropdown menu else -->
       <span if="dropdownEnabled" class="dropdownMenu"
             onmouseover="toggleDropdown(this)"
             onmouseout="toggleDropdown(this,'none')">
        <x>:field.pxIcon</x>
        <!-- The dropdown menu containing freeze actions -->
        <table class="dropdown" width="110px">
         <!-- Unfreeze -->
         <tr if="freezeAllowed and frozen" valign="top">
          <td width="95px">
           <a onclick=":'freezePod(%s,%s,%s,%s,%s)' % (q(uid), q(name), \
                        q(info.template), q(fmt), q('unfreeze'))"
              class="smaller">:_('unfreezeField')</a>
          </td>
          <td width="15px"><img src=":url('unfreeze')"/></td>
         </tr>
         <!-- (Re-)freeze -->
         <tr if="freezeAllowed" valign="top">
          <td width="85px">
           <a onclick=":'freezePod(%s,%s,%s,%s,%s)' % (q(uid), q(name), \
                        q(info.template), q(fmt), q('freeze'))"
              class="smaller">:_('freezeField')</a>
          </td>
          <td width="15px"><img src=":url('freeze')"/></td>
         </tr>
         <!-- (Re-)upload -->
         <tr if="freezeAllowed" valign="top">
          <td width="85px">
           <a onclick=":'uploadPod(%s,%s,%s,%s)' % (q(uid), q(name), \
                        q(info.template), q(fmt))"
              class="smaller">:_('uploadField')</a>
          </td>
          <td width="15px"><img src=":url('upload')"/></td>
         </tr>
         <!-- Mailing lists -->
         <x if="hasMailings" var2="sendLabel=_('email_send')">
          <tr for="mailing in mailings[fmt]" valign="top"
              var2="mInfo=field.getMailingInfo(obj, info.template, mailing,
                                               None, forUi=True)">
           <td colspan="2">
            <a var="js='generatePod(this,%s,%s,%s,%s,%s,null,%s,%s,comment)' % \
                       (q(uid), q(name), q(info.template), q(fmt), \
                        q(field.getSearchParams(req, layout)), gc, q(mailing))"
               onclick=":'askConfirm(%s,%s,null,true,400,%s,%s,6)' % \
                          (q('script'), q(js,False), \
                           q(mInfo.getConfirmLabel(_)), q(mInfo.body))"
               title=":sendLabel">
             <img src=":url('email')" align="left" style="margin-right: 2px"/>
             <x>:mInfo.name</x></a>
            </td>
          </tr>
         </x>
        </table>
       </span>
      </x>
      <!-- Show the specific template name only if there is more than one
           template. For a single template, the field label already does the
           job. -->
      <span if="field.useTemplateName"
        class=":(not loop.info.last and not lineBreak) and 'pod smaller' \
         or 'podLast smaller'">:field.getTemplateName(obj, info.template)</span>
      <br if="lineBreak"/>
     </x>''')

    edit = search = ''

    def __init__(self, validator=None, show=('view', 'result'), page='main',
      group=None, layouts=None, move=0, readPermission='read',
      writePermission='write', width=None, height=None, maxChars=None,
      colspan=1, master=None, masterValue=None, focus=False, historized=False,
      mapping=None, generateLabel=None, label=None, template=None,
      templateName=None, useTemplateName=None, showTemplate=None,
      freezeTemplate=None, showFrozenOnly=True, maxPerRow=5, context=None,
      stylesMapping={}, formats=None, getChecked=None, mailing=None,
      mailingName=None, showMailing=None, mailingInfo=None, view=None,
      cell=None, edit=None, xml=None, translations=None, downloadName=None,
      downloadDisposition='attachment', forceOoCall=False, forceLoad=False,
      optimalColumnWidths=False, distributeColumns=None, script=None,
      pdfOptions='ExportNotes=True', confirm=False, raiseOnError=False,
      action=None, beforeAction=None):
        # Param "template" stores the path to the pod template(s). If there is
        # a single template, a string is expected. Else, a list or tuple of
        # strings is expected. Every such path must be relative to your
        # application. A pod template name Test.odt that is stored at the root
        # of your app will be referred as "Test.odt" in self.template. If it is
        # stored within sub-folder "pod", it will be referred as "pod/Test.odt".
        if not template: raise Exception(NO_TEMPLATE)
        if isinstance(template, str):
            self.template = [template]
        elif isinstance(template, tuple):
            self.template = list(template)
        else:
            self.template = template
        # Param "templateName", if specified, is a method that will be called
        # with the current template (from self.template) as single arg and must
        # return the name of this template. If self.template stores a single
        # template, you have no need to use param "templateName". Simply use the
        # field label to name the template. But if you have a multi-pod field
        # (with several templates specified as a list or tuple in param
        # "template"), you will probably choose to hide the field label and use
        # param "templateName" to give a specific name to every template. If
        # "template" contains several templates and "templateName" is None, Appy
        # will produce names from template filenames.
        self.templateName = templateName
        # If you want to use "templateName" hereabove even if self.template
        # contains a single template, set "usetTemplateName" to True.
        if useTemplateName == None:
            self.useTemplateName = len(self.template) > 1
        else:
            self.useTemplateName = useTemplateName
        # "showTemplate" determines if the current user may generate documents
        # based on this pod field. More precisely, "showTemplate", if specified,
        # must be a method that will be called with the current template as
        # single arg (one among self.template) and that must return the list or
        # tuple of formats that the current user may use as output formats for
        # generating a document. If the current user is not allowed at all to
        # generate documents based on the current template, "showTemplate" must
        # return an empty tuple/list. If "showTemplate" is not specified, the
        # user will be able to generate documents based on the current template,
        # in any format from self.formats (see below).
        # "showTemplate" comes in addition to self.show. self.show dictates the
        # visibility of the whole field (ie, all templates from self.template)
        # while "showTemplate" dictates the visiblity of a specific template
        # within self.template.
        self.showTemplate = showTemplate
        # "freezeTemplate" determines if the current user may freeze documents
        # normally generated dynamically from this pod field. More precisely,
        # "freezeTemplate", if specified, must be a method that will be called
        # with the current template as single arg and must return the (possibly
        # empty) list or tuple of formats the current user may freeze. The
        # "freezing-related actions" that are granted by "freezeTemplate" are
        # the following. When no document is frozen yet for a given
        # template/format, the user may:
        # - freeze the document: pod will be called to produce a document from
        #   the current database content and will store it in the database.
        #   Subsequent user requests for this pod field will return the frozen
        #   doc instead of generating on-the-fly documents;
        # - upload a document: the user will be able to upload a document that
        #   will be stored in the database. Subsequent user requests for this
        #   pod field will return this doc instead of generating on-the-fly
        #   documents.
        # When a document is already frozen or uploaded for a given
        # template/format, the user may:
        # - unfreeze the document: the frozen or uploaded document will be
        #   deleted from the database and subsequent user requests for the pod
        #   field will again generate on-the-fly documents;
        # - re-freeze the document: the frozen or uploaded document will be
        #   deleted, a new document will be generated from the current database
        #   content and will be frozen as a replacement to the deleted one;
        # - upload a document: the frozen or uploaded document will be replaced
        #   by a new document uploaded by the current user.
        self.freezeTemplate = freezeTemplate
        # If "showFrozenOnly" is True, only formats for which a frozen document
        # exists will be available to the user. This mechanism is used to
        # prevent data from being frozen in one format and being available for
        # real-time computation in another format, which could be incoherent.
        # Note that is has sense (and thus applies) only when there is at least
        # one frozen document. When "showFrozenOnly" is applied, and when there
        # is at least one frozen document, it overrides the list of available
        # formats (as determined by self.showTemplate or self.formats).
        self.showFrozenOnly = showFrozenOnly
        # If p_template contains more than 1 template, "maxPerRow" tells how
        # much templates must appear side by side.
        self.maxPerRow = maxPerRow
        # The context is a dict containing a specific pod context, or a method
        # that returns such a dict.
        self.context = context
        # A global styles mapping that would apply to the whole template(s)
        self.stylesMapping = stylesMapping
        # What are the output formats when generating documents from this pod ?
        self.formats = formats
        if not formats: # Compute default ones
            self.formats = self.getAllFormats(self.template[0])
        # Parameter "getChecked" can specify the name of a Ref field belonging
        # to the same Appy class, or the term "search". If getChecked is...
        # ----------------------------------------------------------------------
        # the name of | The context of the pod template will contain an
        # a Ref field | additional object, named "_checked". On this object, an
        #             | attribute will be set, whose name is the name of the Ref
        #             | field, and whose value will be the list of the objects
        #             | linked via the Ref field that are currently selected in
        #             | the user interface.
        # ----------------------------------------------------------------------
        #   "search"  | The pod context variable "objects", normally containing
        #             | all search results, will only contain objects being
        #             | checked in the user interface.
        # ----------------------------------------------------------------------
        self.getChecked = getChecked
        # Mailing lists can be defined for this pod field. For every visible
        # mailing list, a menu item will be available in the user interface and
        # will allow to send the pod result as attachment to the mailing list
        # recipients. Attribute p_mailing stores a mailing list's id
        # (as a string) or a list of ids.
        self.mailing = mailing
        if isinstance(mailing, str):
            self.mailing = [mailing]
        elif isinstance(mailing, tuple):
            self.mailing = list(mailing)
        # "showMailing" below determines when the mailing list(s) must be shown.
        # It may store a method accepting a mailing list's id (among
        # self.mailing) and a template (among self.template) and returning the
        # list or tuple of formats for which the pod result can be sent to the
        # mailing list. If no such method is defined, the mailing list will be
        # available for all visible templates and formats.
        self.showMailing = showMailing
        # When it it time to send an email (or preview it), "mailingInfo" gives
        # all the necessary information for this email: recipients, subject
        # body. It must be a method accepting 2 args:
        # - "mailing" is the mailing ID (from self.mailing);
        # - "forUi" is a boolean indicating if we must compute mailing info for
        #           displaying it in the user interface (forUi=True) or for
        #           sending the mail (forUi=False). It is important because, if
        #           True (False), you must translate i18n labels with parameter
        #           format="html" (format="text").
        # Displaying info in the user interface allows the user to preview the
        # mail and modify the predefined mail body if necessary. The method must
        # return a Mailing instance (see class hereabove). Note that the
        # returned Mailing instance can be subsequently modified by the
        # framework.
        self.mailingInfo = mailingInfo
        # "downloadName", if specified, is a method that will be called with
        # the current template (from self.template) as single arg and must
        # return the name of the file as the user will get it once he will
        # download the pod result from its browser. This is for people that do
        # not like the default download name. Do not specify any extension: it
        # will be appended automatically. For example, if your method returns
        # "PodResultForSomeObject", and the pod result is a pdf file, the file
        # will be named "PodResultForSomeObject.pdf". If you specify such a
        # method, you have the responsibility to produce a valid,
        # any-OS-and-any-browser-proof file name. For inspiration, see the
        # default m_getDownloadName method hereafter. If you have several
        # templates in self.template, for some of them where you are satisfied
        # with the default download name, return None.
        self.downloadName = downloadName
        # The field below allow to determine the "disposition" when downloading
        # a pod result. "attachment" by default, it can be set to "inline". But
        # with disposition=inline, Google Chrome and IE may launch a PDF viewer
        # that triggers one or many additional crashing HTTP GET requests.
        self.downloadDisposition = downloadDisposition
        # Normally, when you generate a pod result that is in ODT/ODS format,
        # LibreOffice is not called. But if you want it to be called
        # nevertheless, for example to ensure that all the indexes are
        # up-to-date (including the table of contents), set "forceOoCall" to
        # True. When generating pod results in other formats (pdf, doc, xls...),
        # LibreOffice is always called and indexes are always refreshed.
        self.forceOoCall = forceOoCall
        # To ensure that LibreOffice, when called, loads a large document in
        # its entirety, before doing other things like updating its table of
        # contents, set the following attribute to True.
        self.forceLoad = forceLoad
        # For these parameters, see appy.pod.renderer.Renderer's docstring
        self.optimalColumnWidths = optimalColumnWidths
        self.distributeColumns = distributeColumns
        # "script" can be used to customize the process of rendering the POD
        # result via LibreOffice UNO. See option "-s" of appy/pod/converter.py
        # for more information. "script" can hold the absolute path to a Python
        # file or a method that returns it. If you specify a method, it will
        # accept 2 parameters:
        # * template     the name of the current template (important when
        #                multiple templates are in use);
        # * context      the context given to the pod template.
        self.script = script
        # When the result is PDF, options for configuring the production of the
        # PDF file can be given in this attribute (ie, for adding a watermark).
        # More information about available options on class
        # appy.pod.renderer.Renderer, which has an homonym attribute.
        # "pdfOptions" can hold a method as well.
        self.pdfOptions = pdfOptions
        # If "confirm" is True, a popup will be shown before generating the
        # pod result. "confirm" may also hold a method, that must accept, as
        # single arg, the name of the current template (indeed, self.template
        # may hold several templates), and must return a boolean value.
        self.confirm = confirm
        # If "raiseOnError" is False (the default), no error is raised:
        # traceback(s) is (are) dumped into the pod result within note(s). If
        # you prefer a real exception to be raised, set this parameter to True.
        # This could be important if, for example, an action is tied to this pod
        # field: you want it to be completely executed or rolled back.
        self.raiseOnError = raiseOnError
        # If you want some action to be executed after the pod result has been
        # generated, set a method in parameter "action". This must be a method
        # accepting parameters:
        # * template     the name of the current template (important when
        #                multiple templates are in use);
        # * context      the context given to the pod template;
        # * format       the output format.
        self.action = action
        # If you want some action to be executed just before the pod result is
        # generated, set a method in parameter "beforeAction". This method's
        # signature must be the same as for parameter "action" hereabove.
        self.beforeAction = beforeAction
        # Call the base constructor
        Field.__init__(self, None, (0,1), None, None, show, page, group,
          layouts, move, False, True, None, False, readPermission,
          writePermission, width, height, None, colspan, master, masterValue,
          focus, historized, mapping, generateLabel, label, None, None, None,
          None, False, False, view, cell, edit, xml, translations)
        # Param "persist" is False, but actual persistence for this field is
        # determined by freezing.
        self.validable = False

    def getExtension(self, template):
        '''Gets a p_template's extension (".odt" or ".ods"). Because a template
           can simply be a pointer to another template (ie, "Item.odt.variant"),
           the logic for getting the extension is a bit more tricky.'''
        elems = os.path.splitext(template)
        if elems[1] in Pod.allFormats: return elems[1]
        # p_template must be a pointer to another template and has one more
        # extension.
        return os.path.splitext(elems[0])[1]

    def getAllFormats(self, template):
        '''Gets all the output formats that are available for a given
           p_template.'''
        return Pod.allFormats[self.getExtension(template)]

    def setTemplateFolder(self, folder):
        '''This methods adds a prefix to every template name in
           self.template. This can be useful if a plug-in module needs to
           replace an application template by its own templates. Here is an
           example: imagine a base application has a pod field with:
           
           self.templates = ["Item.odt", "Decision.odt"]
           
           The plug-in module, named "PlugInApp", wants to replace it with its
           own templates Item.odt, Decision.odt and Other.odt, stored in its
           sub-folder "pod". Suppose the base pod field is in <podField>. The
           plug-in will write:
           
           <podField>.templates = ["Item.odt", "Decision.odt", "Other.odt"]
           <podField>.setTemplateFolder('../PlugInApp/pod')
           
           The following code is equivalent, will work, but is precisely the
           kind of things we want to avoid.

           <podField>.templates = ["../PlugInApp/pod/Item.odt",
                                   "../PlugInApp/pod/Decision.odt",
                                   "../PlugInApp/pod/Other.odt"]
        '''
        for i in range(len(self.template)):
            self.template[i] = os.path.join(folder, self.template[i])

    def getTemplateName(self, obj, fileName):
        '''Gets the name of a template given its p_fileName'''
        res = None
        if self.templateName:
            # Use the method specified in self.templateName
            res = self.templateName(obj, fileName)
        # Else, deduce a nice name from p_fileName
        if not res:
            name = os.path.splitext(os.path.basename(fileName))[0]
            res = produceNiceMessage(name)
        return res

    def getTemplatePath(self, diskFolder, template):
        '''Return the absolute path to some pod p_template, by prefixing it with
           the application path. p_template can be a pointer to another
           template.'''
        res = resolvePath(os.path.join(diskFolder, template))
        if not os.path.isfile(res):
            raise Exception(TEMPLATE_NOT_FOUND % template)
        # Unwrap the path if the file is simply a pointer to another one
        elems = os.path.splitext(res)
        if elems[1] not in Pod.allFormats:
            res = self.getTemplatePath(diskFolder, elems[0])
        return res

    def getDownloadName(self, obj, template, format, queryRelated):
        '''Gets the name of the pod result as will be seen by the user that will
           download it. Ensure the returned name is not too long for the OS that
           will store the downloaded file with this name.'''
        # Use method self.downloadName if present and if it returns something
        # for p_template
        if self.downloadName:
            name = self.downloadName(obj, template)
            if name: return '%s.%s' % (name, format)
        # Compute the default download name
        norm = obj.tool.normalize
        fileName = norm(self.getTemplateName(obj, template))[:100]
        if not queryRelated:
            # This is a POD for a single object: personalize the file name with
            # the object title.
            title = obj.o.getShownValue('title')
            fileName = '%s-%s' % (norm(title)[:140], fileName)
        return fileName + '.' + format

    def getVisibleTemplates(self, obj):
        '''Returns, among self.template, the template(s) that can be shown'''
        res = []
        if not self.showTemplate:
            # Show them all in the formats specified in self.formats
            for template in self.template:
                res.append(Object(template=template, formats=self.formats,
                            freezeFormats=self.getFreezeFormats(obj, template)))
        else:
            for template in self.template:
                formats = self.showTemplate(obj, template)
                if not formats: continue
                elif isinstance(formats, bool):
                    formats = self.getAllFormats(template)
                elif isinstance(formats, str):
                    formats = (formats,)
                res.append(Object(template=template, formats=formats,
                           freezeFormats=self.getFreezeFormats(obj, template)))
        # Compute the already frozen documents, and update the available formats
        # accordingly when self.showFrozenOnly is True.
        for info in res:
            frozenFormats = []
            for fmt in info.formats:
                if self.isFrozen(obj, info.template, fmt):
                    frozenFormats.append(fmt)
            info.frozenFormats = frozenFormats
            # Replace formats with frozenFormats when relevant
            if frozenFormats and self.showFrozenOnly:
                info.formats = frozenFormats
        return res

    def getVisibleMailings(self, obj, template):
        '''Gets, among self.mailing, the mailing(s) that can be shown for
           p_template, as a dict ~{s_format:[s_id]}~.'''
        if not self.mailing: return
        res = {}
        for mailing in self.mailing:
            # Is this mailing visible ? In which format(s) ?
            if not self.showMailing:
                # By default, the mailing is available in any format
                formats = True
            else:
                formats = self.showMailing(obj, mailing, template)
            if not formats: continue
            if isinstance(formats, bool): formats = self.getAllFormats(template)
            elif isinstance(formats, str): formats = (formats,)
            # Add this mailing to the result
            for fmt in formats:
                if fmt in res: res[fmt].append(mailing)
                else: res[fmt] = [mailing]
        return res

    def getConfirm(self, obj, template):
        '''When producing a result from p_template for p_obj, must we ask a
           confirmation to the user ?'''
        confirm = self.confirm
        if not callable(confirm): return confirm
        return confirm(obj, template)

    def getCheckHook(self, o, req):
        '''If p_self.getChecked is in use, return the ID of the DOM node
           containing the list of (un)checked objects.'''
        gc = self.getChecked
        if not gc:
            r = 'null'
        elif gc == 'search':
            r = req.get('search')
            r = r and ('"%s"' % r) or 'null'
        else:
            if o.allows(o.getField(gc).readPermission):
                r = '"%s_%s"' % (o.id, gc)
            else:
                r = 'null'
        return r

    def getIconId(self, confirm, objectId, info, fmt):
        '''Returns an identifier for an icon allowing to trigger a pod. This
           identifier is long and is not needed when p_confirm is False.'''
        if not confirm: return ''
        return '%s_%s_%s_%s' % (objectId, self.name,
                                sutils.normalizeString(info.template), fmt)

    def getMailingInfo(self, obj, template, mailing, mailText, forUi=False):
        '''Gets the necessary information for sending an email to p_mailing
           list, or for getting this info for displaying it in the user
           interface if p_forUi is True.'''
        r = self.mailingInfo(obj, mailing, forUi)
        r.complete(self, obj, template, mailing, mailText, forUi)
        return r

    def sendMailing(self, obj, template, mailing, mailText, attachment):
        '''Sends the emails for m_mailing'''
        info = self.getMailingInfo(obj, template, mailing, mailText)
        if not info.logins:
            obj.log('mailing %s contains no recipient.' % mailing)
            return 'action_ko'
        tool = obj.tool
        # Collect logins corresponding to inexistent users and recipients
        missing = []
        recipients = []
        for login in info.logins:
            user = tool.search1('User', noSecurity=True, login=login)
            if not user:
                missing.append(login)
                continue
            else:
                recipient = user.getMailRecipient()
                if not recipient:
                    missing.append(login)
                else:
                    recipients.append(recipient)
        if missing:
            obj.log('mailing %s: inexistent user or no email for %s.' % \
                    (mailing, str(missing)))
        if not recipients:
            obj.log('mailing %s contains no recipient (after removing wrong ' \
                    'entries, see above).' % mailing)
            msg = 'action_ko'
        else:
            tool.sendMail(recipients, info.subject, info.body, [attachment])
            msg = 'action_done'
        return msg

    def getValue(self, obj, name=None, layout=None, template=None, format=None,
      result=None, queryData=None, computeCustomContext=None, noSecurity=False,
      executeAction=True):
        '''For a pod field, getting its value means computing a pod document or
           returning a frozen one. A pod field differs from other field types
           because there can be several ways to produce the field value (ie:
           self.template can hold various templates; output file format can be
           odt, pdf,.... We get those precisions about the way to produce the
           file, either from params, or from default values.
           * p_template is the specific template, among self.template, that must
             be used as base for generating the document;
           * p_format is the output format of the resulting document;
           * p_result, if given, must be the absolute path of the document that
             will be computed by pod. If not given, pod will produce a doc in
             the OS temp folder;
           * if the pod document is related to a query, the query parameters
             needed to re-trigger the query are given in p_queryData, and, if it
             is a custom search, criteria are in the request, at key "criteria";
           * if p_computeCustomContext is True, this special context will be
             computed (see m_setCustomContext) and will override any other
             value available in the context, including values from the
             field-specific context.
        '''
        start = time.time()
        obj = obj.appy()
        template = template or self.template[0]
        format = format or 'pdf'
        # Security check
        if not noSecurity and not queryData:
            if self.showTemplate and not self.showTemplate(obj, template):
                raise Exception(UNAUTHORIZED)
        # Return the possibly frozen document (not applicable for query-related
        # pods).
        if not queryData:
            frozen = self.isFrozen(obj, template, format)
            if frozen:
                fileName = self.getDownloadName(obj, template, format, False)
                return FileInfo(frozen, inDb=False, uploadName=fileName)
        # We must call pod to compute a pod document from "template"
        tool = obj.tool
        ztool = tool.o
        diskFolder = tool.getDiskFolder()
        # Get the path to the pod template
        templatePath = self.getTemplatePath(diskFolder, template)
        # Get or compute the specific POD context
        specificContext = self.getAttribute(obj, 'context')
        # Compute the name of the result file
        if not result:
            result = '%s/%s_%f.%s' % (getOsTempFolder(), obj.id, time.time(),
                                      format)
        # Define parameters to give to the appy.pod renderer
        req = tool.request
        podContext = {'tool': tool, 'user': obj.user, 'self': obj, 'field':self,
                      'now': ztool.getProductConfig().DateTime(),
                      '_': obj.translate, 'projectFolder': diskFolder,
                      'template': template, 'request': req}
        # If the pod document is related to a search, re-trigger it and put the
        # result in the pod context.
        if queryData:
            podContext['objects'] = self.getSearchResults(tool, queryData)
            podContext['queryData'] = queryData.split(':')
        # Add the field-specific context if present
        if specificContext: podContext.update(specificContext)
        # Add the custom context when required
        if computeCustomContext:
            self.setCustomContext(podContext, obj, req)
        # Variable "_checked" can be expected by a template but absent (ie,
        # when generating frozen documents).
        if '_checked' not in podContext: podContext['_checked'] = Object()
        # Define a potential global styles mapping
        if callable(self.stylesMapping):
            stylesMapping = self.callMethod(obj, self.stylesMapping)
        else:
            stylesMapping = self.stylesMapping
        # Execute the "before" action when relevant
        if executeAction and self.beforeAction:
            self.beforeAction(obj, template, podContext, format)
        # Get the optional script to give to the renderer
        script = self.script
        if callable(script): script = script(obj, template, podContext)
        # Compute PDF options
        if callable(self.pdfOptions):
            pdfOptions = self.pdfOptions(obj, template)
        else:
            pdfOptions = self.pdfOptions
        # Compute the renderer's parameters
        rendererParams = {'template': templatePath, 'context': podContext,
          'result': result, 'stylesMapping': stylesMapping,
          'imageResolver': ztool.getApp(), 'overwriteExisting': True,
          'forceOoCall': self.forceOoCall, 'forceLoad': self.forceLoad,
          'raiseOnError': self.raiseOnError,
          'optimalColumnWidths': self.optimalColumnWidths,
          'distributeColumns': self.distributeColumns, 'script': script,
          'pdfOptions': pdfOptions}
        cfg = ztool.getProductConfig(True)
        if cfg.unoEnabledPython:
            rendererParams['pythonWithUnoPath'] = cfg.unoEnabledPython
        if cfg.libreOfficePort:
            rendererParams['ooPort'] = cfg.libreOfficePort
        # Launch the renderer
        try:
            renderer = Renderer(**rendererParams)
            renderer.run()
        except PodError as pe:
            if not os.path.exists(result):
                # In some (most?) cases, when OO returns an error, the result is
                # nevertheless generated.
                obj.log(str(pe).strip(), type='error')
                return POD_ERROR
        # Give a friendly name for this file
        fileName = self.getDownloadName(obj, template, format, queryData)
        # Execute the tied action when relevant
        if executeAction and self.action:
            self.action(obj, template, podContext, format)
        # Log the successfull rendering
        obj.log(RENDERED % (obj.id, self.name, fileName, time.time()-start))
        # Get a FileInfo instance to manipulate the file on the filesystem
        return FileInfo(result, inDb=False, uploadName=fileName)

    def getBaseName(self, template=None):
        '''Gets the "base name" of p_template (or self.template[0] if not
           given). The base name is the name of the template, without path
           and extension. Moreover, if the template is a pointer to another one
           (ie Item.odt.something), the base name integrates the specific
           extension. In the example, the base name will be "ItemSomething".'''
        template = template or self.template[0]
        elems = os.path.splitext(os.path.basename(template))
        if elems[1] in ('.odt', '.ods'):
            res = elems[0] # Item.odt > Item
        else:
            # Item.odt.something > ItemSomething
            res = os.path.splitext(elems[0])[0] + elems[1][1:].capitalize()
        return res

    def getFreezeName(self, template=None, format='pdf', sep='.'):
        '''Gets the name on disk on the frozen document corresponding to this
           pod field, p_template and p_format.'''
        return '%s_%s%s%s' % (self.name,self.getBaseName(template),sep,format)

    def isFrozen(self, obj, template=None, format='pdf'):
        '''Is there a frozen document for thid pod field, on p_obj, for
           p_template in p_format? If yes, it returns the absolute path to the
           frozen doc.'''
        template = template or self.template[0]
        dbFolder, folder = obj.o.getFsFolder()
        fileName = self.getFreezeName(template, format)
        res = os.path.join(dbFolder, folder, fileName)
        if os.path.exists(res): return res

    def freeze(self, obj, template=None, format='pdf', noSecurity=True,
               upload=None, freezeOdtOnError=True):
        '''Freezes, on p_obj, a document for this pod field, for p_template in
           p_format. If p_noSecurity is True, the security check, based on
           self.freezeTemplate, is bypassed. If no p_upload file is specified,
           we re-compute a pod document on-the-fly and we freeze this document.
           Else, we store the uploaded file.
           
           If p_freezeOdtOnError is True and format is not "odt" (has only sense
           when no p_upload file is specified), if the freezing fails we try to
           freeze the odt version, which is more robust because it does not
           require calling LibreOffice.'''
        # Security check
        if not noSecurity and \
           (format not in self.getFreezeFormats(obj, template)):
            raise Exception(UNAUTHORIZED)
        # Compute the absolute path where to store the frozen document in the
        # database.
        dbFolder, folder = obj.o.getFsFolder(create=True)
        fileName = self.getFreezeName(template, format)
        result = os.path.join(dbFolder, folder, fileName)
        if os.path.exists(result):
            prefix = upload and 'freeze (upload)' or 'freeze'
            obj.log('%s: overwriting %s...' % (prefix, result))
            os.remove(result)
        if not upload:
            # Generate the document
            doc = self.getValue(obj, template=template, format=format,
                                result=result)
            if isinstance(doc, str):
                # An error occurred, the document was not generated.
                obj.log(FREEZE_ERROR % (format, self.name, doc), type='error')
                if not freezeOdtOnError or (format == 'odt'):
                    raise Exception(FREEZE_FATAL_ERROR)
                obj.log('freezing the ODT version...')
                # Freeze the ODT version of the document, which does not require
                # to call LibreOffice: the risk of error is smaller.
                fileName = self.getFreezeName(template, 'odt')
                result = os.path.join(dbFolder, folder, fileName)
                if os.path.exists(result):
                    obj.log('freeze: overwriting %s...' % result)
                doc = self.getValue(obj, template=template, format='odt',
                                    result=result)
                if isinstance(doc, str):
                    self.log(FREEZE_ERROR % ('odt', self.name, doc),
                             type='error')
                    raise Exception(FREEZE_FATAL_ERROR)
                obj.log('freezed at %s.' % result)
        else:
            # Store the uploaded file in the database
            f = open(result, 'wb')
            doc = FileInfo(result, inDb=False)
            doc.replicateFile(upload, f)
            f.close()
        return doc

    def unfreeze(self, obj, template=None, format='pdf', noSecurity=True):
        '''Unfreezes, on p_obj, the document for this pod field, for p_template
           in p_format.'''
        # Security check
        if not noSecurity and \
           (format not in self.getFreezeFormats(obj, template)):
            raise Exception(UNAUTHORIZED)
        # Compute the absolute path to the frozen doc
        dbFolder, folder = obj.o.getFsFolder()
        fileName = self.getFreezeName(template, format)
        frozenName = os.path.join(dbFolder, folder, fileName)
        if os.path.exists(frozenName):
            os.remove(frozenName)
            obj.log('removed (unfrozen) %s.' % frozenName)

    def getFreezeFormats(self, obj, template=None):
        '''What are the formats into which the current user may freeze
           p_template?'''
        # One may have the right to edit the field to freeze anything in it
        if not obj.o.mayEdit(self.writePermission): return ()
        template = template or self.template[0]
        # Users (managers included) can perform freeze actions depending on
        # self.freezeTemplate.
        if not self.freezeTemplate: return ()
        r = self.freezeTemplate(obj, template)
        if not r:
            return () # Ensure the result is a tuple
        elif r == True:
            return self.getAllFormats(template)
        else:
            return r

    def getIconTitle(self, obj, format, frozen):
        '''Get the title of the format icon'''
        res = obj.translate(format)
        if frozen:
            res += ' (%s)' % obj.translate('frozen')
        return res

    def setCustomContext(self, context, o, req):
        '''Before calling pod to compute a result, if specific elements must be
           added to the p_context, compute it here. This request-dependent
           method is not called when computing a pod field for freezing it into
           the database.'''
        # Get potential custom params from the request. Custom params must be
        # coded as a string containing a valid Python dict.
        params = req.customParams
        if params:
            context.update(eval(params))
        # Compute the checked objects when relevant
        gc = self.getChecked
        if not gc: return
        # Manage a Ref field
        if gc != 'search':
            # Get the IDs specified in the request
            ids, unchecked = self.getCheckedInfo(req)
            objects = []
            tool = o.tool
            for id in o.ids(gc):
                if unchecked: condition = id not in ids
                else:         condition = id in ids
                if condition:
                    tied = tool.getObject(id)
                    if tied.allows('read'): objects.append(tied)
            context['_checked'] = Object()
            setattr(context['_checked'], gc, objects)
        # Manage a search. All search results are in p_context['objects'].
        else:
            self.keepCheckedResults(req, context['objects'])

    def resetPodCookie(self, req):
        '''Reset the "pod download" cookie indicating that the pod download as
           ended (successfully or not).'''
        req.RESPONSE.setCookie('podDownload', 'true', path='/')

    def onUiRequest(self, obj, rq):
        '''This method is called when an action tied to this pod field
           (generate, freeze, upload...) is triggered from the user
           interface.'''
        # What is the action to perform ?
        action = rq.get('action', 'generate')
        # Security check
        zobj = obj.o
        zobj.mayView(self.readPermission, raiseError=True)
        # Perform the requested action
        template = rq.get('template')
        format = rq.get('podFormat')
        if action == 'generate':
            mailing = rq.get('mailing')
            # Generate a (or get a frozen) document
            res = self.getValue(obj, template=template, format=format,
                              queryData=rq.queryData, computeCustomContext=True)
            if isinstance(res, str):
                # An error has occurred, and p_res contains the error message
                obj.say(res)
                if not mailing: self.resetPodCookie(rq)
                return zobj.goto(zobj.getReferer())
            # res contains a FileInfo instance.
            # Must we return the res to the ui or send a mail with the res as
            # attachment?
            if not mailing:
                self.resetPodCookie(rq)
                resp = rq.RESPONSE
                res.writeResponse(resp, disposition=self.downloadDisposition)
                return
            else:
                # Send the email(s)
                mailText = rq.get('mailText')
                msg = self.sendMailing(obj, template, mailing, mailText, res)
                obj.say(obj.translate(msg))
                return zobj.goto(zobj.getReferer())
        # Performing any other action requires write access to p_obj
        obj.o.mayEdit(self.writePermission, raiseError=True)
        msg = 'action_done'
        if action == 'freeze':
            # (Re-)freeze a document in the database
            self.freeze(obj, template, format, noSecurity=False,
                        freezeOdtOnError=False)
        elif action == 'unfreeze':
            # Unfreeze a document in the database
            self.unfreeze(obj, template, format, noSecurity=False)
        elif action == 'upload':
            # Ensure a file from the correct type has been uploaded
            upload = rq.get('uploadedFile')
            if not upload or not upload.filename or \
               not upload.filename.endswith('.%s' % format):
                # A wrong file has been uploaded (or no file at all)
                msg = 'upload_invalid'
            else:
                # Store the uploaded file in the database
                self.freeze(obj, template, format, noSecurity=False,
                            upload=upload)
        # Return a message to the user interface
        obj.say(obj.translate(msg))
        return zobj.goto(zobj.getReferer())

    def getJsConfirmVar(self, obj):
        '''Gets the Javascript variable definition for storing the specific
           confirmation message to show when self.confirm is not False.'''
        prefix = self.labelId
        return 'var %s = "%s";' % (prefix, obj.translate('%s_confirm' % prefix))
# ------------------------------------------------------------------------------
