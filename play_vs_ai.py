import random
from leduc_env import new_hand, legal_actions, apply_action, needs_board_card, deal_board, full_deck, utility_p0
from agents_and_sim import ExpectiminimaxAgent

RANK_NAME = {'J': 'Jack', 'Q': 'Queen', 'K': 'King'}


# This function displays the current game information and asks the human player to choose a legal action.
# It also accepts shorthand inputs such as f=fold, c=call/check, k=check, and r=raise.
def prompt_human_action(state, seat):
    acts = legal_actions(state)
    print(f"\nYour hole card: {RANK_NAME[state.hole[seat]]}")
    print(f"Board: {RANK_NAME[state.board] if state.board else '(none yet)'}")
    print(f"Pot: you={state.bets[seat]}  opponent={state.bets[1-seat]}")
    print(f"Legal actions: {acts}")
    while True:
        choice = input("Your action: ").strip().lower()
        if choice in acts:
            return choice
        shorthand = {'f': 'fold', 'c': 'call' if 'call' in acts else 'check',
                     'k': 'check', 'r': 'raise'}
        if choice in shorthand and shorthand[choice] in acts:
            return shorthand[choice]
        print(f"Invalid. Choose one of {acts} (or f/c/k/r).")


# This function controls the complete interactive poker game between the human player and the Expectiminimax AI.
# It creates each hand, deals cards, manages turns, calls the AI when needed, and displays the result.
def play_interactive():
    print("=== Leduc Hold'em: You vs Expectiminimax AI ===")
    print("Actions: fold, check, call, raise  (shorthand: f, k/c, r)\n")

    human_seat = 0 if input("Go first? (y/n): ").strip().lower().startswith('y') else 1
    ai_seat = 1 - human_seat
    ai = ExpectiminimaxAgent(ai_seat, max_depth=20)

    rng = random.Random()
    play_again = True
    human_total = 0.0

    # Repeat the game loop so the player can play multiple hands until they choose to stop.
    while play_again:
        deck = full_deck()
        rng.shuffle(deck)
        hole = {0: deck[0], 1: deck[1]} if human_seat == 0 else {0: deck[1], 1: deck[0]}
        h0, h1 = deck[0], deck[1]
        state = new_hand(h0, h1)

        print("\n" + "=" * 40)
        print(f"New hand. Your hole card: {RANK_NAME[state.hole[human_seat]]}")

        # Continue processing the current hand until a terminal game state is reached.
        while not state.terminal:
            # If the game requires a community/board card, randomly reveal one from the remaining deck.
            if needs_board_card(state):
                remaining = [c for c in full_deck()]
                for c in (state.hole[0], state.hole[1]):
                    remaining.remove(c)
                card = rng.choice(remaining)
                state = deal_board(state, card)
                print(f"\n--- Board card revealed: {RANK_NAME[card]} ---")
                continue

            # Check whose turn it is; the human chooses an action on their turn.
            if state.current == human_seat:
                action = prompt_human_action(state, human_seat)
            else:
                action = ai.act(state)
                print(f"\nAI action: {action}")
            state = apply_action(state, action)

        # Calculate the game's utility from player 0's perspective, then convert it to the human player's perspective.
        net_p0 = utility_p0(state)
        net_human = net_p0 if human_seat == 0 else -net_p0
        human_total += net_human

        print("\n--- Hand over ---")
        print(f"Your hole card: {RANK_NAME[state.hole[human_seat]]}  "
              f"AI hole card: {RANK_NAME[state.hole[ai_seat]]}  "
              f"Board: {RANK_NAME[state.board] if state.board else '(folded before flop)'}")
        if state.folded is not None:
            who = "You" if state.folded == human_seat else "AI"
            print(f"{who} folded.")
        print(f"Your net this hand: {net_human:+.0f} chips  |  Running total: {human_total:+.0f} chips")

        play_again = input("\nPlay another hand? (y/n): ").strip().lower().startswith('y')

    print(f"\nFinal result: {human_total:+.0f} chips over the session. Thanks for playing!")


# This condition ensures the game starts only when this file is executed directly, not when it is imported.
if __name__ == '__main__':
    play_interactive()
