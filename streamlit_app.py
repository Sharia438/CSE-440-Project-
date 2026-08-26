from __future__ import annotations

import random
import time
from html import escape

import streamlit as st


PLAYERS = (
    {"name": "You", "role": "Human", "icon": "♠"},
    {"name": "Atlas", "role": "Aggressive AI", "icon": "♣"},
    {"name": "Nova", "role": "Strategic AI", "icon": "♦"},
    {"name": "Echo", "role": "Careful AI", "icon": "♥"},
)
RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
SUITS = ("♠", "♥", "♦", "♣")
RANK_VALUE = {rank: value for value, rank in enumerate(RANKS, start=2)}
VALUE_RANK = {value: rank for rank, value in RANK_VALUE.items()}
RANK_NAMES = {"2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten", "J": "jack", "Q": "queen", "K": "king", "A": "ace"}
RANK_PLURALS = {"2": "twos", "3": "threes", "4": "fours", "5": "fives", "6": "sixes", "7": "sevens", "8": "eights", "9": "nines", "10": "tens", "J": "jacks", "Q": "queens", "K": "kings", "A": "aces"}
STARTING_STACK = 100
ANTE = 1
MAX_RAISES = 2

st.set_page_config(page_title="Four Seat Poker", page_icon="♠", layout="wide")


def init_session() -> None:
    session = st.session_state
    session.setdefault("stacks", [STARTING_STACK] * 4)
    session.setdefault("button", 0)
    session.setdefault("hand_number", 0)
    session.setdefault("hand", None)
    session.setdefault("log", [])
    session.setdefault("user_total", 0)
    session.setdefault("ai_delay", 1.5)
    session.setdefault("last_action", "Welcome to the table.")
    session.setdefault("rng", random.Random())


def add_log(message: str) -> None:
    st.session_state.log.append(message)
    st.session_state.last_action = message


def standard_deck() -> list[tuple[str, str]]:
    return [(rank, suit) for rank in RANKS for suit in SUITS]


def next_active(after_seat: int, active: list[bool], folded: list[bool] | None = None) -> int:
    for offset in range(1, 5):
        seat = (after_seat + offset) % 4
        if active[seat] and (folded is None or not folded[seat]):
            return seat
    return after_seat


def live_seats(hand: dict) -> list[int]:
    return [seat for seat in range(4) if hand["active"][seat] and not hand["folded"][seat]]


def actionable_seats(hand: dict) -> list[int]:
    return [seat for seat in live_seats(hand) if st.session_state.stacks[seat] > 0]


def begin_hand() -> None:
    session = st.session_state
    eligible = [seat for seat, stack in enumerate(session.stacks) if stack > 0]
    if len(eligible) < 2 or session.stacks[0] <= 0:
        session.stacks = [STARTING_STACK] * 4
        session.user_total = 0
        eligible = list(range(4))

    deck = standard_deck()
    session.rng.shuffle(deck)
    cards = {seat: [deck.pop(), deck.pop()] for seat in eligible}
    contributions = [0] * 4
    active = [seat in eligible for seat in range(4)]
    for seat in eligible:
        ante = min(ANTE, session.stacks[seat])
        session.stacks[seat] -= ante
        contributions[seat] = ante

    hand = {
        "cards": cards,
        "board": [],
        "active": active,
        "folded": [False] * 4,
        "contributions": contributions,
        "round_contributions": contributions.copy(),
        "current_bet": ANTE,
        "phase": "Pre-flop",
        "raises": 0,
        "current": session.button,
        "pending": set(),
        "deck": deck,
        "finished": False,
        "scored": False,
        "button": session.button,
    }
    hand["pending"] = set(actionable_seats(hand))
    if hand["pending"]:
        hand["current"] = next_pending(session.button, hand)
    session.hand = hand
    session.hand_number += 1
    session.last_action = f"Hand {session.hand_number} begins — everyone antes {ANTE} chip."
    session.log = [session.last_action]
    session.button = next_active(session.button, active)
    if not hand["pending"]:
        run_out_board(hand)


