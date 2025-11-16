"""
Qix-like Game - A territory claiming game where players draw lines to capture areas
while avoiding enemies (Qix and Sparx).
"""

import pygame
import random
from collections import deque
from dataclasses import dataclass
from typing import List, Set, Tuple, Optional
from enum import IntEnum


# ============================================================================
# CONSTANTS AND ENUMS
# ============================================================================

class TileState(IntEnum):
    """Represents the state of a grid tile."""
    EMPTY = 0
    BORDER = 1
    FILLED = 2
    TRAIL = 3


class GameState(IntEnum):
    """Represents the current state of the game."""
    MENU = 0
    PLAYING = 1
    GAMEOVER = 2
    WIN = 3


class Difficulty(IntEnum):
    """Represents game difficulty levels."""
    EASY = 9
    MEDIUM = 6
    HARD = 3


@dataclass
class GameConfig:
    """Configuration settings for the game."""
    # Grid settings
    TILE_SIZE: int = 8
    GRID_WIDTH: int = 80
    GRID_HEIGHT: int = 60
    
    # Display settings
    FPS: int = 60
    HUD_HEIGHT: int = 20
    WINDOW_SCALE: float = 1.0  # Adjustable window scale
    
    # Game rules
    FILL_THRESHOLD: float = 0.75
    INITIAL_LIVES: int = 9
    
    # Movement speeds (frames between moves - higher = slower)
    PLAYER_SPEED: int = 3
    QIX_SPEED: int = 4
    SPARX_SPEED: int = 5
    SPARX_COOLDOWN: int = 3
    
    # Colors
    COL_EMPTY: Tuple[int, int, int] = (10, 10, 40)
    COL_BORDER: Tuple[int, int, int] = (40, 150, 40)
    COL_FILLED: Tuple[int, int, int] = (40, 150, 40)
    COL_TRAIL: Tuple[int, int, int] = (255, 200, 0)
    COL_PLAYER: Tuple[int, int, int] = (255, 255, 255)
    COL_QIX: Tuple[int, int, int] = (200, 50, 50)
    COL_PERIMETER: Tuple[int, int, int] = (200, 200, 200)
    COL_HUD_BG: Tuple[int, int, int] = (255, 255, 255)
    COL_HUD_TEXT: Tuple[int, int, int] = (0, 0, 0)
    
    @property
    def screen_width(self) -> int:
        return int(self.GRID_WIDTH * self.TILE_SIZE * self.WINDOW_SCALE)
    
    @property
    def screen_height(self) -> int:
        return int(self.GRID_HEIGHT * self.TILE_SIZE * self.WINDOW_SCALE)
    
    @property
    def scaled_tile_size(self) -> int:
        return int(self.TILE_SIZE * self.WINDOW_SCALE)
    
    @property
    def scaled_hud_height(self) -> int:
        return int(self.HUD_HEIGHT * self.WINDOW_SCALE)


# ============================================================================
# UTILITY CLASSES
# ============================================================================

