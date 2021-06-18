# Print iterations progress
from enum import Enum
import ast
import operator
import datetime, pytz, holidays


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
    WILDSTAR = "\U00002B50"
    BELL = "\U0001F514"
    CHERRY = "\U0001F352"
    BANANA = "\U0001F34C"
    LEMON = "\U0001F34B"
    STAR = "\U00002B50"
    STRAWBERRY = "\U0001F353"
    PINEAPPLE = "\U0001F34D"
    WATERMELON = "\U0001F349"
    ORANGE = "\U0001F34A"
    PARTY = "\U0001F389"


# Calc class from user mgilson on stackoverflow
_OP_MAP = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Invert: operator.neg,
    ast.Pow: operator.pow
}


class Calc(ast.NodeVisitor):

    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        return _OP_MAP[type(node.op)](left, right)

    def visit_Num(self, node):
        return node.n

    def visit_Expr(self, node):
        return self.visit(node.value)

    @classmethod
    def evaluate(cls, expression):
        tree = ast.parse(expression)
        calc = cls()
        return calc.visit(tree.body[0])


# Check if the stock market is open
def is_market_closed():
    tz = pytz.timezone('America/New_York')
    us_holidays = holidays.US()

    now = datetime.datetime.now(tz)
    open_time = datetime.time(hour=9, minute=30, second=0)
    close_time = datetime.time(hour=16, minute=0, second=0)
    # If a holiday
    if now.strftime('%Y-%m-%d') in us_holidays:
        return True
    # If before 0930 or after 1600
    if (now.time() < open_time) or (now.time() > close_time):
        return True
    # If it's a weekend
    if now.date().weekday() > 4:
        return True

    return False


def pre_market_closed():
    tz = pytz.timezone('America/New_York')
    us_holidays = holidays.US()

    now = datetime.datetime.now(tz)
    pre_open_time = datetime.time(hour=4, minute=00, second=0)
    pre_close_time = datetime.time(hour=9, minute=30, second=00)

    # If a holiday
    if now.strftime('%Y-%m-%d') in us_holidays:
        return True
    if now.time() < pre_open_time or now.time() > pre_close_time:
        return True
    # If it's a weekend
    if now.date().weekday() > 4:
        return True

    return False


def post_market_closed():
    tz = pytz.timezone('America/New_York')
    us_holidays = holidays.US()

    now = datetime.datetime.now(tz)
    post_open_time = datetime.time(hour=16, minute=00, second=0)
    post_close_time = datetime.time(hour=20, minute=00, second=00)

    # If a holiday
    if now.strftime('%Y-%m-%d') in us_holidays:
        return True
    if now.time() < post_open_time or now.time() > post_close_time:
        return True
    # If it's a weekend
    if now.date().weekday() > 4:
        return True

    return False