def amount_to_call(hand: dict, seat: int) -> int:
    return max(0, hand["current_bet"] - hand["round_contributions"][seat])


def legal_actions(hand: dict, seat: int) -> list[str]:
    if (hand["finished"] or seat != hand["current"] or hand["folded"][seat]
            or st.session_state.stacks[seat] <= 0):
        return []
    to_call = amount_to_call(hand, seat)
    actions = ["check"] if to_call == 0 else ["fold", "call"]
    raise_size = 2 if hand["phase"] in {"Pre-flop", "Flop"} else 4
    if hand["raises"] < MAX_RAISES and st.session_state.stacks[seat] >= to_call + raise_size:
        actions.append("raise")
    return actions


def payment(seat: int, amount: int, hand: dict) -> int:
    paid = min(amount, st.session_state.stacks[seat])
    st.session_state.stacks[seat] -= paid
    hand["contributions"][seat] += paid
    hand["round_contributions"][seat] += paid
    return paid


def action_label(seat: int, action: str, hand: dict, all_in: bool = False) -> str:
    name = PLAYERS[seat]["name"]
    if action == "raise":
        return f"{name} raised to {hand['current_bet']}"
    if action == "call" and all_in:
        return f"{name} is all-in"
    return f"{name} {action}ed" if action != "call" else f"{name} called"


def next_pending(after_seat: int, hand: dict) -> int:
    for offset in range(1, 5):
        seat = (after_seat + offset) % 4
        if seat in hand["pending"]:
            return seat
    return after_seat


def five_card_rank(cards: list[tuple[str, str]]) -> tuple:
    values = sorted((RANK_VALUE[rank] for rank, _ in cards), reverse=True)
    counts = sorted(((values.count(value), value) for value in set(values)), reverse=True)
    flush = len({suit for _, suit in cards}) == 1
    unique = sorted(set(values), reverse=True)
    straight_high = 0
    if len(unique) == 5:
        if unique[0] - unique[4] == 4:
            straight_high = unique[0]
        elif unique == [14, 5, 4, 3, 2]:
            straight_high = 5
    if flush and straight_high:
        return (8, straight_high)
    if counts[0][0] == 4:
        return (7, counts[0][1], counts[1][1])
    if counts[0][0] == 3 and counts[1][0] == 2:
        return (6, counts[0][1], counts[1][1])
    if flush:
        return (5, *values)
    if straight_high:
        return (4, straight_high)
    if counts[0][0] == 3:
        kickers = sorted((value for value in values if value != counts[0][1]), reverse=True)
        return (3, counts[0][1], *kickers)
    pairs = sorted((value for count, value in counts if count == 2), reverse=True)
    if len(pairs) == 2:
        kicker = next(value for value in values if value not in pairs)
        return (2, *pairs, kicker)
    if len(pairs) == 1:
        kickers = sorted((value for value in values if value != pairs[0]), reverse=True)
        return (1, pairs[0], *kickers)
    return (0, *values)


def best_five_hand(cards: list[tuple[str, str]], board: list[tuple[str, str]]) -> tuple[tuple, list[tuple[str, str]]]:
    all_cards = cards + board
    if len(all_cards) < 5:
        return (0, *(sorted((RANK_VALUE[rank] for rank, _ in all_cards), reverse=True))), all_cards
    best_rank = (-1,)
    best_cards = []
    for first in range(len(all_cards)):
        for second in range(first + 1, len(all_cards)):
            for third in range(second + 1, len(all_cards)):
                for fourth in range(third + 1, len(all_cards)):
                    for fifth in range(fourth + 1, len(all_cards)):
                        selection = [all_cards[first], all_cards[second], all_cards[third], all_cards[fourth], all_cards[fifth]]
                        rank = five_card_rank(selection)
                        if rank > best_rank:
                            best_rank, best_cards = rank, selection
    return best_rank, best_cards


def hand_strength(cards: list[tuple[str, str]], board: list[tuple[str, str]]) -> tuple:
    return best_five_hand(cards, board)[0]


