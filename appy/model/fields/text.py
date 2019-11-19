# -*- coding: utf-8 -*-
# ~license~

# ------------------------------------------------------------------------------
import re

from appy.px import Px
from appy.utils import flipDict
from appy.ui.layout import Layouts
from appy.model.fields import Field
from appy.utils import string as sutils
from appy.ui.layout import Layouts, Layout
from appy.model.fields.multilingual import Multilingual

# ------------------------------------------------------------------------------
class Replacements:
    '''Used by class Text2Html below, this class is used to define replacements
       for characters found in structured text, in order to recreate formatting
       from structured text written with some conventions.'''
    # Default replacement conventions
    default = {
      # Replace double quotes by "guillemets" (angle quotes). The sub-dict has
      # this meaning: if the previous char is a space (or if there is no
      # previous char), the double quote will be replaced with an opening
      # guillemet; else (special key "0"), it will be replaced by a closing
      # guillemet. The guillemet is flanked by a non-breakable space.
      '"': {' ': '« ', '': '« ', 0: ' »'},
      # Conventions for bold, italic and highlighting
      '[': '<b>', ']': '</b>',
      '<': '<i>', '>': '</i>',
      '{': '<span style="background-color: yellow">', '}': '</span>',
      '&': '&amp;' # XML escaping
    }
    # Among "default", some keys represent opening and ending delimiters
    delimiters = {'[': ']', '<': '>', '{': '}'}
    endDelimiters = flipDict(delimiters)
    # Prefix (semi)colons, question and exclamation marks with a non-breakable
    # space, excepted if such a space is already present.
    nbspChars = (':', ';', '!', '?', '%')
    for c in nbspChars:
        default[c] = {' ': c, 0: ' %s' % c}
    whitespace = (' ', ' ')
    # Regular expression for replacing special markers (see "replacementFun"
    # attribute below.
    regex = re.compile('\*(.+?)\*')

    def __init__(self, replacements=None):
        # Apply custom replacements (if any). In order to disable a default
        # replacement, add it in p_replacement with a "None" value.
        if replacements:
            self.replacements = Replacements.default.copy()
            self.replacements.update(replacements)
        else:
            self.replacements = Replacements.default

    def getReplacementFor(self, char, previous):
        '''Return the replacement char for p_char. p_previous is the previous
           char encountered before p_char.'''
        r = self.replacements[char]
        if not isinstance(r, basestring):
            # The replacement depends on "previous"
            if previous in r:
                r = r[previous]
            else:
                r = r[0]
        return r

    def applyOn(self, text, fun=None, toReopen=None):
        '''Apply replacements on p_text and return a tuple
                           (s_result, [s_toReopen])
        '''
        # ----------------------------------------------------------------------
        #  s_result  | Is the resulting unicode string, whose special chars have
        #            | been replaced with their replacements.
        # ----------------------------------------------------------------------
        # [toReopen] | Among special chars to replace, there are opening and
        #            | ending chars, used as delimiters for applying style, ie,
        #            | bold and italic. After having processed p_text, for some
        #            | opening delimiters, we may not have encountered their
        #            | corresponding ending delimiter. If it occurs, in order to
        #            | produce a valid output, we will nevertheless dump, in
        #            | p_result, the replacements chars corresponding to the
        #            | missing ending delimiters. In that case, [toReopen] will
        #            | contain the list of these opening delimiters. This will
        #            | allow the caller be conscious of this fact, and, the next
        #            | time he will call us in order to dump a subsequent chunk
        #            | of p_text, he will possibly give us this list of tags
        #            | p_toReopen. Indeed, the real ending delimiters may be
        #            | present in the next p_text.
        # ----------------------------------------------------------------------
        # Ensure p_text is Unicode
        isStr = isinstance(text, str)
        if isStr: text = text.decode('utf-8')
        # Replace special markers when appropriate
        if fun: text = self.regex.sub(fun, text)
        # Build the result as a list
        r = []
        add = r.append
        repls = self.replacements
        delimiters = Replacements.delimiters
        endDelimiters = Replacements.endDelimiters
        previous = '' # The previous word or whitespace char
        # Start by dumping p_toReopen delimiters if any
        stack = toReopen # The stack of currently opened delimiters
        if toReopen:
            for delimiter in toReopen:
                add(self.getReplacementFor(delimiter, None))
        # Dump "normal" p_text
        for char in text:
            if char not in repls:
                # Leave the char untouched in the result
                add(char)
            else:
                # Apply a replacement
                add(self.getReplacementFor(char, previous))
                # Update the stack
                if char in delimiters:
                    if stack is None: stack = []
                    stack.append(char)
                elif (char in endDelimiters) and stack:
                    # We suppose p_text to be well structured and the last
                    # opened delimiter to correspond to this end delimiter. But
                    # we protect ourselves against possible mess and avoid
                    # popping the stack if empty.
                    stack.pop()
            # Update "previous"
            if (char in self.whitespace) or (previous in self.whitespace):
                previous = char
            else:
                previous += char
        # If the stack is not empty, dump corresponding ending delimiters
        if stack:
            i = len(stack) - 1
            while i >= 0:
                add(self.getReplacementFor(delimiters[stack[i]], None))
                i -= 1
        # Join the result to a string
        r = u''.join(r)
        # Encode the result when relevant
        if isStr: r = r.encode('utf-8')
        return r, stack

