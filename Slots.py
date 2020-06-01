#    Copyright (C) 2017  https://github.com/s4w3d0ff
#    BTC: 15D8VaZco22GTLVrFMAehXyif6EGf8GMYV
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc.,
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
import logging

import Utils

try:
    from numpy.random import RandomState
    from numpy.random import shuffle
except:
    logging.warning('Could not find numpy.random, using random.SystemRandom')
    from random import SystemRandom as RandomState

logger = logging.getLogger(__name__)


class SlotMachine(object):
    """ A simple, expandable, customizable slotmachine complete with
    identifyable 'jackpot' and 'bonus' symbols.
    """

    def __init__(self, jack=Utils.Reel.GEM, bonus=Utils.Reel.STAR,
                 size=(3, 1), randomState=None):
        self.jack, self.bonus = jack, bonus
        self.size = size
        self.reel = self.buildReel()
        if randomState:
            self.randomState = randomState
        else:
            self.randomState = RandomState()
        self.count = 0
        self.sinceJack = 0
        self.odds = None
        self.lastSpin = None

    def buildReel(self):
        reel = [Utils.Reel.STAR.value, Utils.Reel.STAR.value,
                Utils.Reel.GEM.value, Utils.Reel.GEM.value, Utils.Reel.GEM.value,
                Utils.Reel.CHERRY.value, Utils.Reel.CHERRY.value, Utils.Reel.CHERRY.value, Utils.Reel.CHERRY.value,
                Utils.Reel.BANANA.value, Utils.Reel.BANANA.value, Utils.Reel.BANANA.value, Utils.Reel.BANANA.value,
                Utils.Reel.BANANA.value,
                Utils.Reel.LEMON.value, Utils.Reel.LEMON.value, Utils.Reel.LEMON.value, Utils.Reel.LEMON.value,
                Utils.Reel.LEMON.value, Utils.Reel.LEMON.value,
                Utils.Reel.STRAWBERRY.value, Utils.Reel.STRAWBERRY.value, Utils.Reel.STRAWBERRY.value,
                Utils.Reel.STRAWBERRY.value, Utils.Reel.STRAWBERRY.value,
                Utils.Reel.STRAWBERRY.value, Utils.Reel.STRAWBERRY.value]
        shuffle(reel)
        return reel

    def __call__(self):
        """ Pulls the 'handle' """
        logger.debug('Spinning machine')
        # set empty display
        nCols, nRows = range(self.size[0]), range(self.size[1])
        # pick symbols and fill display
        raw = [[self.reel[i - row] for row in nRows]
               for i in [self.randomState.choice(range(len(self.reel)))
                         for col in nCols]]
        self.count += 1
        self.sinceJack += 1
        # return display (turned 90 so it makes more
        # sense and easier to traverse/read)
        self.lastSpin = [[col[i] for col in raw] for i in range(len(raw[0]))]
        return self.lastSpin

    def checkLine(self, line):
        first = line[0]
        index = 1
        in_a_row = 1

        while first is self.bonus and index < len(line) - 1:
            first = line[index]
            in_a_row += 1
            index += 1

        while (line[index] in [first, self.bonus]) and (index <= len(line)):
            in_a_row += 1
            index += 1
            if index == len(line):
                break

        return in_a_row, first


if __name__ == '__main__':
    from sys import argv

    s = SlotMachine()
    logging.basicConfig(level=logging.INFO)
    r = s()[0]
    print(r)
    print(s.checkLine(r))


def get_winnings(reel, win_list, bet, bonus):
    in_a_row = win_list[0]
    winning_symbol = win_list[1]

    if in_a_row <= 1:
        return 0

    count = reel.count(winning_symbol) + reel.count(bonus)
    total = len(reel)

    winnings = (((total / count) / 1.5) ** (in_a_row)) * bet

    return int(winnings)