def hand_description(rank: tuple) -> str:
    category = rank[0]
    high_name = RANK_NAMES[VALUE_RANK[rank[1]]]
    high_plural = RANK_PLURALS[VALUE_RANK[rank[1]]]
    if category == 8:
        return f"{high_name.title()}-high straight flush"
    if category == 7:
        return f"Four {high_plural}"
    if category == 6:
        pair_plural = RANK_PLURALS[VALUE_RANK[rank[2]]]
        return f"{high_plural.title()} full of {pair_plural}"
    if category == 5:
        return f"{high_name.title()}-high flush"
    if category == 4:
        return f"{high_name.title()}-high straight"
    if category == 3:
        return f"Three {high_plural}"
    if category == 2:
        lower_pair = RANK_PLURALS[VALUE_RANK[rank[2]]]
        return f"Two pair, {high_plural} and {lower_pair}"
    if category == 1:
        return f"Pair of {high_plural}"
    return f"{high_name.title()}-high card"


def showdown_winners(hand: dict) -> list[int]:
    remaining = live_seats(hand)
    best = max(hand_strength(hand["cards"][seat], hand["board"]) for seat in remaining)
    return [seat for seat in remaining if hand_strength(hand["cards"][seat], hand["board"]) == best]


def pot_layers(hand: dict) -> list[tuple[int, list[int]]]:
    levels = sorted({amount for amount in hand["contributions"] if amount > 0})
    previous = 0
    layers = []
    for level in levels:
        contributors = [seat for seat, amount in enumerate(hand["contributions"]) if amount >= level]
        eligible = [seat for seat in live_seats(hand) if hand["contributions"][seat] >= level]
        layers.append(((level - previous) * len(contributors), eligible))
        previous = level
    return layers


def distribute_pots(hand: dict, forced_winner: int | None = None) -> list[dict]:
    payouts = []
    for index, (amount, eligible) in enumerate(pot_layers(hand)):
        if forced_winner is not None:
            winners = [forced_winner]
        else:
            if not eligible:
                continue
            best = max(hand_strength(hand["cards"][seat], hand["board"]) for seat in eligible)
            winners = [seat for seat in eligible if hand_strength(hand["cards"][seat], hand["board"]) == best]
        share, extra = divmod(amount, len(winners))
        for winner_index, seat in enumerate(winners):
            st.session_state.stacks[seat] += share + (1 if winner_index < extra else 0)
        label = "Main pot" if index == 0 else f"Side pot {index}"
        payouts.append({"label": label, "amount": amount, "winners": winners})
    return payouts


def score_hand(hand: dict) -> None:
    if hand["scored"]:
        return
    user_delta = st.session_state.stacks[0] - STARTING_STACK - st.session_state.user_total
    st.session_state.user_total += user_delta
    hand["scored"] = True


def finish_hand(hand: dict, winners: list[int], reason: str) -> None:
    pot = sum(hand["contributions"])
    forced_winner = winners[0] if reason != "Showdown" else None
    payouts = distribute_pots(hand, forced_winner)
    winners = sorted({seat for payout in payouts for seat in payout["winners"]})
    names = ", ".join(PLAYERS[seat]["name"] for seat in winners)
    hand.update(finished=True, winners=winners, reason=reason, pot=pot, payouts=payouts)
    add_log(f"{reason}: {names} win {pot} chips.")
    for payout in payouts:
        payout_names = ", ".join(PLAYERS[seat]["name"] for seat in payout["winners"])
        add_log(f"{payout['label']} ({payout['amount']}): {payout_names}")
    score_hand(hand)


def close_round(hand: dict) -> None:
    board_cards = {"Pre-flop": 3, "Flop": 1, "Turn": 1}
    next_phase = {"Pre-flop": "Flop", "Flop": "Turn", "Turn": "River"}
    if hand["phase"] not in board_cards:
        finish_hand(hand, [], "Showdown")
        return
    hand["board"].extend(hand["deck"].pop() for _ in range(board_cards[hand["phase"]]))
    hand["phase"] = next_phase[hand["phase"]]
    hand["round_contributions"] = [0] * 4
    hand["current_bet"] = 0
    hand["raises"] = 0
    hand["pending"] = set(actionable_seats(hand))
    revealed = " ".join(rank + suit for rank, suit in hand["board"])
    add_log(f"{hand['phase']} revealed: {revealed}")
    if len(hand["pending"]) <= 1:
        run_out_board(hand)
    else:
        hand["current"] = next_pending(hand["button"], hand)


