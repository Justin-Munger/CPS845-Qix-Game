# The Qix Game

A Python implementation of the classic arcade game Qix, where players claim territory by drawing lines while avoiding deadly enemies.

## Overview

The Qix Game is a territory-claiming arcade game where you control a marker that draws lines across the playfield. Your goal is to claim 75% of the screen by enclosing areas while avoiding two types of enemies: the Qix (octopus) that roams the open space, and the Sparx (starfish) that patrol the borders.

## How It Works

### Gameplay Mechanics

**Objective:** Claim 75% of the playfield to win

**Controls:**
- **Arrow Keys:** Move your character (bird)
- **SPACE:** Hold to draw trails into open territory
- **ENTER/SPACE:** Select menu options
- **ESC:** Exit game

### Game Rules

1. **Drawing Trails:**
   - Start from the border (white rocks)
   - Hold SPACE while moving into blue water
   - Your trail appears as a yellow line
   - Complete the trail by returning to the border or filled area (grass)

2. **Claiming Territory:**
   - When you complete a trail, it creates a new border
   - The smaller enclosed area gets filled with grass
   - The Qix must remain in the larger area

3. **Enemies:**
   - **Qix (Octopus):** Roams freely in empty space
   - **Sparx (Starfish):** Patrol the border perimeter
   - Touching either enemy or crossing your own trail costs a life

4. **Lives:**
   - Start with 9 lives
   - Game over when lives reach 0
   - Win by filling 75% of the area

### Difficulty Modes

**NORMAL:**
- 1 Qix
- 2 Sparx
- 9 Lives

**HARD:**
- 2 Qix
- 3 Sparx
- 9 Lives

## Installation

### Requirements

- Python 3.7 or higher
- Pygame library

### Setup

1. **Install Python:**
   - Download from [python.org](https://www.python.org/downloads/)
   - Ensure Python is added to your system PATH

2. **Install Pygame:**
```bash
   pip install pygame
```

3. **Download Game Files:**
   - Save `Qix.py` (the game code)
   - Optional: Download texture files for enhanced graphics

### Optional Assets

For the best visual experience, place these image files in the same directory as the game:

- `water.png` - Background water texture
- `grass.png` - Land/filled area texture
- `rock.png` - Border marker texture
- `bird.png` - Player character
- `octopus.png` - Qix enemy
- `starfish.png` - Sparx enemy

*The game will run without these files using colored rectangles as fallback graphics.*

## Running the Game

### Windows

1. Open Command Prompt or PowerShell
2. Navigate to the game directory:
```bash
   cd path\to\game\folder
```
3. Run the game:
```bash
   python Qix.py
```

### macOS/Linux

1. Open Terminal
2. Navigate to the game directory:
```bash
   cd path/to/game/folder
```
3. Run the game:
```bash
   python3 Qix.py
```
---

**Enjoy claiming territory and avoiding the Qix!**