class Text2Html:
    '''Allows to convert chunk of structured text into XHTML. Some conventions
       apply, ie, rows of text starting with a dash are converted to bulleted
       lists; rows starting with char "|" are considered to be table rows,
       etc.'''
    defaultReplacements = Replacements()

    def __init__(self, p='p', prefix='', replacements='default',
                 replacementsFun=None, preListClass=None, lastLiClass=None):
        # The HTML tag used for representing a paragraph
        self.p = p
        # A chunk of HTML code that could be inserted just after the first
        # opening tag in the result.
        self.prefix = prefix
        # The result, will be a list that'll be joined at the end of the process
        self.res = None
        # If p_replacements is:
        # ----------------------------------------------------------------------
        #   "default"    | A default Replacements instance will be used, in
        #                | order to format text according to some conventions
        #                | (see class hereabove)
        # ----------------------------------------------------------------------
        #   None         | Text replacement is disabled
        # ----------------------------------------------------------------------
        #   an instance  | A Replacements instance containing a set of
        #                | formatting options that may de different from the
        #                | defaults.
        # ----------------------------------------------------------------------
        if replacements == 'default':
            self.replacements = Text2Html.defaultReplacements
        else:
            self.replacements = replacements
        # If a p_fun(ction) is defined, structured p_text can contain special
        # markers of the form
        #                            *<name>*
        # Evertytime such marker is encountered in the text, p_fun will be
        # called, with "name" as unique arg, and must return the replacement
        # text for this name.
        self.replacementsFun = replacementsFun
        # If "preListClass" is specified, it corresponds to a CSS class that
        # will be applied to the paragraph that is positioned just before a list
        # (ol or ul).
        self.preListClass = preListClass
        # If "lastLiClass" is specified, it corresponds to a CSS class that will
        # be applied to the last bullet in a list.
        self.lastLiClass = lastLiClass
        # The list of opened delimiters not closed after the last text converted
        # with replacements (see attribute Replacements.delimiters hereabove).
        self.opened = None

    def add(self, part, suffix='\n'):
        '''Adds some p_part into the result'''
        res = self.res
        wasEmpty = not res
        res.append(part + suffix)
        if wasEmpty and self.prefix:
            # It is time to dump the prefix if specified
            res.append(self.prefix)

    def addTag(self, tag, start=True):
        '''Adds a (starting or ending, depending on p_start) tag to the
           result.'''
        if tag in ('ul', 'ol'):
            # Surround the list by a paragraph. Else, self.prefix could not be
            # rendered.
            if start:
                self.add('<%s>' % self.p, '')
                self.add('<%s>' % tag)
            else:
                self.add('</%s>' % tag, '')
                self.add('</%s>' % self.p)
        else:
            t = not start and '/' or ''
            self.add('<%s%s>' % (t, tag))

    def convertText(self, text):
        '''Converts, within p_text, some chars according to self.replacements
           and return the result. Use p_self.replacementsFun if defined and
           p_useReplacementFun is True.'''
        if not self.replacements: return text
        r, opened = self.replacements.applyOn(text, fun=self.replacementsFun,
                                              toReopen=self.opened)
        # "opened" may contain the list of opened delimiters found in p_text
        # that were not closed within p_text. Remember them in p_self.opened: we
        # will re-open them in the next call to p_converText, because they were
        # automatically closed, in p_text, by m_applyOn hereabove.
        self.opened = opened
        return r

    def applyPreListClass(self):
        '''Apply the CSS class in self.preListClass to the last paragraph in
           self.res.'''
        r = self.res
        if not r: return
        i = len(r) - 1
        while i >= 0:
            if r[i].startswith('<p>'):
                r[i] = '<p class="%s"%s' % (self.preListClass, r[i][2:])
                break
            i -= 1

    def isLast(self, rows, i, elem):
        '''Is row #p_i within p_rows the last to contain some p_elem ?'''
        return (i+1 == len(rows)) or not rows[i+1].startswith(elem)

    def convert(self, s):
        '''Returns the converted chunk of HTML'''
        if not s: return self.prefix
        self.res = []
        inList = False
        inTable = False
        i = 0
        rows = s.split('\n')
        total = len(rows)
        for row in rows:
            if row.startswith('- '):
                # Convert it to a bullet. But are we already in a list ?
                if not inList:
                    # Apply the "prelist" CSS class to the last paragraph
                    if self.preListClass: self.applyPreListClass()
                    self.addTag('ul')
                    inList = True
                # Is this the last bullet ?
                isLast = self.isLast(rows, i, '- ')
                if isLast:
                    start= '<li class="%s">' % self.lastLiClass
                    end = '</li>'
                    inList = False
                else:
                    start = '<li>'
                    end = '</li>'
                self.add('%s%s%s' % (start, self.convertText(row[2:]), end))
                # Add the end list tag when relevant
                if isLast: self.addTag('ul', start=False)
            elif row.startswith('|'):
                # Convert it to a table row. But are we already in a table ?
                if not inTable:
                    self.addTag('table')
                    inTable = True
                # Split the row in cells
                tr = '<tr>'
                tdh = 'td'
                for cell in row.strip('|').split('|'):
                    if cell.startswith('_'):
                        tdh = 'th'
                        cell = cell[1:]
                    tr += '<%s>%s</%s>' % (tdh, self.convertText(cell), tdh)
                tr += '</tr>'
                self.add(tr)
                if self.isLast(rows, i, '|'):
                    self.add('</table>')
                    self.inTable = False
            else:
                self.addTag(self.p)
                # Allow the use of dashes that remain dashes (and are not
                # converted to bullets, as above).
                if row.startswith('-'): row = '- %s' % row[1:]
                self.add('%s</%s>' % (self.convertText(row), self.p))
            i += 1
        # Close the last opened list if any
        if inList: self.addTag('ul', start=False)
        return ''.join(self.res)

