"""
Qix-like Territory Capture Game - Updated with Fixed Sparx and Rendering

A Python implementation of the classic Qix arcade game where players capture
territory by drawing lines while avoiding enemy entities.

Game Mechanics:
- Draw lines to capture territory (75% to win)
- Avoid Qix enemies that roam the play area
- Avoid Sparx enemies that patrol the perimeter
- Complete lines by returning to safe territory
"""

import pygame
import random
from dataclasses import dataclass
from typing import List, Set, Tuple
from enum import IntEnum


# ============================================================================
# GAME CONSTANTS AND ENUMS
# ============================================================================

class TileState(IntEnum):
    """Represents the state of a grid tile."""
    EMPTY = 0      # Uncaptured territory
    BORDER = 1     # Initial border or captured perimeter
    FILLED = 2     # Captured interior territory
    TRAIL = 3      # Player's active drawing trail


class GameState(IntEnum):
    """Represents the current game state."""
    MENU = 0
    PLAYING = 1
    GAMEOVER = 2
    WIN = 3


class Difficulty(IntEnum):
    """Game difficulty levels affecting enemy count."""
    NORMAL = 0  # 1 Qix, 2 Sparx
    HARD = 1    # 2 Qix, 3 Sparx


@dataclass
class GameConfig:
    """Configuration settings for game dimensions and timing."""
    
    # Grid and display settings
    TILE_SIZE: int = 8
    GRID_WIDTH: int = 80
    GRID_HEIGHT: int = 60
    FPS: int = 60
    HUD_HEIGHT: int = 20
    WINDOW_SCALE: float = 1.0
    
    # Game mechanics
    FILL_THRESHOLD: float = 0.75  # Win condition (75% territory)
    
    # Entity speeds (frames between moves)
    PLAYER_SPEED: int = 3
    QIX_SPEED: int = 4
    SPARX_SPEED: int = 5
    SPARX_COOLDOWN: int = 3  # Frames of cooldown after hitting player
    
    @property
    def screen_width(self) -> int:
        """Calculate scaled screen width."""
        return int(self.GRID_WIDTH * self.TILE_SIZE * self.WINDOW_SCALE)
    
    @property
    def screen_height(self) -> int:
        """Calculate scaled screen height."""
        return int(self.GRID_HEIGHT * self.TILE_SIZE * self.WINDOW_SCALE)
    
    @property
    def scaled_hud_height(self) -> int:
        """Calculate scaled HUD height."""
        return int(self.HUD_HEIGHT * self.WINDOW_SCALE)


# ============================================================================
# GRID MANAGEMENT
# ============================================================================

class Grid:
    """
    Manages the game grid state and territory calculations.
    
    The grid tracks which tiles are empty, filled, border, or trail.
    Uses caching to optimize fill percentage calculations.
    """
    
    __slots__ = ['width', 'height', 'tiles', '_fill_cache', '_cache_valid']
    
    def __init__(self, width: int, height: int):
        """
        Initialize grid with borders around the perimeter.
        
        Args:
            width: Grid width in tiles
            height: Grid height in tiles
        """
        self.width = width
        self.height = height
        self.tiles = [[TileState.EMPTY] * width for _ in range(height)]
        self._fill_cache = 0.0
        self._cache_valid = False
        self._initialize_borders()
    
    def _initialize_borders(self):
        """Set up initial border tiles around the perimeter."""
        # Top and bottom borders
        for x in range(self.width):
            self.tiles[0][x] = TileState.BORDER
            self.tiles[self.height - 1][x] = TileState.BORDER
        
        # Left and right borders
        for y in range(self.height):
            self.tiles[y][0] = TileState.BORDER
            self.tiles[y][self.width - 1] = TileState.BORDER
        
        self._cache_valid = False
    
    def in_bounds(self, y: int, x: int) -> bool:
        """Check if coordinates are within grid bounds."""
        return 0 <= x < self.width and 0 <= y < self.height
    
    def get(self, y: int, x: int) -> TileState:
        """
        Get tile state at coordinates.
        
        Returns BORDER if out of bounds to simplify collision logic.
        """
        if not self.in_bounds(y, x):
            return TileState.BORDER
        return self.tiles[y][x]
    
    def set(self, y: int, x: int, state: TileState):
        """Set tile state and invalidate cache."""
        if self.in_bounds(y, x):
            self.tiles[y][x] = state
            self._cache_valid = False
    
    def calculate_fill_percentage(self) -> float:
        """
        Calculate percentage of non-border tiles that are filled.
        
        Uses caching to avoid recalculating on every frame.
        
        Returns:
            Float between 0.0 and 1.0 representing fill percentage
        """
        if self._cache_valid:
            return self._fill_cache
        
        total = 0
        filled = 0
        
        for row in self.tiles:
            for tile in row:
                if tile != TileState.BORDER:
                    total += 1
                    if tile == TileState.FILLED:
                        filled += 1
        
        self._fill_cache = filled / total if total > 0 else 0.0
        self._cache_valid = True
        return self._fill_cache
    
    def flood_fill_fast(self, start_y: int, start_x: int) -> Set[Tuple[int, int]]:
        """
        Perform flood fill to find connected empty region.
        
        Uses iterative stack-based approach for performance.
        
        Args:
            start_y: Starting Y coordinate
            start_x: Starting X coordinate
            
        Returns:
            Set of (y, x) coordinates in the connected region
        """
        if not self.in_bounds(start_y, start_x):
            return set()
        if self.tiles[start_y][start_x] in (TileState.FILLED, TileState.BORDER):
            return set()
        
        visited = set()
        stack = [(start_y, start_x)]
        visited.add((start_y, start_x))
        
        while stack:
            y, x = stack.pop()
            
            # Check 4-directional neighbors
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                
                if (ny, nx) in visited:
                    continue
                if not self.in_bounds(ny, nx):
                    continue
                if self.tiles[ny][nx] in (TileState.FILLED, TileState.BORDER):
                    continue
                
                visited.add((ny, nx))
                stack.append((ny, nx))
        
        return visited


