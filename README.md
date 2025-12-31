# Mistake Gravity Index (MGI)

Mistake Gravity Index is a decision-impact assistant coach for League of Legends.
It quantifies how damaging in-game mistakes are based on context and downstream consequences,
rather than treating all errors equally.

Built for the Sky’s The Limit – Cloud9 x JetBrains Hackathon.

## Quick Start Demo

```bash
# 1. List game titles to see what's available
python -m mgi.cli.main titles

# 2. List series for a specific tournament (LCS Summer 2024) filtered by team
python -m mgi.cli.main series list --tournament-id 774888 --team "Cloud9"

# 3. Fetch match data (events and end state) for a specific series
python -m mgi.cli.main series fetch --series-id 2689881

# 4. Run the Mistake Gravity Index analysis
python -m mgi.cli.main mistakes untraded --series-id 2689881
```