# ------------------------------------------------------------------------------
class Icon:
    '''An icon from the toolbar when the Text field is used in "structured"
       mode.'''

    def __init__(self, name, type,
                 label=None, icon=None, data=None, shortcut=None):
        # A short, unique name for the icon
        self.name = name
        # The following type of icons exist. Depending on the type, p_data
        # carries a specific type of information.
        # ----------------------------------------------------------------------
        # p_type      | p_data
        # ----------------------------------------------------------------------
        # "wrapper"   | the icon corresponds to a portion of text that will be
        #             | wrapped around a start and end char. p_data contains 2
        #             | chars: the start and end wrapper chars.
        #             | 
        #             | For example, icon "bold" is of type "wrapper", with data
        #             | being "[]". When applied to selected text "hello", it
        #             | becomes "[hello]".
        # ----------------------------------------------------------------------
        # "char"      | the icon corresponds to a char to insert into the field.
        #             | p_data is the char to insert.
        # ----------------------------------------------------------------------
        # "action"    | the icon corresponds to some action that is not
        #             | necessarily related to the field content. In that case,
        #             | p_data may be None or its sematincs may be specific to
        #             | the action.
        # ----------------------------------------------------------------------
        # "sentences" | a clic on the icon will display a menu containing
        #             | predefined sentences. Selecting one of them will inject
        #             | it in the target field, where the cursor is currently
        #             | set. In that case, p_data must hold the name of a
        #             | method that must exist on the current object. This
        #             | method will be called without arg and must return a list
        #             | of sentences, each one being a string.
        # ----------------------------------------------------------------------
        self.type = type
        # The i18n label for the icon's tooltip. Should include the keyboard
        # shortcut when present. If None, defaults to "icon_<name>"
        self.label = label or ('icon_%s' % name)
        # The name of the icon image on disk. If None, will be computed as
        # "icon_<name>.png".
        self.icon = icon or ('icon_%s' % name)
        # The data related to this icon, as described hereabove
        self.data = data
        # If a keyboard shortcut is tied to the icon, its key code is defined
        # here, as an integer. See JavasScript keycodes, https://keycode.info.
        self.shortcut = shortcut

    def asSentences(self, r, o):
        '''For an icon of type "sentences", wraps the icon into a div allowing
           to hook the sub-div containing the sentences, and add this latter.'''
        # For an icon of type "sentences", add a div containing the sentences
        sentences = []
        for sentence in getattr(o, self.data)():
            div = '<div class="sentence"><a class="clickable" ' \
                  'onclick="injectSentence(this)" title="%s">%s</a></div>' % \
                  (sentence, Px.truncateValue(sentence, width=65))
            sentences.append(div)
        # Add a warning message if no sentence has been found
        if not sentences:
            sentences.append('<div class="legend">%s</div>' % \
                             o.translate('no_sentence'))
        return '<div class="sentenceContainer" ' \
               'onmouseover="toggleDropdown(this) " ' \
               'onmouseout="toggleDropdown(this,\'none\')">%s' \
               '<div class="dropdown" style="display:none; width:350px">' \
               '%s</div></div>' % (r, '\n'.join(sentences))

    def get(self, o):
        '''Returns the HTML chunk representing this icon'''
        shortcut = str(self.shortcut) if self.shortcut else ''
        r = '<img class="icon" src="%s" title="%s" name="%s"' \
            ' onmouseover="switchIconBack(this, true)"' \
            ' onmouseout="switchIconBack(this, false)"' \
            ' data-type="%s" data-data="%s" data-shortcut="%d" ' \
            'onclick="useIcon(this)"/>' % \
             (o.buildUrl(self.icon), o.translate(self.label), self.name,
              self.type, self.data or '', shortcut)
        # Add specific stuff if icon type is "sentences"
        if self.type == 'sentences': r = self.asSentences(r, o)
        return r