class Grid:
    """Manages the game grid and tile states."""
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.tiles = [[TileState.EMPTY for _ in range(width)] for _ in range(height)]
        self._initialize_borders()
    
    def _initialize_borders(self):
        """Set up the perimeter borders."""
        for x in range(self.width):
            self.tiles[0][x] = TileState.BORDER
            self.tiles[self.height - 1][x] = TileState.BORDER
        for y in range(self.height):
            self.tiles[y][0] = TileState.BORDER
            self.tiles[y][self.width - 1] = TileState.BORDER
    
    def in_bounds(self, y: int, x: int) -> bool:
        """Check if coordinates are within grid bounds."""
        return 0 <= x < self.width and 0 <= y < self.height
    
    def get(self, y: int, x: int) -> TileState:
        """Get tile state at position."""
        if not self.in_bounds(y, x):
            return TileState.BORDER
        return self.tiles[y][x]
    
    def set(self, y: int, x: int, state: TileState):
        """Set tile state at position."""
        if self.in_bounds(y, x):
            self.tiles[y][x] = state
    
    def flood_fill(self, start_positions: List[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        """
        Return set of tiles reachable from start positions via 4-neighbor moves
        across tiles that are not FILLED or BORDER.
        """
        visited = set()
        queue = deque()
        
        for sy, sx in start_positions:
            if not self.in_bounds(sy, sx) or (sy, sx) in visited:
                continue
            if self.get(sy, sx) in (TileState.FILLED, TileState.BORDER):
                continue
            visited.add((sy, sx))
            queue.append((sy, sx))
        
        while queue:
            y, x = queue.popleft()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if not self.in_bounds(ny, nx) or (ny, nx) in visited:
                    continue
                if self.get(ny, nx) in (TileState.FILLED, TileState.BORDER):
                    continue
                visited.add((ny, nx))
                queue.append((ny, nx))
        
        return visited
    
    def calculate_fill_percentage(self) -> float:
        """Calculate percentage of non-border tiles that are filled."""
        total = 0
        filled = 0
        for row in self.tiles:
            for tile in row:
                if tile != TileState.BORDER:
                    total += 1
                    if tile == TileState.FILLED:
                        filled += 1
        return filled / total if total > 0 else 0.0


# ============================================================================
# GAME ENTITIES
# ============================================================================

class Player:
    """Represents the player character."""
    
    def __init__(self, x: int, y: int, lives: int = 9):
        self.x = x
        self.y = y
        self.vis_x = float(x * GameConfig.TILE_SIZE)
        self.vis_y = float(y * GameConfig.TILE_SIZE)
        self.lives = lives
        self.is_drawing = False
        self.trail: List[Tuple[int, int]] = []
        self.trail_start: Optional[Tuple[int, int]] = None
        self.last_key: Optional[int] = None
        self.move_timer = 0
    
    def take_damage(self):
        """Reduce player lives by 1."""
        self.lives -= 1
        print(f"Player hit! Lives remaining: {self.lives}")
    
    def start_trail(self, y: int, x: int):
        """Begin drawing a trail."""
        self.is_drawing = True
        self.trail = []
        self.trail_start = (y, x)
        print(f"Trail started at {self.trail_start}")
    
    def reset_trail(self, grid: Grid):
        """Clear the current trail from the grid."""
        for y, x in self.trail:
            if grid.get(y, x) == TileState.TRAIL:
                grid.set(y, x, TileState.EMPTY)
        self.trail.clear()
        self.is_drawing = False
    
    def update_visual_position(self, tile_size: int):
        """Smoothly interpolate visual position toward actual position."""
        target_x = self.x * tile_size
        target_y = self.y * tile_size
        self.vis_x += (target_x - self.vis_x) * 0.4
        self.vis_y += (target_y - self.vis_y) * 0.4


class Qix:
    """Represents the main enemy (Qix) that roams the play area."""
    
    def __init__(self, y: int, x: int, tile_size: int = 8):
        self.y = y
        self.x = x
        self.vel_y = 1
        self.vel_x = 1
        self.tile_size = tile_size
        self.vis_x = float(x * tile_size)
        self.vis_y = float(y * tile_size)
        self.move_timer = 0
    
    def move(self, grid: Grid):
        """Move the Qix with random walk behavior."""
        # Occasionally change direction randomly
        if random.random() < 0.02:
            if random.random() < 0.5:
                self.vel_y *= -1
            if random.random() < 0.5:
                self.vel_x *= -1
        
        ny = self.y + self.vel_y
        nx = self.x + self.vel_x
        
        # Bounce off FILLED or BORDER tiles
        if not grid.in_bounds(ny, nx) or grid.get(ny, nx) in (TileState.FILLED, TileState.BORDER):
            if not grid.in_bounds(ny, nx) or grid.get(ny, nx) == TileState.BORDER:
                self.vel_y *= -1
                self.vel_x *= -1
            else:
                # Reverse only the offending axis
                if not grid.in_bounds(ny, self.x) or grid.get(ny, self.x) in (TileState.FILLED, TileState.BORDER):
                    self.vel_y *= -1
                if not grid.in_bounds(self.y, nx) or grid.get(self.y, nx) in (TileState.FILLED, TileState.BORDER):
                    self.vel_x *= -1
            
            ny = self.y + self.vel_y
            nx = self.x + self.vel_x
        
        # Only move if destination is empty or trail
        if grid.in_bounds(ny, nx) and grid.get(ny, nx) in (TileState.EMPTY, TileState.TRAIL):
            self.y, self.x = ny, nx
    
    def update_visual_position(self):
        """Smoothly interpolate visual position toward actual position."""
        target_x = self.x * self.tile_size
        target_y = self.y * self.tile_size
        self.vis_x += (target_x - self.vis_x) * 0.3
        self.vis_y += (target_y - self.vis_y) * 0.3


class Sparx:
    """Represents a Sparx enemy that patrols the perimeter."""
    
    def __init__(self, pos: Tuple[int, int], direction: int, index: int, tile_size: int = 8):
        self.pos = pos
        self.direction = direction  # 1 = clockwise, -1 = counterclockwise
        self.index = index
        self.tile_size = tile_size
        self.vis_x = float(pos[1] * tile_size)
        self.vis_y = float(pos[0] * tile_size)
        self.cooldown = 0
    
    def move(self, ordered_perimeter: List[Tuple[int, int]]):
        """Move one step along the ordered perimeter path."""
        if not ordered_perimeter:
            return
        
        self.index = (self.index + self.direction) % len(ordered_perimeter)
        self.pos = ordered_perimeter[self.index]
        
        if self.cooldown > 0:
            self.cooldown -= 1
    
    def update_visual_position(self):
        """Smoothly interpolate visual position toward actual position."""
        target_x = self.pos[1] * self.tile_size
        target_y = self.pos[0] * self.tile_size
        self.vis_x += (target_x - self.vis_x) * 0.2
        self.vis_y += (target_y - self.vis_y) * 0.2


# ============================================================================
# GAME LOGIC
# ============================================================================

class PerimeterManager:
    """Manages the player's movement perimeter."""
    
    def __init__(self, grid: Grid):
        self.grid = grid
        self.perimeter: Set[Tuple[int, int]] = set()
        self.ordered_perimeter: List[Tuple[int, int]] = []
        self.update()
    
    def update(self):
        """Recompute the perimeter based on current grid state."""
        self.perimeter = self._compute_perimeter()
        self.ordered_perimeter = self._build_ordered_perimeter()
    
    def _compute_perimeter(self) -> Set[Tuple[int, int]]:
        """Find all non-empty tiles adjacent to empty tiles."""
        allowed = set()
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                if self.grid.get(y, x) == TileState.EMPTY:
                    # Check 8-neighbor adjacency
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = y + dy, x + dx
                            if self.grid.in_bounds(ny, nx) and self.grid.get(ny, nx) != TileState.EMPTY:
                                allowed.add((ny, nx))
        return allowed
    
    def _build_ordered_perimeter(self) -> List[Tuple[int, int]]:
        """Build a contiguous ordered list of perimeter tiles."""
        if not self.perimeter:
            return []
        
        perim_set = set(self.perimeter)
        ordered = []
        
        # Start from top-leftmost tile
        current = min(perim_set, key=lambda p: (p[0], p[1]))
        prev = None
        ordered.append(current)
        
        # Walk around the perimeter (clockwise)
        directions = [(-1, 0), (0, 1), (1, 0), (0, -1)]
        
        while True:
            found_next = False
            for dy, dx in directions:
                ny, nx = current[0] + dy, current[1] + dx
                if (ny, nx) in perim_set and (ny, nx) != prev:
                    prev, current = current, (ny, nx)
                    ordered.append(current)
                    found_next = True
                    break
            
            if not found_next or current == ordered[0]:
                break
        
        return ordered


class CollisionDetector:
    """Handles collision detection logic."""
    
    @staticmethod
    def player_crossed_segment(old_pos: Tuple[int, int], new_pos: Tuple[int, int], 
                               player_pos: Tuple[int, int]) -> bool:
        """
        Detect if player passed through a segment between two positions.
        Works for horizontal/vertical moves.
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


class TrailManager:
    """Manages trail creation and area filling."""
    
    def __init__(self, grid: Grid):
        self.grid = grid
    
    def commit_trail(self, trail: List[Tuple[int, int]], qix_pos: Tuple[int, int]) -> int:
        """
        Commit the trail and fill captured areas.
        Returns the number of newly filled tiles.
        """
        if not trail:
            return 0
        
        # Handle single-tile trail
        if len(trail) == 1 and not self._is_single_tile_valid(trail[0]):
            self.grid.set(trail[0][0], trail[0][1], TileState.EMPTY)
            return 0
        
        # Mark trail as filled
        for y, x in trail:
            self.grid.set(y, x, TileState.FILLED)
        
        # Flood fill from Qix to find reachable empty tiles
        qix_reachable = self.grid.flood_fill([qix_pos])
        
        # Count empty areas on each side
        all_empty = set()
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                if self.grid.get(y, x) == TileState.EMPTY:
                    all_empty.add((y, x))
        
        non_qix_empty = all_empty - qix_reachable
        
        # Determine which side to fill (the smaller area)
        if len(non_qix_empty) < len(qix_reachable):
            # Fill the side WITHOUT the Qix (smaller area)
            area_to_fill = non_qix_empty
        else:
            # Fill the side WITH the Qix (smaller area)
            area_to_fill = qix_reachable
        
        # Fill the smaller area
        newly_filled = 0
        for y, x in area_to_fill:
            self.grid.set(y, x, TileState.FILLED)
            newly_filled += 1
        
        return newly_filled
    
    def _is_single_tile_valid(self, pos: Tuple[int, int]) -> bool:
        """Check if a single-tile trail has enough adjacent perimeter tiles."""
        y, x = pos
        adjacent_count = 0
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            ny, nx = y + dy, x + dx
            if self.grid.get(ny, nx) in (TileState.BORDER, TileState.FILLED):
                adjacent_count += 1
        return adjacent_count >= 2


# ============================================================================
# MAIN GAME CLASS
# ============================================================================

class QixGame:
    """Main game controller."""
    
    def __init__(self):
        self.config = config
        self.game_state = GameState.MENU
        self.selected_difficulty = Difficulty.MEDIUM
        self.menu_selection = 0  # 0=Easy, 1=Medium, 2=Hard
        
        # Initialize Pygame
        pygame.init()
        self.screen = pygame.display.set_mode(
            (config.screen_width, config.screen_height + config.scaled_hud_height),
            pygame.RESIZABLE
        )
        pygame.display.set_caption("The Qix Game")
        self.clock = pygame.time.Clock()
        self._update_fonts()
        
        # Load assets
        self._load_assets()
        
        # Game entities (initialized when starting game)
        self.grid = None
        self.perimeter_mgr = None
        self.trail_mgr = None
        self.collision = None
        self.player = None
        self.qix = None
        self.sparx_list = []
        
        self.running = True
    
    def _update_fonts(self):
        """Update font sizes based on window scale."""
        self.font = pygame.font.SysFont("consolas", int(18 * self.config.WINDOW_SCALE), bold=True)
        self.title_font = pygame.font.SysFont("consolas", int(42 * self.config.WINDOW_SCALE), bold=True)
        self.menu_font = pygame.font.SysFont("consolas", int(24 * self.config.WINDOW_SCALE), bold=True)
    
    def _load_assets(self):
        """Load game images."""
        try:
            self.background_img = pygame.image.load("water.png").convert()
            self.land_img = pygame.image.load("grass.png").convert()
            self.rock_img = pygame.image.load("rock.png").convert_alpha()
            self.player_img = pygame.image.load("bird.png").convert_alpha()
            self.qix_img = pygame.image.load("octopus.png").convert_alpha()
            self.sparx_img = pygame.image.load("starfish.png").convert_alpha()
        except pygame.error as e:
            print(f"Warning: Could not load image: {e}")
            # Create placeholder surfaces if images don't exist
            tile_size = config.TILE_SIZE
            self.background_img = pygame.Surface((tile_size, tile_size))
            self.background_img.fill((10, 10, 40))
            self.land_img = pygame.Surface((tile_size, tile_size))
            self.land_img.fill((40, 150, 40))
            self.rock_img = pygame.Surface((tile_size, tile_size))
            self.rock_img.fill((200, 200, 200))
            self.player_img = pygame.Surface((tile_size, tile_size))
            self.player_img.fill((255, 255, 255))
            self.qix_img = pygame.Surface((tile_size, tile_size))
            self.qix_img.fill((200, 50, 50))
            self.sparx_img = pygame.Surface((tile_size, tile_size))
            self.sparx_img.fill((255, 100, 0))
    
    def _scale_image(self, image: pygame.Surface, size: int) -> pygame.Surface:
        """Scale an image to the current window scale."""
        scaled_size = int(size * self.config.WINDOW_SCALE)
        return pygame.transform.scale(image, (scaled_size, scaled_size))
    
    def _initialize_game(self, difficulty: Difficulty):
        """Initialize or reset the game with the selected difficulty."""
        self.grid = Grid(config.GRID_WIDTH, config.GRID_HEIGHT)
        self.perimeter_mgr = PerimeterManager(self.grid)
        self.trail_mgr = TrailManager(self.grid)
        self.collision = CollisionDetector()
        
        # Initialize entities
        start_x = config.GRID_WIDTH // 2
        start_y = config.GRID_HEIGHT - 1
        self.player = Player(start_x, start_y, lives=difficulty.value)
        self.qix = Qix(config.GRID_HEIGHT // 3, config.GRID_WIDTH // 3, config.TILE_SIZE)
        self.sparx_list = []
        
        self._initialize_sparx()
        self.game_state = GameState.PLAYING
    
    def _initialize_sparx(self):
        """Create Sparx enemies on opposite side of player."""
        if not self.perimeter_mgr.ordered_perimeter:
            return
        
        # Find position opposite to player
        target_y = 0 if self.player.y > config.GRID_HEIGHT // 2 else config.GRID_HEIGHT - 1
        target_x = config.GRID_WIDTH - 1 - self.player.x
        
        # Find nearest perimeter tile
        best_idx = min(
            range(len(self.perimeter_mgr.ordered_perimeter)),
            key=lambda i: abs(self.perimeter_mgr.ordered_perimeter[i][0] - target_y) + 
                         abs(self.perimeter_mgr.ordered_perimeter[i][1] - target_x)
        )
        start_pos = self.perimeter_mgr.ordered_perimeter[best_idx]
        
        # Create two Sparx (clockwise and counterclockwise)
        self.sparx_list.append(Sparx(start_pos, 1, best_idx, config.TILE_SIZE))
        self.sparx_list.append(Sparx(start_pos, -1, best_idx, config.TILE_SIZE))
    
    def _remap_sparx_indices(self):
        """Update Sparx positions after perimeter changes."""
        if not self.perimeter_mgr.ordered_perimeter:
            return
        
        for sparx in self.sparx_list:
            sy, sx = sparx.pos
            best_idx = min(
                range(len(self.perimeter_mgr.ordered_perimeter)),
                key=lambda i: abs(self.perimeter_mgr.ordered_perimeter[i][0] - sy) + 
                             abs(self.perimeter_mgr.ordered_perimeter[i][1] - sx)
            )
            sparx.index = best_idx
            sparx.pos = self.perimeter_mgr.ordered_perimeter[best_idx]
    
    def _teleport_player_to_perimeter_if_needed(self):
        """Teleport player to nearest perimeter tile if they're out of bounds."""
        if (self.player.y, self.player.x) in self.perimeter_mgr.perimeter:
            return  # Player is on valid perimeter
        
        # Find nearest perimeter tile using Manhattan distance
        if not self.perimeter_mgr.perimeter:
            return
        
        nearest = min(
            self.perimeter_mgr.perimeter,
            key=lambda pos: abs(pos[0] - self.player.y) + abs(pos[1] - self.player.x)
        )
        
        print(f"Teleporting player from ({self.player.y}, {self.player.x}) to {nearest}")
        self.player.y, self.player.x = nearest
        self.player.vis_x = self.player.x * config.TILE_SIZE
        self.player.vis_y = self.player.y * config.TILE_SIZE
    
    def handle_input(self):
        """Process player input."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                
                # Menu state input
                if self.game_state == GameState.MENU:
                    if event.key == pygame.K_UP:
                        self.menu_selection = (self.menu_selection - 1) % 3
                    elif event.key == pygame.K_DOWN:
                        self.menu_selection = (self.menu_selection + 1) % 3
                    elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        difficulty_map = {0: Difficulty.EASY, 1: Difficulty.MEDIUM, 2: Difficulty.HARD}
                        self.selected_difficulty = difficulty_map[self.menu_selection]
                        self._initialize_game(self.selected_difficulty)
                    # Keep number key shortcuts
                    elif event.key == pygame.K_1:
                        self.menu_selection = 0
                        self.selected_difficulty = Difficulty.EASY
                        self._initialize_game(self.selected_difficulty)
                    elif event.key == pygame.K_2:
                        self.menu_selection = 1
                        self.selected_difficulty = Difficulty.MEDIUM
                        self._initialize_game(self.selected_difficulty)
                    elif event.key == pygame.K_3:
                        self.menu_selection = 2
                        self.selected_difficulty = Difficulty.HARD
                        self._initialize_game(self.selected_difficulty)
                
                # Game over/win state input
                elif self.game_state in (GameState.GAMEOVER, GameState.WIN):
                    if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        self.game_state = GameState.MENU
                        self.menu_selection = 1  # Reset to medium
            
            elif event.type == pygame.VIDEORESIZE:
                # Handle window resize
                self._handle_resize(event.w, event.h)
        
        # Only return movement input if playing
        if self.game_state != GameState.PLAYING:
            return 0, 0, False
        
        keys = pygame.key.get_pressed()
        
        # Movement keys
        key_mapping = {
            pygame.K_LEFT: (-1, 0),
            pygame.K_RIGHT: (1, 0),
            pygame.K_UP: (0, -1),
            pygame.K_DOWN: (0, 1)
        }
        
        # Update last pressed key
        for key, (dx, dy) in key_mapping.items():
            if keys[key]:
                if self.player.last_key is None or self.player.last_key != key:
                    self.player.last_key = key
                break
        
        # Apply movement
        dx, dy = 0, 0
        if self.player.last_key is not None:
            dx, dy = key_mapping[self.player.last_key]
            if not keys[self.player.last_key]:
                self.player.last_key = None
        
        return dx, dy, keys[pygame.K_SPACE]
    
    def _handle_resize(self, width: int, height: int):
        """Handle window resize event."""
        # Calculate new scale based on width (maintaining aspect ratio)
        base_width = config.GRID_WIDTH * config.TILE_SIZE
        base_height = config.GRID_HEIGHT * config.TILE_SIZE + config.HUD_HEIGHT
        
        scale_x = width / base_width
        scale_y = (height - config.HUD_HEIGHT) / base_height
        
        # Use the smaller scale to maintain aspect ratio
        new_scale = min(scale_x, scale_y, 3.0)  # Max scale of 3.0
        new_scale = max(new_scale, 0.5)  # Min scale of 0.5
        
        self.config.WINDOW_SCALE = new_scale
        
        # Update screen
        self.screen = pygame.display.set_mode(
            (self.config.screen_width, self.config.screen_height + self.config.scaled_hud_height),
            pygame.RESIZABLE
        )
        
        # Update fonts
        self._update_fonts()
    
    def update_player(self, dx: int, dy: int, trail_key_pressed: bool):
        """Update player position and trail."""
        # Throttle movement
        self.player.move_timer += 1
        if self.player.move_timer < config.PLAYER_SPEED:
            return
        self.player.move_timer = 0
        
        if dx == 0 and dy == 0:
            return
        
        nx = self.player.x + dx
        ny = self.player.y + dy
        
        # Check valid movement
        can_move = (
            self.grid.in_bounds(ny, nx) and 
            (
                (ny, nx) in self.perimeter_mgr.perimeter or
                (trail_key_pressed and self.grid.get(ny, nx) == TileState.EMPTY) or
                self.grid.get(ny, nx) == TileState.TRAIL
            )
        )
        
        if not can_move:
            return
        
        current_tile = self.grid.get(self.player.y, self.player.x)
        next_tile = self.grid.get(ny, nx)
        
        # Start drawing trail when moving from border/filled to empty
        if not self.player.is_drawing and next_tile == TileState.EMPTY:
            if current_tile in (TileState.BORDER, TileState.FILLED):
                self.player.start_trail(self.player.y, self.player.x)
        
        # Check collision with Qix while drawing
        if self.player.is_drawing and (ny, nx) == (self.qix.y, self.qix.x):
            self._handle_player_death()
            return
        
        # Move player
        self.player.x, self.player.y = nx, ny
        
        # Update trail
        if self.player.is_drawing:
            if self.grid.get(self.player.y, self.player.x) == TileState.TRAIL:
                # Crossed own trail
                print("Crossed own trail!")
                self._handle_player_death()
            elif self.grid.get(self.player.y, self.player.x) == TileState.EMPTY:
                # Add to trail
                self.grid.set(self.player.y, self.player.x, TileState.TRAIL)
                self.player.trail.append((self.player.y, self.player.x))
        
        # Complete trail when returning to border/filled
        if self.player.is_drawing and self.grid.get(self.player.y, self.player.x) in (TileState.BORDER, TileState.FILLED):
            self._complete_trail()
    
    def _handle_player_death(self):
        """Handle player death scenario."""
        self.player.take_damage()
        self.player.reset_trail(self.grid)
        if self.player.trail_start:
            self.player.y, self.player.x = self.player.trail_start
    
    def _complete_trail(self):
        """Complete and commit the current trail."""
        self.trail_mgr.commit_trail(self.player.trail, (self.qix.y, self.qix.x))
        self.perimeter_mgr.update()
        self._remap_sparx_indices()
        self.player.trail.clear()
        self.player.is_drawing = False
        
        # Teleport player to nearest perimeter if out of bounds
        self._teleport_player_to_perimeter_if_needed()
    
    def update_qix(self):
        """Update Qix movement."""
        self.qix.move_timer += 1
        if self.qix.move_timer >= config.QIX_SPEED:
            self.qix.move(self.grid)
            self.qix.move_timer = 0
        
        # Check trail collision
        if (self.qix.y, self.qix.x) in self.player.trail:
            self._handle_player_death()
    
    def update_sparx(self):
        """Update all Sparx movement and collisions."""
        for sparx in self.sparx_list:
            # Initialize move_timer if it doesn't exist
            if not hasattr(sparx, 'move_timer'):
                sparx.move_timer = 0
            
            sparx.move_timer += 1
            if sparx.move_timer >= config.SPARX_SPEED:
                old_pos = sparx.pos
                sparx.move(self.perimeter_mgr.ordered_perimeter)
                sparx.move_timer = 0
                
                # Check collisions (only when not in cooldown)
                if sparx.cooldown == 0:
                    player_pos = (self.player.y, self.player.x)
                    
                    if (player_pos == sparx.pos or 
                        player_pos == old_pos or 
                        self.collision.player_crossed_segment(old_pos, sparx.pos, player_pos)):
                        self.player.take_damage()
                        sparx.direction *= -1
                        sparx.cooldown = config.SPARX_COOLDOWN
                        continue
                
                # Check trail collision
                if self.player.is_drawing and sparx.pos == self.player.trail_start:
                    print("Sparx hit trail!")
                    self._handle_player_death()
    
    def render(self):
        """Render the game state."""
        scale = self.config.WINDOW_SCALE
        tile_size = self.config.scaled_tile_size
        
        # Draw background (scaled to fill entire play area)
        scaled_bg = pygame.transform.scale(self.background_img, 
                                          (self.config.screen_width, self.config.screen_height))
        self.screen.blit(scaled_bg, (0, 0))
        
        # Draw grid tiles - only BORDER and FILLED
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                tile = self.grid.get(y, x)
                if tile in (TileState.BORDER, TileState.FILLED):
                    # Calculate exact pixel position
                    px = x * tile_size
                    py = y * tile_size
                    
                    # Get source texture coordinates (tile within the original texture)
                    tx = (x * config.TILE_SIZE) % self.land_img.get_width()
                    ty = (y * config.TILE_SIZE) % self.land_img.get_height()
                    
                    # Extract the tile from the original texture
                    source_w = min(config.TILE_SIZE, self.land_img.get_width() - tx)
                    source_h = min(config.TILE_SIZE, self.land_img.get_height() - ty)
                    
                    try:
                        texture_portion = self.land_img.subsurface(pygame.Rect(tx, ty, source_w, source_h))
                        # Scale to exact tile size (no +1, exact dimensions)
                        scaled_texture = pygame.transform.scale(texture_portion, (tile_size, tile_size))
                        self.screen.blit(scaled_texture, (px, py))
                    except ValueError:
                        # Fallback if subsurface fails
                        pygame.draw.rect(self.screen, config.COL_FILLED, 
                                       pygame.Rect(px, py, tile_size, tile_size))
        
        # Draw HUD background (full width, scaled height)
        hud_y = self.config.screen_height
        
        # Create HUD texture by scaling a portion of land texture
        try:
            hud_source = self.land_img.subsurface(pygame.Rect(0, 0, 
                                                             min(config.TILE_SIZE * 10, self.land_img.get_width()),
                                                             min(config.TILE_SIZE, self.land_img.get_height())))
            scaled_hud_texture = pygame.transform.scale(hud_source, 
                                                        (self.config.screen_width, self.config.scaled_hud_height))
            self.screen.blit(scaled_hud_texture, (0, hud_y))
        except ValueError:
            # Fallback: solid color HUD
            pygame.draw.rect(self.screen, config.COL_FILLED,
                           pygame.Rect(0, hud_y, self.config.screen_width, self.config.scaled_hud_height))
        
        # Draw trail (excluding last tile)
        for y, x in self.player.trail[:-1]:
            px = x * tile_size
            py = y * tile_size
            pygame.draw.rect(self.screen, config.COL_TRAIL, 
                           pygame.Rect(px, py, tile_size, tile_size))
        
        # Draw perimeter markers
        scaled_rock = self._scale_image(self.rock_img, config.TILE_SIZE)
        for y, x in self.perimeter_mgr.perimeter:
            px = x * tile_size
            py = y * tile_size
            # Center the rock image on the tile
            rock_offset = (tile_size - scaled_rock.get_width()) // 2
            self.screen.blit(scaled_rock, (px + rock_offset, py + rock_offset))
        
        # Draw player
        self.player.update_visual_position(tile_size)
        scaled_player = self._scale_image(self.player_img, config.TILE_SIZE + 6)
        player_offset = (config.TILE_SIZE + 6) * scale / 2
        self.screen.blit(scaled_player, 
                        (self.player.vis_x - player_offset, self.player.vis_y - player_offset))
        
        # Draw Qix
        self.qix.update_visual_position()
        scaled_qix = self._scale_image(self.qix_img, config.TILE_SIZE + 8)
        qix_offset = (config.TILE_SIZE + 8) * scale / 2
        self.screen.blit(scaled_qix, 
                        (self.qix.vis_x * scale - qix_offset, self.qix.vis_y * scale - qix_offset))
        
        # Draw Sparx
        scaled_sparx = self._scale_image(self.sparx_img, config.TILE_SIZE + 6)
        sparx_offset = (config.TILE_SIZE + 6) * scale / 2
        for sparx in self.sparx_list:
            sparx.update_visual_position()
            self.screen.blit(scaled_sparx, 
                           (sparx.vis_x * scale - sparx_offset, sparx.vis_y * scale - sparx_offset))
        
        # Draw HUD text
        fill_pct = int(self.grid.calculate_fill_percentage() * 100)
        hud_text = self.font.render(
            f"Lifeforce: {self.player.lives} Filled: {fill_pct}%", 
            True, 
            config.COL_HUD_TEXT
        )
        self.screen.blit(hud_text, (int(5 * scale), int(hud_y + 2 * scale)))
        
        pygame.display.flip()
    
    def check_game_over(self) -> bool:
        """Check for win/loss conditions."""
        if self.player.lives <= 0:
            print("Game Over - You Lost!")
            self.game_state = GameState.GAMEOVER
            return True
        
        if self.grid.calculate_fill_percentage() >= config.FILL_THRESHOLD:
            print("You Win!")
            self.game_state = GameState.WIN
            return True
        
        return False
    
    def render_menu(self):
        """Render the main menu screen."""
        self.screen.fill((20, 20, 60))
        
        scale = self.config.WINDOW_SCALE
        
        # Title
        title_text = self.title_font.render("THE QIX GAME", True, (255, 255, 100))
        title_rect = title_text.get_rect(center=(self.config.screen_width // 2, int(80 * scale)))
        self.screen.blit(title_text, title_rect)
        
        # Difficulty options
        y_offset = int(160 * scale)
        select_text = self.menu_font.render("SELECT DIFFICULTY:", True, (255, 255, 100))
        select_rect = select_text.get_rect(center=(self.config.screen_width // 2, y_offset))
        self.screen.blit(select_text, select_rect)
        
        difficulties = [
            ("EASY (9 Lives)", 0),
            ("MEDIUM (6 Lives)", 1),
            ("HARD (3 Lives)", 2)
        ]
        
        y_offset += int(45 * scale)
        for text, index in difficulties:
            # Highlight selected option
            if index == self.menu_selection:
                color = (100, 255, 100)
                prefix = "> "
            else:
                color = (200, 200, 200)
                prefix = "  "
            
            option_text = self.menu_font.render(f"{prefix}{text}", True, color)
            option_rect = option_text.get_rect(center=(self.config.screen_width // 2, y_offset))
            self.screen.blit(option_text, option_rect)
            y_offset += int(40 * scale)
        
        # Instructions
        y_offset += int(30 * scale)
        instructions = [
            "HOW TO PLAY:",
            "Arrow keys to navigate / move",
            "ENTER or SPACE to select / draw",
            "Capture 75% area to win!",
            "Avoid Qix and Sparx enemies",
            "",
            "Resize window to scale"
        ]
        
        for line in instructions:
            if line == "HOW TO PLAY:":
                color = (255, 255, 100)
            else:
                color = (180, 180, 180)
            
            text = self.font.render(line, True, color)
            text_rect = text.get_rect(center=(self.config.screen_width // 2, y_offset))
            self.screen.blit(text, text_rect)
            y_offset += int(24 * scale)
        
        pygame.display.flip()
    
    def render_game_over(self):
        """Render the game over screen."""
        self.screen.fill((60, 20, 20))
        
        scale = self.config.WINDOW_SCALE
        
        # Game Over title
        title_text = self.title_font.render("GAME OVER", True, (255, 100, 100))
        title_rect = title_text.get_rect(center=(self.config.screen_width // 2, int(150 * scale)))
        self.screen.blit(title_text, title_rect)
        
        # Stats
        if self.grid:
            fill_pct = int(self.grid.calculate_fill_percentage() * 100)
            stats_text = self.menu_font.render(f"Area Captured: {fill_pct}%", True, (255, 255, 255))
            stats_rect = stats_text.get_rect(center=(self.config.screen_width // 2, int(250 * scale)))
            self.screen.blit(stats_text, stats_rect)
        
        # Continue instruction
        continue_text = self.menu_font.render("Press ENTER to Continue", True, (200, 200, 200))
        continue_rect = continue_text.get_rect(center=(self.config.screen_width // 2, int(350 * scale)))
        self.screen.blit(continue_text, continue_rect)
        
        pygame.display.flip()
    
    def render_win(self):
        """Render the win screen."""
        self.screen.fill((20, 60, 20))
        
        scale = self.config.WINDOW_SCALE
        
        # Win title
        title_text = self.title_font.render("VICTORY!", True, (100, 255, 100))
        title_rect = title_text.get_rect(center=(self.config.screen_width // 2, int(150 * scale)))
        self.screen.blit(title_text, title_rect)
        
        # Stats
        difficulty_names = {Difficulty.EASY: "EASY", Difficulty.MEDIUM: "MEDIUM", Difficulty.HARD: "HARD"}
        diff_text = self.menu_font.render(
            f"Difficulty: {difficulty_names[self.selected_difficulty]}", 
            True, 
            (255, 255, 255)
        )
        diff_rect = diff_text.get_rect(center=(self.config.screen_width // 2, int(230 * scale)))
        self.screen.blit(diff_text, diff_rect)
        
        lives_text = self.menu_font.render(
            f"Lives Remaining: {self.player.lives}", 
            True, 
            (255, 255, 255)
        )
        lives_rect = lives_text.get_rect(center=(self.config.screen_width // 2, int(280 * scale)))
        self.screen.blit(lives_text, lives_rect)
        
        if self.grid:
            fill_pct = int(self.grid.calculate_fill_percentage() * 100)
            stats_text = self.menu_font.render(f"Area Captured: {fill_pct}%", True, (255, 255, 255))
            stats_rect = stats_text.get_rect(center=(self.config.screen_width // 2, int(330 * scale)))
            self.screen.blit(stats_text, stats_rect)
        
        # Continue instruction
        continue_text = self.menu_font.render("Press ENTER to Continue", True, (200, 200, 200))
        continue_rect = continue_text.get_rect(center=(self.config.screen_width // 2, int(410 * scale)))
        self.screen.blit(continue_text, continue_rect)
        
        pygame.display.flip()
    
    def run(self):
        """Main game loop."""
        while self.running:
            self.clock.tick(config.FPS)
            
            # Input
            dx, dy, trail_key = self.handle_input()
            
            # Update and render based on game state
            if self.game_state == GameState.MENU:
                self.render_menu()
            
            elif self.game_state == GameState.PLAYING:
                # Update
                self.update_player(dx, dy, trail_key)
                self.update_qix()
                self.update_sparx()
                
                # Render
                self.render()
                
                # Check game over
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
    config = GameConfig()
    game = QixGame()
    game.run()