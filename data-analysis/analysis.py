from args import parse_args
from likert_questions import likert_plots

def main():
    # TODO: use argparse
    argv = parse_args()

    likert_plots(argv)
    # ...
if __name__=="__main__":
    main()