# All available icons
Icon.all = [Icon('bold',      'wrapper', data='[]',       shortcut=66),
            Icon('italic',    'wrapper', data='&lt;&gt;', shortcut=73),
            Icon('highlight', 'wrapper', data='{}',       shortcut=72),
            # Non breaking space
            Icon('blank',     'char',    data=' ',        shortcut=32),
            # Non breaking dash
            Icon('dash',      'char',    data='‑',        shortcut=54),
            # Increment the field height by <data>%
            Icon('lengthen',  'action',  data='30',       shortcut=56)]

# ------------------------------------------------------------------------------
class Text(Multilingual, Field):
    '''Field allowing to encode a text made of several paragraphs, implemented
       by a HTML textarea tag.'''
    # Make some classes available here
    Icon = Icon
    Replacements = Replacements
    ToHtml = Text2Html

    class Layouts(Layouts):
        '''Text-specific layouts'''
        b = Layouts(edit='lrv-d-f', view='l-f')
        g = Layouts(edit=Layout('d2-f;rv=', width='99%'),
                    view=Layout('fl', width='99%'))

        @classmethod
        def getDefault(class_, field):
            '''Default layouts for this Text p_field'''
            return class_.g if field.inGrid() else class_.b

    # Default ways to render the field if multilingual
    defaultLanguagesLayouts = {'edit': 'horizontal', 'view': 'vertical'}

    # Unilingual pxView
    viewUni = cellUni = Px('''
     <span if="not value" class="smaller">-</span><x if="value">::value</x>''')

    # The toolbar for structured content
    pxToolbar = Px('''
     <div class="toolbar" id=":tbid|field.name + '_tb'">
      <x for="icon in field.Icon.all">::icon.get(o)</x></div>''',

     css = '''
      .toolbar { height: 24px; margin: 2px 0 }
      .sentenceContainer { position: relative; display: inline }
      .sentence { padding: 3px 0 }
      .icon { padding: 3px; border-width: 1px; border: 1px transparent solid }
      .iconSelected { background-color: #dbdbdb; border-color: #909090 }
     ''',

     js='''
      function getIconsMapping(toolbar) {
        // Gets a mapping containing toolbar icons, keyed by their shortcut
        var r = {}, icons=toolbar.getElementsByClassName('icon');
        for (var i=0; i<icons.length; i++) {
          var icon=icons[i], key=icon.getAttribute('data-shortcut');
          if (key) r[parseInt(key)] = icon;
        }
        return r;
      }
      function linkTextToolbar(toolbarId, target) {
        /* Link the toolbar with its target textarea. Get the target textarea if
           not given in p_target. */
        if (!target) {
          var targetId=_rsplit(toolbarId, '_', 2)[0];
          target = document.getElementById(targetId);
        }
        var toolbar=document.getElementById(toolbarId);
        toolbar['target'] = target;
        target['icons'] = getIconsMapping(toolbar);
      }
      function switchIconBack(icon, selected) {
        icon.className = (selected)? 'icon iconSelected': 'icon';
      }
      function lengthenArea(area, percentage) {
        // Lengthen some text p_area by some p_percentage
        var rate = 1 + (percentage / 100),
            styled = Boolean(area.style.height),
            height = (styled)? parseInt(area.style.height): area.rows;
        // Apply the rate
        height = Math.ceil(height * rate);
        // Reinject the new height to the correct area property
        if (styled) area.style.height = String(height) + 'px';
        else area.rows = height;
      }
      function injectString(area, s) {
        // Inject some p_s(tring) into the text p_area, where the cursor is set
        var text = area.value,
                   start=area.selectionStart;
        area.value = text.substring(0, start) + s + \
                     text.substring(area.selectionEnd, area.value.length);
        area.selectionStart = area.selectionEnd = start +s.length;
        area.focus();
      }
      function useIcon(icon) {
        // Get the linked textarea (if already linked)
        var area = icon.parentNode['target'];
        if (!area) return;
        var type=icon.getAttribute('data-type'),
            data=icon.getAttribute('data-data'),
            selectStart=area.selectionStart,
            selectEnd=area.selectionEnd,
            text=area.value;
        if (type == 'wrapper') {
          // Wrap the selected text within special chars
          area.value = text.substring(0, selectStart) + data[0] + \
                       text.substring(selectStart, selectEnd) + data[1] + \
                       text.substring(selectEnd, area.value.length);
          area.selectionStart = selectStart;
          area.selectionEnd = selectEnd + 2;
          area.focus();
        }
        else if (type == 'char') {
          // Insert a (sequence of) char(s) into the text
          injectString(area, data);
        }
        else if (type == 'action') {
          // Actions
          if (icon.name == 'lengthen') lengthenArea(area, parseInt(data));
        }
      }
      function useShortcut(event, id) {
        if ((event.ctrlKey) && (event.keyCode in event.target['icons'])) {
          // Perform the icon's action
          useIcon(event.target['icons'][event.keyCode]);
          event.preventDefault();
        }
      }
      function injectSentence(atag) {
        var area = atag.parentNode.parentNode.parentNode.parentNode['target'];
        if (!area) return;
        // Inject it
        injectString(area, atag.getAttribute('title'));
      }
     ''')

    # Unilingual edit
    editUni = Px('''
     <x var="tid=not lg and name or '%s_%s' % (name, lg);
             tbid='%s_tb' % tid;
             placeholder=field.getPlaceholder(o)">
      <x if="field.showToolbar()">:field.pxToolbar</x>
      <textarea id=":tid" name=":tid" cols=":field.getTextareaCols()"
       style=":field.getTextareaStyle()" placeholder=":placeholder"
       readonly=":field.isReadonly(o)" onkeydown=":field.onKeyDown(tid)"
       onfocus=":field.onFocus(lg)"
       rows=":field.height">:field.getInputValue(inRequest, requestValue, value)
      </textarea></x>''')

    pxSearch = Px('''
     <input type="text" maxlength=":field.maxChars" size=":field.swidth"
            value=":field.sdefault" name=":widgetName"/>''')

    def __init__(self, validator=None, multiplicity=(0,1), default=None,
      defaultOnEdit=None, show=True, page='main', group=None, layouts=None,
      move=0, indexed=False, mustIndex=True, indexValue=None, searchable=False,
      readPermission='read', writePermission='write', width=60, height=5,
      maxChars=None, colspan=1, master=None, masterValue=None, focus=False,
      historized=False, mapping=None, generateLabel=None, label=None,
      sdefault='', scolspan=1, swidth=None, sheight=None, persist=True,
      inlineEdit=False, view=None, cell=None, edit=None, xml=None,
      translations=None,
      # Specific attributes
      placeholder=None, languages=('en',), languagesLayouts=None,
      structured=False, readonly=False):
        # You can define a placeholder in the following attribute. Please
        # consult the homonym attribute on class String from string.py for more
        # information.
        self.placeholder = placeholder
        # If attribute "structured" is True, the text encoded by your users in
        # the field will implicitly follow some conventions for applying text
        # formatting. A toolbar will be shown and will offer shortcuts allowing
        # to inject formatting marks (or also special chars) into the textarea.
        self.structured = structured
        # If attribute "readonly" is True (or stores a method returning True),
        # the rendered textarea tag, on edit layouts, will have attribute
        # "readonly" set.
        self.readonly = readonly
        # Call the base constructors
        Multilingual.__init__(self, languages, languagesLayouts)
        Field.__init__(self, validator, multiplicity, default, defaultOnEdit,
          show, page, group, layouts, move, indexed, mustIndex, indexValue,
          searchable, readPermission, writePermission, width, height, maxChars,
          colspan, master, masterValue, focus, historized, mapping,
          generateLabel, label, sdefault, scolspan, swidth, sheight, persist,
          inlineEdit, view, cell, edit, xml, translations)
        # Specify a filter PX if the field content is indexed
        if self.indexed: self.filterPx = 'pxFilterText'

    def getTextareaStyle(self):
        '''Get the content of textarea's "style" attribute'''
        # If the width is expressed as a string, the field width must be
        # expressed in attribute "style" (so returned by this method) and not
        # via attribute "cols" (returned by m_getTextareaCols below).
        return 'width:%s' % self.width if isinstance(self.width, str) else ''

    def getTextareaCols(self):
        '''Get the content of textarea's "cols" attribute'''
        # If width is expressed as an integer, it must be set as HTML attribute
        # "cols", and not as CSS attribute "width".
        return self.width if isinstance(self.width, int) else ''

    def showToolbar(self, ignoreInner=False):
        '''Show the toollbar if the field is structured and is not inner. In
           that latter case, the toolbar has already been rendered in the
           container field's headers.'''
        # Never show the tool bar if the field is not structured
        if not self.structured: return
        # Do not show the toolbar if the field is an inner field, provided this
        # check must be performed.
        return True if ignoreInner else not self.isInner()

    def onKeyDown(self, tid):
        '''When field is structured, this method returns the Javascript code to
           execute when a key is pressed, in order to implement keyboard
           shortcuts.'''
        return "useShortcut(event, '%s')" % tid if self.structured else ''

    def onFocus(self, lg):
        '''When field is structured, this method returns the Javascript code to
           execute when the textarea gets focus, in order to link the field with
           the toolbar.'''
        if not self.structured: return ''
        # The toolbar ID will be the same, be the field inner or not
        id = '%s_%s' % (self.name, lg) if lg else self.name
        return "linkTextToolbar('%s_tb', this)" % id

    def getPlaceholder(self, o):
        '''Returns a placeholder for the field if defined'''
        r = self.getAttribute(o, 'placeholder') or ''
        if r == True:
            # A placeholder must be set, but we have no value. In this case, we
            # take the field label.
            r = o.translate(self.labelId)
        return r

    def getUniFormattedValue(self, o, value, layout='view', showChanges=False,
                             language=None, contentLanguage=None):
        '''Returns the formatted variant of p_value. If p_contentLanguage is
           specified, p_value is the p_contentLanguage part of a multilingual
           value.'''
        if Field.isEmptyValue(self, o, value) and not showChanges: return ''
        r = value
        if layout in ('view', 'cell'):
            r = sutils.formatText(r, format='html_from_text')
        # If value starts with a carriage return, add a space; else, it will
        # be ignored.
        if isinstance(r, str) and \
           (r.startswith('\n') or r.startswith('\r\n')): r = ' ' + r
        return r

    def getUniIndexValue(self, o, value):
        '''Gets the value to index for this unilingual p_value'''
        return sutils.normalizeString(value, usage='extract').lower() \
               if value else ''

    def getUniStorableValue(self, o, value):
        '''Gets the p_value as can be stored in the database within p_o'''
        if not value: return value
        # Clean the value
        value = value.replace('\r', '')
        # Manage maxChars
        max = self.maxChars
        if max and (len(value) > max): value = value[:max]
        return value

    def getIndexType(self): return 'TextIndex'

    def getListHeader(self, ctx):
        '''If this field is structured, when used as an inner field, the
           toolbar must be rendered only once, within the container field's
           header row corresponding to this field.'''
        # Inject the toolbar when appropriate
        if (ctx.layout == 'edit') and self.showToolbar(ignoreInner=True):
            bar = self.pxToolbar(ctx)
        else:
            bar = ''
        return '%s%s' % (Field.getListHeader(self, ctx), bar.encode('utf-8'))
# ------------------------------------------------------------------------------
