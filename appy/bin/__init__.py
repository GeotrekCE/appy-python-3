'''This module contains command-line programs'''

# ------------------------------------------------------------------------------
import sys, argparse

# ------------------------------------------------------------------------------
class Program:
    '''Abstract base class for all command-line programs'''
    def __init__(self):
        # Create the argument parser
        self.parser = argparse.ArgumentParser()
        # Define arguments
        self.defineArguments()
        # Parse arguments
        self.args = self.parser.parse_args()
        # Analyse parsed arguments
        self.analyseArguments()

    def defineArguments(self):
        '''Override this method to define arguments to self.parser (using
           method self.parser.add_argument): see documentation for the
           argparse module.'''

    def analyseArguments(self):
        '''Override this method to analyse arguments that were parsed an stored
           in self.args:
           * check their validity;
           * potentially apply some computation on it and store, on p_self, new
             attributes derived from self.args.
           If this method detects an error within self.args, abort program
           execution by calling m_exit (see below).
        '''

    def exit(self, msg, printUsage=True):
        '''Exists the program afer an error has been encountered and display
           some p_msg.'''
        print(msg)
        if printUsage:
            self.parser.print_usage()
        return sys.exit(1)

    def run(self):
        '''Executes the program after arguments were successfully analysed'''
# ------------------------------------------------------------------------------
