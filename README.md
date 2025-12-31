# Mistake Gravity Index (MGI)

Mistake Gravity Index is a decision-impact assistant coach for League of Legends.
It quantifies how damaging in-game mistakes are based on context and downstream consequences,
rather than treating all errors equally.

Built for the Sky’s The Limit – Cloud9 x JetBrains Hackathon.

## Run

List Cloud9 series in LCS Summer 2024:  
python -m mgi.cli.main series list --tournament-id 774888 --team "Cloud9" --limit 20

Download match files:  
python -m mgi.cli.main series fetch --series-id 2689881

Detect untraded deaths:  
python -m mgi.cli.main mistakes untraded --series-id 2689881
