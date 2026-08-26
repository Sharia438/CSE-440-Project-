# Four-Seat Texas Hold'em — CSE440 Project

The main app is a four-seat Texas Hold'em table: one human player competes
against three distinct AI opponents.

## Play the app

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

You always sit at the bottom of the table. The other seats are filled by:

- **Atlas** — aggressive and more likely to raise.
- **Nova** — strategic and balanced.
- **Echo** — careful and more willing to fold weak hands.

Each player starts with 100 chips. The app is an **ante-based fixed-limit**
Texas Hold'em table: every player antes one chip, bets/raises are two chips
pre-flop and on the flop, then four chips on the turn and river, with a
two-raise cap per betting round. Every player gets **two private hole cards**,
followed by the shared five-card board: **flop** (three cards), **turn**, and
**river**. The best five-card poker hand wins. All-in calls are supported,
remaining cards run out automatically when betting ends, and main/side pots
are awarded only to eligible players. A player who cannot cover a full fixed
raise may still call all-in, but cannot make a smaller raise. Use the **AI
thinking time** control to set a half-second to three-second pause before each
AI decision.

## Project files

- `streamlit_app.py` — polished four-player Texas Hold'em web experience.
- `leduc_env.py` — original two-player Leduc game environment.
- `agents_and_sim.py` — original Expectiminimax implementation, baseline AI
  agents, and evaluation harness.
- `play_vs_ai.py` — original two-player terminal game.

## Research component

The original two-player Expectiminimax agent remains available for the AI
algorithm and simulation section:

```bash
python agents_and_sim.py
```

Expectiminimax fits the two-player zero-sum Leduc variant. The interactive
Texas Hold'em table uses practical named AI play styles so it remains quick
and easy to play with three opponents.