def run_out_board(hand: dict) -> None:
    board_cards = {"Pre-flop": 3, "Flop": 1, "Turn": 1}
    next_phase = {"Pre-flop": "Flop", "Flop": "Turn", "Turn": "River"}
    while hand["phase"] in board_cards:
        hand["board"].extend(hand["deck"].pop() for _ in range(board_cards[hand["phase"]]))
        hand["phase"] = next_phase[hand["phase"]]
        revealed = " ".join(rank + suit for rank, suit in hand["board"])
        add_log(f"{hand['phase']} revealed: {revealed}")
    finish_hand(hand, [], "Showdown")


def apply_action(hand: dict, seat: int, action: str) -> None:
    if action not in legal_actions(hand, seat):
        return
    to_call = amount_to_call(hand, seat)
    if action == "fold":
        hand["folded"][seat] = True
        hand["pending"].discard(seat)
    elif action == "call":
        paid = payment(seat, to_call, hand)
        all_in = paid < to_call or st.session_state.stacks[seat] == 0
        hand["pending"].discard(seat)
    elif action == "check":
        hand["pending"].discard(seat)
    else:
        raise_size = 2 if hand["phase"] in {"Pre-flop", "Flop"} else 4
        payment(seat, to_call + raise_size, hand)
        hand["current_bet"] = hand["round_contributions"][seat]
        hand["raises"] += 1
        hand["pending"] = set(actionable_seats(hand)) - {seat}
    add_log(action_label(seat, action, hand, locals().get("all_in", False)))

    remaining = live_seats(hand)
    if len(remaining) == 1:
        finish_hand(hand, remaining, "Everyone else folded")
        return
    hand["pending"] = {player for player in hand["pending"] if player in actionable_seats(hand)}
    if not hand["pending"]:
        close_round(hand)
    else:
        hand["current"] = next_pending(seat, hand)


def ai_action(hand: dict, seat: int) -> str:
    actions = legal_actions(hand, seat)
    cards = hand["cards"][seat]
    values = sorted((RANK_VALUE[rank] for rank, _ in cards), reverse=True)
    board_ranks = [rank for rank, _ in hand["board"]]
    strength = values[0] + values[1] / 3
    if cards[0][0] == cards[1][0]:
        strength += 5
    strength += sum(2 for rank, _ in cards if rank in board_ranks)
    to_call = amount_to_call(hand, seat)
    profile = ("human", "aggressive", "strategic", "careful")[seat]
    roll = st.session_state.rng.random()
    if "raise" in actions:
        threshold = {"aggressive": .30, "strategic": .52, "careful": .72}.get(profile, 1)
        if strength >= 15 or (strength >= 11 and roll > threshold):
            return "raise"
        if to_call == 0 and profile == "aggressive" and roll > .80:
            return "raise"
    if to_call == 0:
        return "check"
    fold_limit = {"aggressive": .10, "strategic": .28, "careful": .48}[profile]
    if strength <= 8 and roll < fold_limit:
        return "fold"
    if strength <= 11 and to_call >= 4 and roll < fold_limit:
        return "fold"
    return "call"


def card_html(card: tuple[str, str] | None, hidden: bool = False, compact: bool = False) -> str:
    size = "card--small" if compact else ""
    if hidden:
        return f'<div class="playing-card card-back {size}">♠</div>'
    if card is None:
        return f'<div class="playing-card card-placeholder {size}"></div>'
    rank, suit = card
    color = "red-card" if suit in {"♥", "♦"} else ""
    return f'<div class="playing-card {size} {color}"><span>{escape(rank)}</span><small>{suit}</small></div>'


