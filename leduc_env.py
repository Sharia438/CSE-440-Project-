"""
Leduc Hold'em environment.

Deck: 6 cards -> ranks J,Q,K, two copies each (two "suits" but suit is irrelevant here).
2 players. Each antes 1 chip, gets 1 private hole card.
Round 0 (preflop): betting with fixed raise size = 2.
Then 1 public board card is dealt (chance event).
Round 1 (flop): betting with fixed raise size = 4.
Showdown: pair with board beats non-pair; else higher hole-card rank wins; tie splits.
Max 2 raises per betting round.
"""
import random
from itertools import product

RANKS = ['J', 'Q', 'K']
RANK_VALUE = {'J': 1, 'Q': 2, 'K': 3}
RAISE_SIZE = {0: 2, 1: 4}
MAX_RAISES = 2


def full_deck():
    return [r for r in RANKS for _ in range(2)]  # 6 cards, 2 copies each rank


class State:
    __slots__ = ('hole', 'board', 'bets', 'current', 'round', 'raises_this_round',
                 'round_history', 'folded', 'terminal', 'deck_seen')

    def __init__(self, hole, board, bets, current, round_, raises_this_round,
                 round_history, folded, terminal):
        self.hole = hole                  # {0: rank, 1: rank}
        self.board = board                # rank or None
        self.bets = bets                  # {0: int, 1: int} total chips committed
        self.current = current            # player to act (0 or 1)
        self.round = round_               # 0 = preflop, 1 = flop
        self.raises_this_round = raises_this_round
        self.round_history = round_history  # list of actions this betting round
        self.folded = folded              # None or player id who folded
        self.terminal = terminal

    def clone(self):
        return State(dict(self.hole), self.board, dict(self.bets), self.current,
                      self.round, self.raises_this_round, list(self.round_history),
                      self.folded, self.terminal)


def new_hand(hole0, hole1, rng=None):
    """Start a hand with given hole cards (each player antes 1 chip)."""
    return State({0: hole0, 1: hole1}, None, {0: 1, 1: 1}, 0, 0, 0, [], None, False)


def legal_actions(state):
    if state.terminal:
        return []
    if state.bets[0] == state.bets[1]:
        acts = ['check']
        if state.raises_this_round < MAX_RAISES:
            acts.append('raise')
    else:
        acts = ['fold', 'call']
        if state.raises_this_round < MAX_RAISES:
            acts.append('raise')
    return acts


def _round_closes(history):
    """True if the just-appended action ends the current betting round."""
    if not history:
        return False
    if history[-1] == 'call':
        return True
    if history[-1] == 'check' and len(history) >= 2 and history[-2] == 'check':
        return True
    return False


def apply_action(state, action):
    """Return a new State after `action` is applied (no chance events resolved)."""
    s = state.clone()
    p, o = s.current, 1 - s.current
    r = RAISE_SIZE[s.round]

    if action == 'fold':
        s.folded = p
        s.terminal = True
        return s

    if action == 'call':
        s.bets[p] = s.bets[o]
        s.round_history.append('call')
    elif action == 'check':
        s.round_history.append('check')
    elif action == 'raise':
        s.bets[p] = s.bets[o] + r
        s.raises_this_round += 1
        s.round_history.append('raise')
    else:
        raise ValueError(action)

    if _round_closes(s.round_history):
        if s.round == 0:
            s.round = 1
            s.raises_this_round = 0
            s.round_history = []
            s.current = 0
            s.terminal = False
        else:
            s.terminal = True  # showdown
    else:
        s.current = o
    return s


def needs_board_card(state):
    return state.round == 1 and state.board is None and not state.terminal


def deal_board(state, card):
    s = state.clone()
    s.board = card
    return s


def is_chance_node(state):
    return needs_board_card(state)


def hand_rank(hole, board):
    """Returns (is_pair, rank_value) for comparison."""
    pair = (hole == board)
    return (1 if pair else 0, RANK_VALUE[hole])


def utility_p0(state):
    """Net chip result for player 0 at a terminal state (zero-sum)."""
    assert state.terminal
    if state.folded is not None:
        winner = 1 - state.folded
    else:
        r0 = hand_rank(state.hole[0], state.board)
        r1 = hand_rank(state.hole[1], state.board)
        if r0 > r1:
            winner = 0
        elif r1 > r0:
            winner = 1
        else:
            winner = None  # split pot
    if winner is None:
        return 0.0
    return float(state.bets[1]) if winner == 0 else -float(state.bets[0])


def remaining_deck(state, exclude_player_view=None):
    """Cards not visible to a given viewpoint (or all dealt cards if None)."""
    deck = full_deck()
    seen = []
    if exclude_player_view is not None:
        seen.append(state.hole[exclude_player_view])
    else:
        seen.extend(state.hole.values())
    if state.board is not None:
        seen.append(state.board)
    for c in seen:
        deck.remove(c)
    return deck
