'''This module contains all visitors for the tree of tags defined in tags.py
   and build by parser.py.'''

# ------------------------------------------------------------------------------
from appy.pod.xhtml import tags

# ------------------------------------------------------------------------------
class Visitor:
    '''Abstract base class for all visitors'''

    def visit(self, env):
        '''Visits the tree of tags that has been build in the p_env(ironment)'''

# ------------------------------------------------------------------------------
class TablesNormalizer(Visitor):
    '''Ensure all tables rows are under a tag "thead" or "tbody"'''

    def isHeaderRow(self, row):
        '''A row is considered a header row if all cells are "th" cells'''
        for cell in row.iterChildren(types='Cell'):
            if cell.name == 'td': return
        return True # Implicitly, all rows are "th" rows if we are here

    def visitTable(self, table):
        '''Visiting a table = normalizing it'''
        # Store here tags "thead" and "tbody"
        thead = tbody = None
        # Store here "root" rows, ie, those encountered directly under the
        # "table" tag (not being under tag "thead" nor "tbody").
        rootRows = []
        # Walk table sub-tags
        for tag in table.iterChildren():
            if tag.className == 'Header':
                thead = tag
            elif tag.className == 'Body':
                tbody = tag
            elif tag.className == 'Row':
                rootRows.append(tag)
        # Set all root rows within thead or tbody
        for row in rootRows:
            if self.isHeaderRow(row):
                # This is a header row. Create the "thead" tag when inexistent.
                if not thead:
                    thead = tags.Header('thead', None, parent=table)
                row.setParent(thead)
            else:
                # This is a body row. Create the "tbody" tag when inexistent.
                if not tbody:
                    tbody = tags.Body('tbody', None, parent=table)
                row.setParent(tbody)

    def visit(self, env):
        # Do nothing if no table was found
        if 'Table' not in env.tags: return
        # Walk every table
        for table in env.tags['Table']:
            self.visitTable(table)
        
# ------------------------------------------------------------------------------
class KeepWithNext(Visitor):
    # CSS classes with "keep with next" functionality, by tag type. By default,
    # class "ParaKWN" is applied.
    cssClasses = {'li': 'podItemKeepWithNext'}
    # We will only walk tags directly under the root tag, having one of these
    # types.
    rootTagTypes = ('Para', 'List', 'Table')

    def __init__(self, chars):
        # The number of chars that must be kept together
        self.charsToKeep = chars
        # The number of chars walked and counted so far
        self.charsWalked = 0
        # If we must split a table due to our "keep-with-next" constraints, we
        # store here the table row of the table to split; this row will be the
        # first of the second table.
        self.splitRow = None

    def charsReached(self):
        '''Have we reached self.charsToKeep ?'''
        return self.charsWalked >= self.charsToKeep

    def splitTable(self):
        '''Splits the table containing p_self.splitRow into 2 separate tables in
           order to enforce "keep-with-next" constraints.'''
        # Let's call the table to split "table" and the splitted tables
        # "table1" and "table2". Instead of performing a real split, where
        # "table1" will contain the first "table" rows, including the one
        # preceding p_self.splitRow, and "table2" will contain the last "table"
        # rows, from p_self.splitRow to the end, we will duplicate "table":
        # "table1" and "table2" will contain all "table" rows. Indeed, xhtml2odt
        # and LibreOffice will potentially compute cell's widths, and if these
        # computations are performed on "table1" and "table2" respectively
        # containing their corresponding rows, they may produce different
        # results on "table1" and on "table2". That is not acceptable. This is
        # why we keep all rows duplicated in both tables, but we set a
        # "keeprows" attribute that will be processed by the POD's
        # post-processor.
        # Get the first table's tags of interest
        tbody1 = self.splitRow.parent
        table1 = tbody1.parent
        # Create the second table by cloning the first one
        table2 = table1.clone()
        tbody2 = tags.Body('tbody', parent=table2)
        # Ensure "table2" will be kept with the next paragraphs
        table2.addCss('TableKWN')
        # Copy all rows from "table1" to "table2". Here, we cheat: instead of
        # copying rows, we copy them by reference. The rows will have "tbody1"
        # as parent, but currently this has no importance when dumping the tree
        # of tags as XHTML.
        tbody2.children = tbody1.children
        # Set attributes "keeprows" on "table1" and "table2"
        i = tbody1.children.index(self.splitRow)
        table1.addAttribute('keeprows', ':%d' % i)
        table2.addAttribute('keeprows', '%d:' % i)
        # Insert table2 just after table1
        parent = table1.parent
        table2.setParent(parent, at=parent.children.index(table1)+1)

    def visitPara(self, para):
        '''Visiting a p_para(graph) = applying the correct "keep-with-next"
           class on it.'''
        para.addCss(self.cssClasses.get(para.name) or 'ParaKWN')
        # Update the number of walked chars
        self.charsWalked += para.getContentLength()

    def visitList(self, list):
        '''Visiting a list = visiting its items in reverse order'''
        # "li" sub-tags are Para instances
        for child in list.iterChildren(types='Para', reverse=True):
            self.visitPara(child)
            if self.charsReached():
                return

    def visitRow(self, row):
        '''We visit a row only for computing its content length'''
        self.charsWalked += row.getContentLength()

    def visitTable(self, table):
        '''Visiting a table = visiting its rows in reverse order.

           If we reach p_self.charsToKeep at a given row R, we must split the
           table in 2 tables: the first one containing all rows preceding R, and
           the second one containing row R and subsequent rows.
        '''
        # Get the "tbody" tag
        tbody = table.getChild('Body')
        if not tbody: return
        # Walk tbody's rows in reverse order
        for row in tbody.iterChildren(types='Row', reverse=True):
            self.visitRow(row)
            if self.charsReached():
                # This row and subsequent ones must be splitted in a second
                # table, excepted if this row is the first row of data in its
                # table. Indeed, we will not take the risk of having table
                # headers left alone on a separate page.
                if row != tbody.getChild('Row'):
                    self.splitRow = row
                break

    def visit(self, env):
        '''We will determine the set of root paragraphs corresponding to the
           last "self.chars" chars and apply, on each one, a special class that
           will ensure it will be kept with the next one on the same page.'''
        # Walk tags directly under the root tag, in reverse order
        for child in env.r.iterChildren(types=self.rootTagTypes, reverse=True):
            # Visit the child
            getattr(self, 'visit%s' % child.className)(child)
            # Stop if we have reached the number of chars to keep together
            if self.charsReached():
                break
        # If we have reached chars in the middle of a table, we must split it
        if self.splitRow: self.splitTable()
# ------------------------------------------------------------------------------