def cards_html(cards: list[tuple[str, str]], hidden: bool = False, compact: bool = False, slots: int | None = None) -> str:
    visible = "".join(card_html(card, hidden=hidden, compact=compact) for card in cards)
    blank_slots = max(0, (slots or len(cards)) - len(cards))
    blanks = "".join(card_html(None, compact=compact) for _ in range(blank_slots))
    return f"<div class='cards'>{visible}{blanks}</div>"


def seat_html(seat: int, hand: dict) -> str:
    player = PLAYERS[seat]
    active_turn = not hand["finished"] and hand["current"] == seat
    folded = hand["folded"][seat]
    cards = "" if seat not in hand["cards"] else cards_html(hand["cards"][seat], hidden=(seat != 0 and not hand["finished"]), compact=True)
    all_in = not hand["finished"] and not folded and st.session_state.stacks[seat] == 0
    status = "FOLDED" if folded else ("ALL-IN" if all_in else ("YOUR TURN" if active_turn and seat == 0 else "THINKING" if active_turn else "IN HAND"))
    return f'''<div class="seat {'seat--turn' if active_turn else ''} {'seat--folded' if folded else ''}">
      <div class="avatar">{player['icon']}</div><div class="seat-info"><b>{player['name']}</b><span>{player['role']}</span></div>
      <div class="seat-stack">{st.session_state.stacks[seat]}<small>chips</small></div>{cards}
      <div class="seat-status">{status}</div></div>'''


