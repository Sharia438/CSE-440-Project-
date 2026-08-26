import random, time
from collections import Counter
from leduc_env import (
    State, new_hand, legal_actions, apply_action, needs_board_card, deal_board,
    utility_p0, remaining_deck, full_deck, RANKS
)

NODES_EXPANDED = 0  # global counter for performance measurement


def evaluate_heuristic(state):
    """Depth-cutoff heuristic (unused at full depth, kept for scalability demo).
    Rough equity: probability AI's hole card beats a uniformly random opponent
    card, scaled by pot size. Not needed for Leduc (tree is fully searchable)
    but included so the design generalizes to bigger games."""
    deck = remaining_deck(state, exclude_player_view=0)
    wins = ties = 0
    for oc in deck:
        r0 = (state.hole[0] == state.board, state.hole[0])
        r1 = (oc == state.board, oc)
        if r0 > r1: wins += 1
        elif r0 == r1: ties += 1
    equity = (wins + 0.5 * ties) / max(1, len(deck))
    pot = state.bets[0] + state.bets[1]
    return equity * pot - state.bets[0]


def expectiminimax(state, depth, alpha=-1e9, beta=1e9):
    """Exact (or depth-limited) expectiminimax over a FULLY SPECIFIED state
    (both hole cards known to the search). Player 0 = MAX, player 1 = MIN.
    Chance node = dealing the flop board card."""
    global NODES_EXPANDED
    NODES_EXPANDED += 1

    if state.terminal:
        return utility_p0(state)

    if depth == 0:
        return evaluate_heuristic(state)

    if needs_board_card(state):
        deck = remaining_deck(state, exclude_player_view=None)
        counts = Counter(deck)
        total = len(deck)
        val = 0.0
        for card, cnt in counts.items():
            prob = cnt / total
            child = deal_board(state, card)
            val += prob * expectiminimax(child, depth - 1, alpha, beta)
        return val

    acts = legal_actions(state)
    if state.current == 0:  # MAX
        best = -1e9
        for a in acts:
            v = expectiminimax(apply_action(state, a), depth - 1, alpha, beta)
            best = max(best, v)
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best
    else:  # MIN
        best = 1e9
        for a in acts:
            v = expectiminimax(apply_action(state, a), depth - 1, alpha, beta)
            best = min(best, v)
            beta = min(beta, best)
            if alpha >= beta:
                break
        return best


class ExpectiminimaxAgent:
    """Plays as either seat. Does NOT peek at the opponent's true hole card:
    it marginalizes over all cards consistent with what has been revealed
    (its own card + any board card), i.e. a chance node over 'nature's deal'
    of the opponent's hand. This is the standard AIMA-style relaxation for
    applying expectiminimax to a hidden-information game: opponent modeled
    as a fully-informed adversarial minimizer, weighted by deal probability."""

    def __init__(self, seat, max_depth=20):
        self.seat = seat
        self.max_depth = max_depth

    def act(self, state):
        me, opp = self.seat, 1 - self.seat
        possible_opp_cards = remaining_deck(state, exclude_player_view=me)
        counts = Counter(possible_opp_cards)
        total = sum(counts.values())

        acts = legal_actions(state)
        best_action, best_val = None, None
        for a in acts:
            exp_val = 0.0
            for card, cnt in counts.items():
                prob = cnt / total
                hypo = state.clone()
                hypo.hole[opp] = card
                child = apply_action(hypo, a)
                v = expectiminimax(child, self.max_depth)
                exp_val += prob * v
            # value is from player 0's perspective; flip sign if we're seat 1
            score = exp_val if me == 0 else -exp_val
            if best_val is None or score > best_val:
                best_val, best_action = score, a
        return best_action


class RandomAgent:
    def __init__(self, seat):
        self.seat = seat

    def act(self, state):
        return random.choice(legal_actions(state))


class CallStationAgent:
    """Always checks/calls, never folds or raises."""
    def __init__(self, seat):
        self.seat = seat

    def act(self, state):
        acts = legal_actions(state)
        if 'call' in acts:
            return 'call'
        return 'check'