# ============================================================================
# GAME ENTITIES
# ============================================================================

class Player:
    """
    Represents the player character.
    
    The player moves along the perimeter and can draw trails into empty
    territory. Completing a trail captures the enclosed area.
    """
    
    __slots__ = ['x', 'y', 'vis_x', 'vis_y', 'lives', 'is_drawing', 'trail', 
                 'trail_start', 'last_key', 'move_timer', 'invincible_timer', 
                 'last_move_dx', 'last_move_dy']
    
    def __init__(self, x: int, y: int, lives: int = 9):
        """
        Initialize player at starting position.
        
        Args:
            x: Starting X coordinate
            y: Starting Y coordinate
            lives: Starting life count
        """
        self.x = x                      # Grid position
        self.y = y
        self.vis_x = float(x * 8)       # Visual position in pixels (interpolated)
        self.vis_y = float(y * 8)
        self.lives = lives
        self.is_drawing = False         # Currently drawing a trail
        self.trail = []                 # List of trail coordinates
        self.trail_start = None         # Where trail started
        self.last_key = None            # Last pressed direction key
        self.move_timer = 0             # Frames until next move
        self.invincible_timer = 0       # Invincibility frames after hit
        self.last_move_dx = 0           # Track movement for backtrack prevention
        self.last_move_dy = 0


class Qix:
    """
    Roaming enemy that moves randomly through empty territory.
    
    Contact with Qix while drawing is fatal. Qix bounces off walls
    and filled territory.
    """
    
    __slots__ = ['y', 'x', 'vel_y', 'vel_x', 'vis_x', 'vis_y', 'move_timer']
    
    def __init__(self, y: int, x: int):
        """Initialize Qix at starting position with random velocity."""
        self.y = y
        self.x = x
        self.vel_y = 1                  # Vertical velocity (-1 or 1)
        self.vel_x = 1                  # Horizontal velocity (-1 or 1)
        self.vis_x = float(x * 8)       # Visual position in pixels (interpolated)
        self.vis_y = float(y * 8)
        self.move_timer = 0             # Frames until next move


class Sparx:
    """
    Enemy that patrols the perimeter of captured territory.
    
    Sparx move along borders and can collide with the player when
    they're on the perimeter. Each Sparx has a direction preference.
    """
    
    __slots__ = ['pos', 'direction', 'index', 'vis_x', 'vis_y', 
                 'cooldown', 'move_timer', 'last_pos']
    
    def __init__(self, pos: Tuple[int, int], direction: int, index: int):
        """
        Initialize Sparx at perimeter position.
        
        Args:
            pos: Starting (y, x) position
            direction: Movement preference (1=clockwise, -1=counter-clockwise)
            index: Sparx identifier
        """
        self.pos = pos
        self.direction = direction      # Clockwise (1) or counter-clockwise (-1)
        self.index = index
        self.vis_x = float(pos[1] * 8)  # Visual position in pixels (interpolated)
        self.vis_y = float(pos[0] * 8)
        self.cooldown = 10              # Frames before can hit player again
        self.move_timer = 0             # Frames until next move
        self.last_pos = pos             # Previous position for pathfinding


# ============================================================================
# MAIN GAME CLASS
# ============================================================================