def inject_style() -> None:
    st.markdown("""
    <style>
      .stApp { background:radial-gradient(circle at 50% 30%,#16493b 0,#08251f 50%,#041511 100%); color:#f7f3e8; }
      #MainMenu,footer,header{visibility:hidden}.block-container{max-width:1180px;padding-top:2rem}.hero{text-align:center;margin-bottom:1.2rem}.hero h1{font-size:2.6rem;margin:0;letter-spacing:.04em;color:#f7de9b}.hero p{color:#b8d6c8;margin:.35rem 0}
      @keyframes table-enter{from{opacity:.65}to{opacity:1}}@keyframes card-deal{from{opacity:0;transform:translateY(-7px) rotate(-2deg)}to{opacity:1;transform:translateY(0) rotate(0)}}@keyframes active-glow{0%,100%{box-shadow:0 0 12px #f6cf7255}50%{box-shadow:0 0 24px #f6cf72cc}}@keyframes thinking-dot{0%,80%,100%{transform:scale(.55);opacity:.45}40%{transform:scale(1);opacity:1}}
      .table{border:10px solid #6e4a24;border-radius:160px;padding:28px;background:radial-gradient(ellipse,#14755c,#07503e);box-shadow:inset 0 0 0 3px #c59c54,0 14px 32px #0008;animation:table-enter .28s ease-out}.seat-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.seat-three{grid-column:1/3;width:50%;justify-self:center}.center-area{grid-column:1/3}.human-seat{grid-column:1/3;width:65%;justify-self:center}.seat{position:relative;min-height:100px;padding:12px 14px;border:1px solid #5d8f7c;border-radius:15px;background:#093b30e8;display:flex;align-items:center;gap:10px;color:#fff}.seat--turn{border-color:#f6cf72;animation:active-glow 1.4s ease-in-out infinite;background:#164c3e}.seat--folded{opacity:.45}.avatar{height:34px;width:34px;display:grid;place-items:center;background:#d7a54a;border-radius:50%;color:#17342b;font-size:18px}.seat-info{display:flex;flex-direction:column;min-width:87px}.seat-info span,.seat-stack small{color:#acd1c0;font-size:.72rem}.seat-stack{margin-left:auto;font-weight:700;text-align:right}.seat-stack small{display:block}.seat-status{position:absolute;bottom:6px;left:58px;color:#e5c26d;font-size:.61rem;font-weight:700;letter-spacing:.08em}
      .cards{display:flex;gap:6px}.playing-card{width:70px;height:92px;border-radius:9px;background:#f9f7f0;color:#1c2723;display:inline-flex;flex-direction:column;justify-content:space-between;padding:7px;box-sizing:border-box;font-size:1.7rem;font-weight:800;box-shadow:0 3px 7px #0005;animation:card-deal .3s ease-out both}.playing-card small{align-self:flex-end;font-size:1rem}.red-card{color:#bd3030}.card-placeholder{background:#ffffff20;border:1px dashed #b4d3c2;box-shadow:none;animation:none}.card--small{width:38px;height:51px;padding:4px;font-size:1.1rem}.card--small small{font-size:.65rem}.card-back{background:repeating-linear-gradient(45deg,#203f73 0 5px,#e8d69f 5px 8px);color:#f8e6aa;align-items:center;justify-content:center;padding:0}.center-area{min-height:155px;display:flex;align-items:center;justify-content:center;gap:25px}.pot{text-align:center}.pot b{font-size:2.1rem;color:#ffe09a;display:block}.pot span{color:#c4e0d3;font-size:.75rem;text-transform:uppercase;letter-spacing:.12em}.board-label{color:#d7e5dd;font-size:.75rem;margin-bottom:6px;text-transform:uppercase;letter-spacing:.12em;text-align:center}.table-message{text-align:center;margin-top:10px;min-height:22px;color:#f5dd9a;font-size:.86rem}.thinking-dots{display:inline-flex;gap:4px;vertical-align:middle;margin-right:7px}.thinking-dots i{width:6px;height:6px;border-radius:50%;background:#f5dd9a;display:block;animation:thinking-dot 1.1s infinite}.thinking-dots i:nth-child(2){animation-delay:.15s}.thinking-dots i:nth-child(3){animation-delay:.3s}
      .action-feed{text-align:center;margin:.9rem 0;padding:.65rem 1rem;border:1px solid #ffffff2e;border-radius:12px;background:#061e18b8;color:#d8eddf;font-size:.95rem}.action-dock{min-height:94px;display:flex;align-items:center;justify-content:center}.action-wait{color:#a8cfc0;font-size:.95rem}.action-title{text-align:center;color:#f8dc92;margin:.7rem 0;font-size:1.15rem}div.stButton>button{border-radius:10px;font-weight:700;min-height:46px;border:1px solid #d3b061;background:#1c6452;color:#fff}div.stButton>button:hover{border-color:#ffdd88;color:#fff;background:#277c66}[data-testid="stSidebar"]{background:#061d18}[data-testid="stMetric"]{background:#0c3a2e;padding:12px;border-radius:10px}.stAlert{border-radius:10px}.log-line{padding:.45rem 0;border-bottom:1px solid #ffffff1c;color:#d2e6dc}@media(max-width:700px){.hero h1{font-size:2rem}.seat-info{min-width:55px}.seat-info span{display:none}.table{border-radius:45px;padding:16px}.seat-grid{grid-template-columns:1fr}.seat-three,.center-area,.human-seat{grid-column:1;width:100%}}
    </style>""", unsafe_allow_html=True)


