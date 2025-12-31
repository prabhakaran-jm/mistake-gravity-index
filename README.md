# Mistake Gravity Index (MGI)

> **Why this matters for coaches:** In the flood of post-match data, identifying which deaths actually cost the game is a manual, exhausting process. MGI automates this by filtering out "traded" kills and highlighting the strategically catastrophic moments where a team loses a member under objective pressure without any reciprocal gain. It turns raw event logs into an actionable hit-list of game-losing mistakes.

Mistake Gravity Index is an assistant-coach analytics tool for League of Legends coaches and analysts.
It quantifies the strategic damage of in-game mistakes by analyzing "untraded deaths" and contextualizing them with objective pressure (Baron, Drake, Towers, etc.).

Built for the **Sky’s The Limit – Cloud9 x JetBrains Hackathon**.

## 🎯 The Problem
In professional League of Legends, not all deaths are equal. A death during a quiet laning phase is a setback; a death 20 seconds before Baron spawns, without a reciprocal kill trade, can lose the game. Coaches often struggle to filter through thousands of events to find the "game-losing" mistakes.

## 💡 The Solution
MGI identifies **untraded deaths**—kills where the victim's team fails to secure a return kill within the same fight cluster. It then applies a composite **Mistake Gravity Index (MGI) Score** based on:
- **Base Gravity:** Time-bucketed impact (Early, Mid, Late game).
- **Answer Status:** Bonuses for deaths that were completely unanswered by objective trades.
- **Objective Proximity:** High-weight bonuses for deaths occurring under "Pressure" (±30s) or "Context" (±90s) of major objectives.

## 🏗️ Architecture
- **Data Source:** Official [GRID Data API](https://grid.gg/).
- **API Clients:** Custom-built Python clients for Central Data (GraphQL) and File Download (REST) with session pooling.
- **Analysis Engine:** A multi-pass processor that clusters fight events and maps objective timelines to player deaths.
- **CLI Interface:** Built with `rich` for professional-grade console visualization and coach insights.

## 🛠️ Development & Junie's Role
This project was developed using **JetBrains PyCharm** and **Junie**. Junie acted as a primary development partner, assisting with:
- **Refactoring:** Centralizing API logic into a robust `BaseGridClient` and standardizing time parsing.
- **Stability:** Implementing snapshot testing to ensure scoring logic remains consistent across iterations.
- **UX/UI:** Designing the `rich` table layouts and the "Coach Insight" engine.
- **Compliance:** Auditing the project for hackathon rules and security best practices.

## 🚀 Quick Start Demo

```bash
# 1. List game titles to see what's available
python -m mgi.cli.main titles

# 2. List series for a specific tournament (LCS Summer 2024) filtered by team
python -m mgi.cli.main series list --tournament-id 774888 --team "Cloud9"

# 3. Fetch match data (events and end state) for a specific series
python -m mgi.cli.main series fetch --series-id 2689881

# 4. Run the Mistake Gravity Index analysis
python -m mgi.cli.main mistakes untraded --series-id 2689881 --window-seconds 25
```

## ⚙️ Setup
1. Clone the repository.
2. Install dependencies: `pip install -e .`
3. Create a `.env` file based on `.env.example` and add your `GRID_API_KEY`.
4. Run the commands above!
