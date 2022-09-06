import sys
import argparse


def parser_flag(parser: argparse.ArgumentParser, flag_name: str, desc: str):
    """
    Template format for creating parser args that are set to True when they
    exist
    Arguments:
      parser (ArgumentParser): The parser to add the arg to
      flag_name (str): Name of flag, delimited by '-'
      desc (str): Description for help section
    """

    parser.add_argument("--" + flag_name,
                        dest=flag_name.replace('-', '_'),
                        action="store_const",
                        help=desc,
                        const=True,
                        default=False)


def parser_value(parser: argparse.ArgumentParser, flag_name: str, desc: str, default: str=None):
    """
    Template format for creating parser args that expect values
    Arguments:
      parser (ArgumentParser): The parser to add the arg to
      flag_name (str): Name of flag, delimited by '-'
      desc (str): Description for help section
    """

    parser.add_argument("--" + flag_name,
                        dest=flag_name.replace('-', '_'),
                        default=default,
                        action="store")

def likert_args(parser: argparse.ArgumentParser):
    parser_value(parser, "fig_name", "The path to save the figures at", default='all')
    parser_value(parser, "questions", "The indices of the questions you want plotted", 'all')  # TODO: indices? Q12.2? all?
    parser_value(parser, "conditions", "The conditions you want to see", 'all')

def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Analysis for Retrograde Data')  
    likert_args(parser) 
    argv = parser.parse_args()
    return argv