def main() -> None:
    init_session()
    inject_style()
    session = st.session_state
    with st.sidebar:
        st.title("♠ Table Control")
        st.caption("A four-seat Texas Hold'em poker table")
        st.metric("Your stack", f"{session.stacks[0]} chips")
        st.metric("Hands played", session.hand_number)
        st.metric("Session result", f"{session.user_total:+.0f} chips")
        session.ai_delay = st.slider("AI thinking time", 0.5, 3.0, session.ai_delay, 0.5, format="%.1f seconds")
        st.divider()
        if st.button("New hand", use_container_width=True):
            begin_hand(); st.rerun()
        if st.button("Reset table", use_container_width=True):
            for key in list(session.keys()): del session[key]
            st.rerun()
        st.divider()
        st.markdown("**Table rules**\n\nFixed-limit Texas Hold'em: everyone antes 1 chip; bets/raises are 2 chips before and on the flop, then 4 chips on the turn and river. Each round allows two raises. All-ins create side pots automatically.")
        st.markdown("**Your opponents**\n\nAtlas raises often, Nova adapts, and Echo plays cautiously.")
    st.markdown("<div class='hero'><h1>THE QUAD TABLE</h1><p>One player. Three AI minds. Every chip matters.</p></div>", unsafe_allow_html=True)
    if session.hand is None:
        st.info("Take your seat and start a four-player hand.")
        if st.button("Deal the first hand", type="primary", use_container_width=True): begin_hand(); st.rerun()
        return
    hand = session.hand
    ai_turn = not hand["finished"] and hand["current"] != 0
    table_message = ""
    if ai_turn:
        player_name = PLAYERS[hand["current"]]["name"]
        table_message = f"<div class='table-message'><span class='thinking-dots'><i></i><i></i><i></i></span>{player_name} is thinking</div>"
    center = "<div class='center-area'><div class='pot'><span>Pot</span><b>" + str(sum(hand["contributions"])) + "</b></div><div><div class='board-label'>Community cards · " + hand["phase"] + "</div>" + cards_html(hand["board"], slots=5) + table_message + "</div></div>"
    table = ("<div class='table'><div class='seat-grid'>" + seat_html(1, hand) + seat_html(2, hand)
             + center + "<div class='seat-three'>" + seat_html(3, hand) + "</div>"
             + "<div class='human-seat'>" + seat_html(0, hand) + "</div></div></div>")
    st.markdown(table, unsafe_allow_html=True)
    st.markdown(f"<div class='action-feed'>Latest action: {escape(session.last_action)}</div>", unsafe_allow_html=True)
    if hand["finished"]:
        if st.button("Deal next hand", type="primary", use_container_width=True):
            begin_hand()
            st.rerun()
        names = ", ".join(PLAYERS[seat]["name"] for seat in hand["winners"])
        message = f"{names} win the {hand['pot']}-chip pot — {hand['reason']}."
        (st.success if 0 in hand["winners"] else st.info)(message)
        if hand["reason"] == "Showdown":
            reveal = " · ".join(f"{PLAYERS[seat]['name']}: {' '.join(rank + suit for rank, suit in hand['cards'][seat])}" for seat in live_seats(hand))
            st.caption(f"Showdown cards: {reveal}")
            strengths = " · ".join(
                f"{PLAYERS[seat]['name']}: {hand_description(best_five_hand(hand['cards'][seat], hand['board'])[0])}"
                for seat in live_seats(hand)
            )
            st.caption(f"Best hands: {strengths}")
        if len(hand["payouts"]) > 1:
            payout_text = " · ".join(
                f"{payout['label']}: {payout['amount']} chips to {', '.join(PLAYERS[seat]['name'] for seat in payout['winners'])}"
                for payout in hand["payouts"]
            )
            st.caption(payout_text)
    elif hand["current"] == 0:
        to_call = amount_to_call(hand, 0)
        prompt = "Your move — check or open the betting." if to_call == 0 else f"Your move — call {to_call} chips, raise, or fold."
        with st.container():
            st.markdown(f"<div class='action-title'>{prompt}</div>", unsafe_allow_html=True)
            actions = legal_actions(hand, 0)
            call_label = f"All-in {session.stacks[0]}" if session.stacks[0] <= to_call else f"Call {to_call}"
            labels = {"fold":"Fold", "check":"Check", "call":call_label, "raise":"Raise"}
            columns = st.columns(len(actions))
            for column, action in zip(columns, actions):
                if column.button(labels[action], type="primary" if action in {"call","check"} else "secondary", use_container_width=True): apply_action(hand, 0, action); st.rerun()
    else:
        seat = hand["current"]
        st.markdown("<div class='action-dock'><span class='action-wait'>The table is waiting for the AI move.</span></div>", unsafe_allow_html=True)
        time.sleep(session.ai_delay)
        apply_action(hand, seat, ai_action(hand, seat))
        st.rerun()
    with st.expander("Hand activity", expanded=False):
        for entry in reversed(session.log): st.markdown(f"<div class='log-line'>{escape(entry)}</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