class TightAggressiveAgent:
    """Simple rule-based baseline: raises with K, calls with Q, folds J
    (unless checking is free)."""
    def __init__(self, seat):
        self.seat = seat

    def act(self, state):
        acts = legal_actions(state)
        my_card = state.hole[self.seat]
        strong = (my_card == 'K') or (state.board is not None and my_card == state.board)
        medium = my_card == 'Q'
        if strong and 'raise' in acts:
            return 'raise'
        if 'check' in acts:
            return 'check' if not strong else ('raise' if 'raise' in acts else 'check')
        if medium and 'call' in acts:
            return 'call'
        if strong and 'call' in acts:
            return 'call'
        return 'fold' if 'fold' in acts else 'call'


def play_hand(agent0, agent1, rng):
    deck = full_deck()
    rng.shuffle(deck)
    h0, h1 = deck[0], deck[1]
    state = new_hand(h0, h1)
    while not state.terminal:
        if needs_board_card(state):
            remaining = remaining_deck(state)
            card = rng.choice(remaining)
            state = deal_board(state, card)
            continue
        agent = agent0 if state.current == 0 else agent1
        action = agent.act(state)
        state = apply_action(state, action)
    return utility_p0(state)  # net result for seat 0


def simulate(agent0_cls, agent1_cls, n_hands=200, seed=42, **kwargs):
    rng = random.Random(seed)
    total0 = 0.0
    results = []
    t0 = time.perf_counter()
    global NODES_EXPANDED
    NODES_EXPANDED = 0
    for i in range(n_hands):
        # alternate seats each hand to cancel positional advantage
        if i % 2 == 0:
            a0 = agent0_cls(0, **kwargs) if agent0_cls is ExpectiminimaxAgent else agent0_cls(0)
            a1 = agent1_cls(1, **kwargs) if agent1_cls is ExpectiminimaxAgent else agent1_cls(1)
            net = play_hand(a0, a1, rng)
        else:
            a0 = agent1_cls(0, **kwargs) if agent1_cls is ExpectiminimaxAgent else agent1_cls(0)
            a1 = agent0_cls(1, **kwargs) if agent0_cls is ExpectiminimaxAgent else agent0_cls(1)
            net = -play_hand(a0, a1, rng)  # flip back to "agent0's" perspective
        total0 += net
        results.append(net)
    elapsed = time.perf_counter() - t0
    return {
        'hands': n_hands,
        'avg_net_per_hand': total0 / n_hands,
        'total_net': total0,
        'elapsed_sec': elapsed,
        'nodes_expanded': NODES_EXPANDED,
        'avg_nodes_per_decision': NODES_EXPANDED / max(1, n_hands),
    }


if __name__ == '__main__':
    print("=== Expectiminimax (seat-alternating) vs baselines, 300 hands each ===\n")

    for name, opp_cls in [('RandomAgent', RandomAgent),
                           ('CallStationAgent', CallStationAgent),
                           ('TightAggressiveAgent', TightAggressiveAgent)]:
        r = simulate(ExpectiminimaxAgent, opp_cls, n_hands=300, seed=1)
        print(f"Expectiminimax vs {name}:")
        print(f"  avg net chips/hand for Expectiminimax: {r['avg_net_per_hand']:+.4f}")
        print(f"  total over {r['hands']} hands: {r['total_net']:+.1f}")
        print(f"  wall time: {r['elapsed_sec']:.2f}s | nodes expanded: {r['nodes_expanded']:,} "
              f"({r['avg_nodes_per_decision']:.0f} nodes/hand)\n")

    print("=== Baseline vs baseline sanity check (Random vs CallStation) ===")
    r = simulate(RandomAgent, CallStationAgent, n_hands=300, seed=2)
    print(f"  avg net chips/hand for RandomAgent: {r['avg_net_per_hand']:+.4f}\n")

    print("=== Depth ablation: limited-depth + heuristic cutoff vs full-depth ===")
    for d in [2, 4, 8, 20]:
        r = simulate(ExpectiminimaxAgent, RandomAgent, n_hands=150, seed=3, max_depth=d)
        print(f"  depth={d:>2}: avg net/hand={r['avg_net_per_hand']:+.4f}  "
              f"nodes/hand={r['avg_nodes_per_decision']:.0f}  time={r['elapsed_sec']:.2f}s")
