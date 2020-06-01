# Print iterations progress
from enum import Enum


def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=100, fill='█'):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    return '%s |%s| %s%% %s' % (prefix, bar, percent, suffix)


class Reel(Enum):
    GEM = "\U0001F48E"
    CHERRY = "\U0001F352"
    BANANA = "\U0001F34C"
    LEMON = "\U0001F34B"
    STAR = "\U00002B50"
    STRAWBERRY = "\U0001F353"