class QixGame:
    """
    Main game controller managing state, entities, and rendering.
    
    Handles the game loop, user input, collision detection, and
    territory capture mechanics.
    """
    
    def __init__(self):
        """Initialize game with menu state and load assets."""
        self.config = GameConfig()
        self.game_state = GameState.MENU
        self.selected_difficulty = Difficulty.NORMAL
        self.menu_selection = 0
        
        # Initialize Pygame
        pygame.init()
        self.screen = pygame.display.set_mode(
            (self.config.screen_width, 
             self.config.screen_height + self.config.scaled_hud_height)
        )
        pygame.display.set_caption("The Qix Game")
        self.clock = pygame.time.Clock()
        self._update_fonts()
        self._load_assets()
        
        # Game state (initialized when game starts)
        self.grid = None
        self.player = None
        self.qix_list = []
        self.sparx_list = []
        self.perimeter = set()          # Set of all perimeter tiles
        
        self.running = True
    
    def _update_fonts(self):
        """Initialize fonts with proper scaling."""
        scale = self.config.WINDOW_SCALE
        self.font = pygame.font.SysFont("consolas", int(18 * scale), bold=True)
        self.title_font = pygame.font.SysFont("consolas", int(42 * scale), bold=True)
        self.menu_font = pygame.font.SysFont("consolas", int(24 * scale), bold=True)
    
    def _load_assets(self):
        """Load image assets or create colored fallbacks."""
        try:
            # Load images without scaling - keep original resolution
            self.background_img = pygame.image.load("water.png").convert()
            self.land_img = pygame.image.load("grass.png").convert()
            self.rock_img = pygame.image.load("rock.png").convert_alpha()
            self.player_img = pygame.image.load("bird.png").convert_alpha()
            self.qix_img = pygame.image.load("octopus.png").convert_alpha()
            self.sparx_img = pygame.image.load("starfish.png").convert_alpha()
        except:
            # Fallback to colored rectangles if images not found
            size = self.config.TILE_SIZE
            self.background_img = pygame.Surface((size, size))
            self.background_img.fill((10, 10, 40))
            self.land_img = pygame.Surface((size, size))
            self.land_img.fill((40, 150, 40))
            self.rock_img = pygame.Surface((size, size))
            self.rock_img.fill((200, 200, 200))
            self.player_img = pygame.Surface((size, size))
            self.player_img.fill((255, 255, 255))
            self.qix_img = pygame.Surface((size, size))
            self.qix_img.fill((200, 50, 50))
            self.sparx_img = pygame.Surface((size, size))
            self.sparx_img.fill((255, 100, 0))
    
    def _initialize_game(self, difficulty: Difficulty):
        """
        Initialize new game with selected difficulty.
        
        Args:
            difficulty: NORMAL or HARD difficulty level
        """
        self.grid = Grid(self.config.GRID_WIDTH, self.config.GRID_HEIGHT)
        
        # Place player at bottom center
        start_x = self.config.GRID_WIDTH // 2
        start_y = self.config.GRID_HEIGHT - 1
        self.player = Player(start_x, start_y, lives=9)
        
        # Clear and initialize Qix based on difficulty
        self.qix_list = []
        if difficulty == Difficulty.NORMAL:
            self.qix_list.append(Qix(
                self.config.GRID_HEIGHT // 3, 
                self.config.GRID_WIDTH // 3
            ))
        else:  # HARD
            self.qix_list.append(Qix(
                self.config.GRID_HEIGHT // 3, 
                self.config.GRID_WIDTH // 3
            ))
            self.qix_list.append(Qix(
                self.config.GRID_HEIGHT * 2 // 3, 
                self.config.GRID_WIDTH * 2 // 3
            ))
        
        # Clear and compute perimeter, then initialize Sparx
        self.sparx_list = []
        self._compute_perimeter()
        self._initialize_sparx(difficulty)
        
        self.game_state = GameState.PLAYING
    
    def _compute_perimeter(self):
        """
        Calculate all tiles adjacent to empty space.
        
        The perimeter consists of all filled/border tiles that are
        adjacent (including diagonally) to empty tiles. This is where
        the player and Sparx can move.
        """
        self.perimeter = set()
        
        # Find all tiles adjacent to empty space
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                if self.grid.tiles[y][x] == TileState.EMPTY:
                    # Check 8-neighbors for non-empty tiles
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            if dy == 0 and dx == 0:
                                continue
                            ny, nx = y + dy, x + dx
                            if (self.grid.in_bounds(ny, nx) and 
                                self.grid.tiles[ny][nx] != TileState.EMPTY):
                                self.perimeter.add((ny, nx))
    
    def _initialize_sparx(self, difficulty: Difficulty):
        """
        Create Sparx enemies at perimeter positions.
        
        Args:
            difficulty: Determines number of Sparx (2 for NORMAL, 3 for HARD)
        """
        if not self.perimeter:
            return
        
        # Place Sparx opposite to player
        target_y = 0 if self.player.y > self.config.GRID_HEIGHT // 2 else self.config.GRID_HEIGHT - 1
        target_x = self.config.GRID_WIDTH - 1 - self.player.x
        
        # Find nearest perimeter tile to target
        start_pos = min(self.perimeter, 
                       key=lambda p: abs(p[0] - target_y) + abs(p[1] - target_x))
        
        # Create clockwise and counter-clockwise Sparx
        self.sparx_list.append(Sparx(start_pos, 1, 0))   # Clockwise
        self.sparx_list.append(Sparx(start_pos, -1, 0))  # Counter-clockwise
        
        # Add third Sparx for hard mode
        if difficulty == Difficulty.HARD:
            opposite_y = self.config.GRID_HEIGHT - 1 - target_y
            opposite_x = self.config.GRID_WIDTH - 1 - target_x
            third_pos = min(self.perimeter,
                           key=lambda p: abs(p[0] - opposite_y) + abs(p[1] - opposite_x))
            self.sparx_list.append(Sparx(third_pos, 1, 0))
    
    def handle_input(self) -> Tuple[int, int, bool]:
        """
        Process user input for current game state.
        
        Returns:
            Tuple of (dx, dy, space_pressed) for player movement
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                
                # Menu input
                if self.game_state == GameState.MENU:
                    if event.key == pygame.K_UP:
                        self.menu_selection = (self.menu_selection - 1) % 2
                    elif event.key == pygame.K_DOWN:
                        self.menu_selection = (self.menu_selection + 1) % 2
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE, 
                                      pygame.K_1, pygame.K_2):
                        if event.key == pygame.K_1:
                            self.menu_selection = 0
                        elif event.key == pygame.K_2:
                            self.menu_selection = 1
                        
                        difficulty = (Difficulty.NORMAL if self.menu_selection == 0 
                                    else Difficulty.HARD)
                        self.selected_difficulty = difficulty
                        self._initialize_game(difficulty)
                
                # Game over / win input
                elif self.game_state in (GameState.GAMEOVER, GameState.WIN):
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.game_state = GameState.MENU
                        self.menu_selection = 0
        
        # Return no input if not playing
        if self.game_state != GameState.PLAYING:
            return 0, 0, False
        
        # Get continuous key state for movement
        keys = pygame.key.get_pressed()
        key_mapping = {
            pygame.K_LEFT: (-1, 0),
            pygame.K_RIGHT: (1, 0),
            pygame.K_UP: (0, -1),
            pygame.K_DOWN: (0, 1)
        }
        
        # Track last pressed key for continuous movement
        for key, (dx, dy) in key_mapping.items():
            if keys[key]:
                if self.player.last_key is None or self.player.last_key != key:
                    self.player.last_key = key
                break
        
        # Get movement from last key
        dx, dy = 0, 0
        if self.player.last_key is not None:
            dx, dy = key_mapping[self.player.last_key]
            if not keys[self.player.last_key]:
                self.player.last_key = None
        
        return dx, dy, keys[pygame.K_SPACE]
    
    def update_player(self, dx: int, dy: int, trail_key: bool):
        """
        Update player position and trail state.
        
        Args:
            dx: Horizontal movement direction (-1, 0, 1)
            dy: Vertical movement direction (-1, 0, 1)
            trail_key: Whether space bar is held for drawing
        """
        # Update invincibility timer
        if self.player.invincible_timer > 0:
            self.player.invincible_timer -= 1
        
        # Handle movement timing
        self.player.move_timer += 1
        if self.player.move_timer < self.config.PLAYER_SPEED:
            return
        self.player.move_timer = 0
        
        if dx == 0 and dy == 0:
            return
        
        # Prevent moving backwards into own trail
        if self.player.is_drawing and len(self.player.trail) > 0:
            if (dx == -self.player.last_move_dx and dy == -self.player.last_move_dy):
                back_x = self.player.x - self.player.last_move_dx
                back_y = self.player.y - self.player.last_move_dy
                if (back_y, back_x) in self.player.trail:
                    return
        
        # Calculate new position
        nx = self.player.x + dx
        ny = self.player.y + dy
        
        if not self.grid.in_bounds(ny, nx):
            return
        
        current_tile = self.grid.tiles[self.player.y][self.player.x]
        next_tile = self.grid.tiles[ny][nx]
        
        # Prevent crossing gaps between border tiles
        if (current_tile in (TileState.BORDER, TileState.FILLED) and 
            next_tile in (TileState.BORDER, TileState.FILLED)):
            if not self._has_adjacent_empty(self.player.y, self.player.x, ny, nx, dx != 0):
                return
        
        # Check if move is valid
        can_move = (
            (ny, nx) in self.perimeter or
            (trail_key and next_tile == TileState.EMPTY) or
            next_tile == TileState.TRAIL
        )
        
        if not can_move:
            return
        
        # Start drawing trail
        if not self.player.is_drawing and next_tile == TileState.EMPTY:
            if current_tile in (TileState.BORDER, TileState.FILLED):
                self.player.trail_start = (self.player.y, self.player.x)
                self.player.is_drawing = True
                self.player.trail = []
        
        # Check Qix collision while drawing
        if self.player.is_drawing and self.player.invincible_timer == 0:
            for qix in self.qix_list:
                if (ny, nx) == (qix.y, qix.x):
                    self._handle_player_death()
                    return
        
        # Move player
        self.player.x, self.player.y = nx, ny
        self.player.last_move_dx = dx
        self.player.last_move_dy = dy
        
        # Update trail
        if self.player.is_drawing:
            if self.grid.tiles[self.player.y][self.player.x] == TileState.TRAIL:
                # Crossed own trail - death
                self._handle_player_death()
                return
            elif self.grid.tiles[self.player.y][self.player.x] == TileState.EMPTY:
                self.grid.set(self.player.y, self.player.x, TileState.TRAIL)
                self.player.trail.append((self.player.y, self.player.x))
        
        # Complete trail if reached safety
        if (self.player.is_drawing and 
            self.grid.tiles[self.player.y][self.player.x] in (TileState.BORDER, TileState.FILLED)):
            self._complete_trail()
    
    def _has_adjacent_empty(self, y1: int, x1: int, y2: int, x2: int, 
                            is_horizontal: bool) -> bool:
        """
        Check if movement between two border tiles has adjacent empty space.
        
        Prevents player from crossing through diagonal gaps in the border.
        
        Args:
            y1, x1: Starting position
            y2, x2: Ending position
            is_horizontal: True if moving horizontally, False if vertical
            
        Returns:
            True if move has adjacent empty space (is valid)
        """
        if is_horizontal:
            check_y1, check_y2 = y1 - 1, y1 + 1
            return (
                (self.grid.in_bounds(check_y1, x1) and 
                 self.grid.tiles[check_y1][x1] == TileState.EMPTY) or
                (self.grid.in_bounds(check_y2, x1) and 
                 self.grid.tiles[check_y2][x1] == TileState.EMPTY) or
                (self.grid.in_bounds(check_y1, x2) and 
                 self.grid.tiles[check_y1][x2] == TileState.EMPTY) or
                (self.grid.in_bounds(check_y2, x2) and 
                 self.grid.tiles[check_y2][x2] == TileState.EMPTY)
            )
        else:  # Vertical movement
            check_x1, check_x2 = x1 - 1, x1 + 1
            return (
                (self.grid.in_bounds(y1, check_x1) and 
                 self.grid.tiles[y1][check_x1] == TileState.EMPTY) or
                (self.grid.in_bounds(y1, check_x2) and 
                 self.grid.tiles[y1][check_x2] == TileState.EMPTY) or
                (self.grid.in_bounds(y2, check_x1) and 
                 self.grid.tiles[y2][check_x1] == TileState.EMPTY) or
                (self.grid.in_bounds(y2, check_x2) and 
                 self.grid.tiles[y2][check_x2] == TileState.EMPTY)
            )
    
    def _handle_player_death(self):
        """Handle player death by removing a life and resetting position."""
        self.player.lives -= 1
        self.player.invincible_timer = 60  # 1 second at 60 FPS
        self._reset_trail()
        if self.player.trail_start:
            self.player.y, self.player.x = self.player.trail_start
    
    def _reset_trail(self):
        """Clear player's active trail and reset drawing state."""
        for y, x in self.player.trail:
            if self.grid.tiles[y][x] == TileState.TRAIL:
                self.grid.set(y, x, TileState.EMPTY)
        self.player.trail.clear()
        self.player.is_drawing = False
    
    def _complete_trail(self):
        """
        Complete player's trail and fill captured territory.
        
        Marks trail as filled, finds disconnected regions, and fills
        the smallest region (not containing Qix). Updates perimeter
        and relocates entities as needed.
        """
        try:
            if not self.player.trail:
                self.player.is_drawing = False
                return
            
            # Mark trail as filled
            for y, x in self.player.trail:
                self.grid.set(y, x, TileState.FILLED)
            
            # Find all empty tiles
            all_empty = [
                (y, x) for y in range(self.grid.height) 
                for x in range(self.grid.width)
                if self.grid.tiles[y][x] == TileState.EMPTY
            ]
            
            # Find and fill smallest region without Qix
            if all_empty:
                regions = self._find_empty_regions(all_empty)
                
                if len(regions) > 1:
                    # Multiple regions - fill smallest one
                    smallest = min(regions, key=len)
                    for y, x in smallest:
                        self.grid.set(y, x, TileState.FILLED)
                elif len(regions) == 1:
                    # Single region - only fill if no Qix inside
                    region = regions[0]
                    qix_in_region = any((qix.y, qix.x) in region for qix in self.qix_list)
                    
                    if not qix_in_region:
                        # Empty region with no Qix - just keep trail as border
                        pass
            
            # Clean up
            self.player.trail.clear()
            self.player.is_drawing = False
            
            # Update game state
            self._compute_perimeter()
            self._remap_sparx()
            self._relocate_qix()
            self._teleport_player_to_perimeter()  # Teleport player if out of bounds
            
        except Exception as e:
            print(f"Trail completion error: {e}")
            self._reset_trail()
    
    def _find_empty_regions(self, all_empty: List[Tuple[int, int]]) -> List[Set[Tuple[int, int]]]:
        """
        Find all disconnected empty regions.
        
        Args:
            all_empty: List of all empty tile coordinates
            
        Returns:
            List of sets, each containing coordinates of one region
        """
        regions = []
        remaining = set(all_empty)
        
        while remaining:
            start_y, start_x = remaining.pop()
            region = self.grid.flood_fill_fast(start_y, start_x)
            if region:
                regions.append(region)
                remaining -= region
        
        return regions
    
    def _relocate_qix(self):
        """Relocate Qix that are trapped in filled territory."""
        for qix in self.qix_list:
            if self.grid.tiles[qix.y][qix.x] != TileState.EMPTY:
                # Find nearest empty tile
                empty_tiles = [
                    (y, x) for y in range(self.grid.height) 
                    for x in range(self.grid.width)
                    if self.grid.tiles[y][x] == TileState.EMPTY
                ]
                
                if empty_tiles:
                    nearest = min(empty_tiles, 
                                 key=lambda p: abs(p[0] - qix.y) + abs(p[1] - qix.x))
                    qix.y, qix.x = nearest
                    qix.vis_x = float(qix.x * 8)
                    qix.vis_y = float(qix.y * 8)
                    # Randomize velocity
                    qix.vel_x = 1 if random.random() > 0.5 else -1
                    qix.vel_y = 1 if random.random() > 0.5 else -1
    
    def _remap_sparx(self):
        """Remap Sparx to nearest valid perimeter position after territory change."""
        if not self.perimeter:
            return
        
        for sparx in self.sparx_list:
            old_pos = sparx.pos
            
            # Keep position if still valid
            if old_pos in self.perimeter:
                continue
            
            # Find nearest perimeter tile
            nearest = min(self.perimeter, 
                         key=lambda p: abs(p[0] - old_pos[0]) + abs(p[1] - old_pos[1]))
            sparx.pos = nearest
            # Note: Do NOT reverse direction when remapping after trail completion
    
    def _teleport_player_to_perimeter(self):
        """Teleport player to nearest perimeter tile if they're out of bounds."""
        if not self.perimeter:
            return
        
        player_pos = (self.player.y, self.player.x)
        
        # Check if player is on valid perimeter
        if player_pos in self.perimeter:
            return
        
        # Find nearest perimeter tile using Manhattan distance
        nearest = min(self.perimeter,
                     key=lambda p: abs(p[0] - self.player.y) + abs(p[1] - self.player.x))
        
        self.player.y, self.player.x = nearest
        print(f"Player teleported to nearest perimeter: {nearest}")
    
    def update_qix(self):
        """
        Update all Qix positions and check collisions.
        
        Qix move randomly through empty territory, bouncing off walls
        and filled areas. Randomly change direction occasionally.
        """
        for qix in self.qix_list:
            qix.move_timer += 1
            if qix.move_timer < self.config.QIX_SPEED:
                continue
            qix.move_timer = 0
            
            # Randomly change direction
            if random.random() < 0.02:
                if random.random() < 0.5:
                    qix.vel_y *= -1
                if random.random() < 0.5:
                    qix.vel_x *= -1
            
            # Calculate new position
            ny = qix.y + qix.vel_y
            nx = qix.x + qix.vel_x
            
            # Bounce off walls or filled territory
            if (not self.grid.in_bounds(ny, nx) or 
                self.grid.tiles[ny][nx] in (TileState.FILLED, TileState.BORDER)):
                
                if (not self.grid.in_bounds(ny, nx) or 
                    self.grid.tiles[ny][nx] == TileState.BORDER):
                    # Hit border - reverse both
                    qix.vel_y *= -1
                    qix.vel_x *= -1
                else:
                    # Hit filled - reverse individual components
                    if (not self.grid.in_bounds(ny, qix.x) or 
                        self.grid.tiles[ny][qix.x] in (TileState.FILLED, TileState.BORDER)):
                        qix.vel_y *= -1
                    if (not self.grid.in_bounds(qix.y, nx) or 
                        self.grid.tiles[qix.y][nx] in (TileState.FILLED, TileState.BORDER)):
                        qix.vel_x *= -1
                
                # Recalculate after bounce
                ny = qix.y + qix.vel_y
                nx = qix.x + qix.vel_x
            
            # Move if valid
            if (self.grid.in_bounds(ny, nx) and 
                self.grid.tiles[ny][nx] in (TileState.EMPTY, TileState.TRAIL)):
                qix.y, qix.x = ny, nx
            
            # Check trail collision (only if player not invincible)
            if (self.player.invincible_timer == 0 and 
                (qix.y, qix.x) in self.player.trail):
                self._handle_player_death()
    
    def update_sparx(self):
        """
        Update all Sparx positions along perimeter.
        
        Sparx patrol the perimeter using intelligent pathfinding that
        prefers their directional bias (clockwise/counter-clockwise).
        Checks for player collisions.
        """
        for sparx in self.sparx_list:
            # Reduce cooldown timer
            if sparx.cooldown > 0:
                sparx.cooldown -= 1
            
            sparx.move_timer += 1
            if sparx.move_timer < self.config.SPARX_SPEED:
                continue
            sparx.move_timer = 0
            
            if not self.perimeter:
                continue
            
            old_pos = sparx.pos
            
            # Check trail start collision BEFORE moving (instant death if Sparx reaches trail start)
            if self.player.is_drawing and old_pos == self.player.trail_start:
                print("Sparx hit trail start!")
                self._handle_player_death()
                sparx.direction *= -1  # Reverse direction when hitting trail
                sparx.cooldown = self.config.SPARX_COOLDOWN
                sparx.last_pos = None
                return
            
            # Find all valid adjacent perimeter moves
            valid_moves = []
            for dy, dx in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                ny, nx = old_pos[0] + dy, old_pos[1] + dx
                new_pos = (ny, nx)
                
                if new_pos not in self.perimeter:
                    continue
                
                # Check gap crossing (same as player logic)
                if self._can_move_between_borders(old_pos, new_pos, dx != 0):
                    valid_moves.append((new_pos, dy, dx))
            
            # Choose best move based on direction and avoiding backtracking
            new_pos = None
            if valid_moves:
                new_pos = self._choose_best_sparx_move(sparx, valid_moves, old_pos)
                if new_pos:
                    sparx.last_pos = old_pos
                    sparx.pos = new_pos
            else:
                # Try diagonal moves if no 4-directional moves available
                for dy, dx in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
                    ny, nx = old_pos[0] + dy, old_pos[1] + dx
                    if (ny, nx) in self.perimeter:
                        sparx.last_pos = old_pos
                        sparx.pos = (ny, nx)
                        new_pos = (ny, nx)
                        break
            
            # If Sparx didn't move, skip collision checks
            if new_pos is None or new_pos == old_pos:
                continue
            
            # === COLLISION CHECKS (all wrapped behind cooldown) ===
            if sparx.cooldown == 0 and self.player.invincible_timer == 0:
                player_pos = (self.player.y, self.player.x)
                
                # A. Player is exactly on new tile
                if player_pos == sparx.pos:
                    self.player.lives -= 1
                    self.player.invincible_timer = 60
                    sparx.direction *= -1  # Reverse direction on hit
                    sparx.cooldown = self.config.SPARX_COOLDOWN
                    sparx.last_pos = None
                    print(f"Sparx hit player at new position! Direction reversed to {sparx.direction}. Lives: {self.player.lives}")
                    continue
                
                # B. Player is exactly on old tile
                if player_pos == old_pos:
                    self.player.lives -= 1
                    self.player.invincible_timer = 60
                    sparx.direction *= -1  # Reverse direction on hit
                    sparx.cooldown = self.config.SPARX_COOLDOWN
                    sparx.last_pos = None
                    print(f"Sparx hit player at old position! Direction reversed to {sparx.direction}. Lives: {self.player.lives}")
                    continue
                
                # C. Player crossed through segment old → new
                if self._player_crossed_segment(old_pos, sparx.pos, player_pos):
                    self.player.lives -= 1
                    self.player.invincible_timer = 60
                    sparx.direction *= -1  # Reverse direction on hit
                    sparx.cooldown = self.config.SPARX_COOLDOWN
                    sparx.last_pos = None
                    print(f"Sparx crossed player path! Direction reversed to {sparx.direction}. Lives: {self.player.lives}")
    
    def _can_move_between_borders(self, pos1: Tuple[int, int], 
                                   pos2: Tuple[int, int], 
                                   is_horizontal: bool) -> bool:
        """
        Check if movement between two border tiles is valid.
        
        Prevents crossing through diagonal gaps in the border.
        
        Args:
            pos1: Starting (y, x) position
            pos2: Ending (y, x) position
            is_horizontal: True if horizontal move, False if vertical
            
        Returns:
            True if move is valid (has adjacent empty space)
        """
        y1, x1 = pos1
        y2, x2 = pos2
        
        current_tile = self.grid.tiles[y1][x1]
        next_tile = self.grid.tiles[y2][x2]
        
        # If not both border/filled, move is always valid
        if not (current_tile in (TileState.BORDER, TileState.FILLED) and 
                next_tile in (TileState.BORDER, TileState.FILLED)):
            return True
        
        return self._has_adjacent_empty(y1, x1, y2, x2, is_horizontal)
    
    def _choose_best_sparx_move(self, sparx: Sparx, 
                                valid_moves: List[Tuple[Tuple[int, int], int, int]], 
                                old_pos: Tuple[int, int]) -> Tuple[int, int]:
        """
        Choose best move for Sparx based on direction preference.
        
        Args:
            sparx: The Sparx entity
            valid_moves: List of (position, dy, dx) tuples
            old_pos: Current position
            
        Returns:
            Best new position for Sparx
        """
        # Calculate where we came from (using last_pos if available and not None)
        last_dy = 0
        last_dx = 0
        
        if (hasattr(sparx, 'last_pos') and 
            sparx.last_pos is not None and 
            sparx.last_pos != old_pos):
            last_dy = old_pos[0] - sparx.last_pos[0]
            last_dx = old_pos[1] - sparx.last_pos[1]
        
        best_move = None
        best_score = -999
        
        for new_pos, dy, dx in valid_moves:
            score = 0
            
            # CRITICAL: Heavily penalize backtracking (going opposite to last move)
            # This is the most important rule - never go backwards
            if last_dy != 0 or last_dx != 0:
                if dy == -last_dy and dx == -last_dx:
                    score -= 1000  # Increased penalty to ensure it's never chosen
                    continue  # Skip this move entirely
            
            # Apply directional preference based on clockwise/counter-clockwise
            # This now has priority since we skip backwards moves
            if sparx.direction == 1:  # Clockwise: prefer right > down > left > up
                if dx == 1 and dy == 0:      # right
                    score += 100
                elif dy == 1 and dx == 0:    # down
                    score += 75
                elif dx == -1 and dy == 0:   # left
                    score += 50
                elif dy == -1 and dx == 0:   # up
                    score += 25
            else:  # Counter-clockwise: prefer left > up > right > down
                if dx == -1 and dy == 0:     # left
                    score += 100
                elif dy == -1 and dx == 0:   # up
                    score += 75
                elif dx == 1 and dy == 0:    # right
                    score += 50
                elif dy == 1 and dx == 0:    # down
                    score += 25
            
            # Small bonus for continuing in same direction (but less than directional preference)
            # Only apply if we have a valid last movement
            if (last_dy != 0 or last_dx != 0) and dy == last_dy and dx == last_dx:
                score += 10
            
            if score > best_score:
                best_score = score
                best_move = new_pos
        
        return best_move
    
    def _player_crossed_segment(self, old_pos: Tuple[int, int], 
                                new_pos: Tuple[int, int], 
                                player_pos: Tuple[int, int]) -> bool:
        """
        Check if player position lies on segment between old and new Sparx positions.
        
        Used to detect collisions when player and Sparx cross paths.
        
        Args:
            old_pos: Sparx's previous position
            new_pos: Sparx's current position
            player_pos: Player's current position
            
        Returns:
            True if player crossed the Sparx's movement path
        """
        oy, ox = old_pos
        ny, nx = new_pos
        py, px = player_pos
        
        # Horizontal movement
        if oy == ny == py:
            return (ox < px < nx) or (nx < px < ox)
        
        # Vertical movement
        if ox == nx == px:
            return (oy < py < ny) or (ny < py < oy)
        
        return False
    
    def check_game_over(self) -> bool:
        """
        Check win/loss conditions.
        
        Returns:
            True if game is over (win or loss)
        """
        if self.player.lives < 1:
            self.game_state = GameState.GAMEOVER
            return True
        
        if self.grid.calculate_fill_percentage() >= self.config.FILL_THRESHOLD:
            self.game_state = GameState.WIN
            return True
        
        return False
    
    def render(self):
        """Render the game world, entities, and HUD."""
        tile_size = self.config.TILE_SIZE
        
        # Background - blit full image at position (0,0)
        self.screen.blit(self.background_img, (0, 0))
        
        # Grid tiles (filled and border) - use direct texture blitting like old version
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                if self.grid.tiles[y][x] in (TileState.BORDER, TileState.FILLED):
                    # Calculate texture coordinates with wrapping
                    tx = (x * tile_size) % self.land_img.get_width()
                    ty = (y * tile_size) % self.land_img.get_height()
                    
                    # Blit directly from land_img using texture coordinates
                    rect = pygame.Rect(x * tile_size, y * tile_size, tile_size, tile_size)
                    self.screen.blit(self.land_img, rect, pygame.Rect(tx, ty, tile_size, tile_size))
        
        # HUD background (tiled land texture)
        hud_y = self.config.screen_height
        self.screen.blit(self.land_img, (0, hud_y), pygame.Rect(0, hud_y, self.config.screen_width, self.config.HUD_HEIGHT))
        
        # Trail (yellow rectangles showing player's drawing)
        for y, x in self.player.trail[:-1]:  # Skip last tile to match old version
            pygame.draw.rect(
                self.screen, 
                (255, 200, 0), 
                pygame.Rect(x * tile_size, y * tile_size, tile_size, tile_size)
            )
        
        # Perimeter markers (rocks) - positioned with slight offset like old version
        for y, x in self.perimeter:
            pos = ((x * tile_size) - 1, (y * tile_size) - 1)
            self.screen.blit(self.rock_img, pos)
        
        # Player (with interpolation for smooth movement)
        self.player.vis_x += (self.player.x * tile_size - self.player.vis_x) * 0.4
        self.player.vis_y += (self.player.y * tile_size - self.player.vis_y) * 0.4
        
        # Flash player when invincible
        if not (self.player.invincible_timer > 0 and 
                (self.player.invincible_timer // 5) % 2 == 0):
            # Offset player image by -3 pixels like old version
            self.screen.blit(self.player_img, (int(self.player.vis_x) - 3, int(self.player.vis_y) - 3))
        
        # Qix enemies with smooth interpolation
        for qix in self.qix_list:
            target_x = qix.x * tile_size
            target_y = qix.y * tile_size
            qix.vis_x += (target_x - qix.vis_x) * 0.3
            qix.vis_y += (target_y - qix.vis_y) * 0.3
            # Offset qix image by -4 pixels like old version
            self.screen.blit(self.qix_img, (int(qix.vis_x) - 4, int(qix.vis_y) - 4))
        
        # Sparx enemies with smooth interpolation
        for sparx in self.sparx_list:
            target_x = sparx.pos[1] * tile_size
            target_y = sparx.pos[0] * tile_size
            sparx.vis_x += (target_x - sparx.vis_x) * 0.2
            sparx.vis_y += (target_y - sparx.vis_y) * 0.2
            # Offset sparx image like old version
            self.screen.blit(self.sparx_img, (int(sparx.vis_x) - 3, int(sparx.vis_y) - 4))
        
        # HUD text
        fill_pct = int(self.grid.calculate_fill_percentage() * 100)
        hud_text = self.font.render(
            f"Lifeforce: {self.player.lives}  Filled: {fill_pct}%", 
            True, 
            (0, 0, 0)
        )
        self.screen.blit(hud_text, (0, hud_y + 2))
        
        pygame.display.flip()
    
    def render_menu(self):
        """Render the main menu screen."""
        self.screen.fill((20, 20, 60))
        scale = self.config.WINDOW_SCALE
        center_x = self.config.screen_width // 2
        center_y = self.config.screen_height // 2
        
        # Title
        title = self.title_font.render("THE QIX GAME", True, (255, 255, 100))
        self.screen.blit(title, title.get_rect(center=(center_x, center_y - int(180 * scale))))
        
        # Difficulty selection
        y_offset = center_y - int(100 * scale)
        select = self.menu_font.render("SELECT DIFFICULTY:", True, (255, 255, 100))
        self.screen.blit(select, select.get_rect(center=(center_x, y_offset)))
        
        difficulties = [
            ("NORMAL (2 Sparx, 1 Qix)", 0), 
            ("HARD (3 Sparx, 2 Qix)", 1)
        ]
        y_offset += int(45 * scale)
        
        for text, index in difficulties:
            color = (100, 255, 100) if index == self.menu_selection else (200, 200, 200)
            prefix = "> " if index == self.menu_selection else "  "
            option = self.menu_font.render(f"{prefix}{text}", True, color)
            self.screen.blit(option, option.get_rect(center=(center_x, y_offset)))
            y_offset += int(40 * scale)
        
        # Instructions
        y_offset = center_y + int(50 * scale)
        instructions = [
            "HOW TO PLAY:",
            "Arrow keys to navigate / move",
            "ENTER or SPACE to select / draw",
            "Capture 75% area to win!",
            "Avoid Qix and Sparx enemies"
        ]
        
        for line in instructions:
            color = (255, 255, 100) if line == "HOW TO PLAY:" else (180, 180, 180)
            text = self.font.render(line, True, color)
            self.screen.blit(text, text.get_rect(center=(center_x, y_offset)))
            y_offset += int(24 * scale)
        
        pygame.display.flip()
    
    def render_game_over(self):
        """Render the game over screen."""
        self.screen.fill((60, 20, 20))
        scale = self.config.WINDOW_SCALE
        center_x = self.config.screen_width // 2
        
        title = self.title_font.render("GAME OVER", True, (255, 100, 100))
        self.screen.blit(title, title.get_rect(center=(center_x, int(150 * scale))))
        
        fill_pct = int(self.grid.calculate_fill_percentage() * 100)
        stats = self.menu_font.render(
            f"Area Captured: {fill_pct}%", 
            True, 
            (255, 255, 255)
        )
        self.screen.blit(stats, stats.get_rect(center=(center_x, int(250 * scale))))
        
        cont = self.menu_font.render(
            "Press ENTER to Continue", 
            True, 
            (200, 200, 200)
        )
        self.screen.blit(cont, cont.get_rect(center=(center_x, int(350 * scale))))
        
        pygame.display.flip()
    
    def render_win(self):
        """Render the victory screen."""
        self.screen.fill((20, 60, 20))
        scale = self.config.WINDOW_SCALE
        center_x = self.config.screen_width // 2
        
        title = self.title_font.render("VICTORY!", True, (100, 255, 100))
        self.screen.blit(title, title.get_rect(center=(center_x, int(150 * scale))))
        
        diff_names = {Difficulty.NORMAL: "NORMAL", Difficulty.HARD: "HARD"}
        diff = self.menu_font.render(
            f"Difficulty: {diff_names[self.selected_difficulty]}", 
            True, 
            (255, 255, 255)
        )
        self.screen.blit(diff, diff.get_rect(center=(center_x, int(230 * scale))))
        
        lives = self.menu_font.render(
            f"Lives Remaining: {self.player.lives}", 
            True, 
            (255, 255, 255)
        )
        self.screen.blit(lives, lives.get_rect(center=(center_x, int(280 * scale))))
        
        fill_pct = int(self.grid.calculate_fill_percentage() * 100)
        stats = self.menu_font.render(
            f"Area Captured: {fill_pct}%", 
            True, 
            (255, 255, 255)
        )
        self.screen.blit(stats, stats.get_rect(center=(center_x, int(330 * scale))))
        
        cont = self.menu_font.render(
            "Press ENTER to Continue", 
            True, 
            (200, 200, 200)
        )
        self.screen.blit(cont, cont.get_rect(center=(center_x, int(410 * scale))))
        
        pygame.display.flip()
    
    def run(self):
        """
        Main game loop.
        
        Processes input, updates game state, and renders based on
        current game state (menu, playing, game over, win).
        """
        while self.running:
            self.clock.tick(self.config.FPS)
            
            dx, dy, trail_key = self.handle_input()
            
            if self.game_state == GameState.MENU:
                self.render_menu()
            
            elif self.game_state == GameState.PLAYING:
                self.update_player(dx, dy, trail_key)
                self.update_qix()
                self.update_sparx()
                self.render()
                self.check_game_over()
            
            elif self.game_state == GameState.GAMEOVER:
                self.render_game_over()
            
            elif self.game_state == GameState.WIN:
                self.render_win()
        
        pygame.quit()


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    game = QixGame()
    game.run()