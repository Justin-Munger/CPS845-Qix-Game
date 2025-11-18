"""
Optimized Qix-like Game - High performance version
"""

import pygame
import random
from collections import deque
from dataclasses import dataclass
from typing import List, Set, Tuple, Optional
from enum import IntEnum


# ============================================================================
# CONSTANTS
# ============================================================================

class TileState(IntEnum):
    EMPTY = 0
    BORDER = 1
    FILLED = 2
    TRAIL = 3


class GameState(IntEnum):
    MENU = 0
    PLAYING = 1
    GAMEOVER = 2
    WIN = 3


class Difficulty(IntEnum):
    NORMAL = 0
    HARD = 1


@dataclass
class GameConfig:
    TILE_SIZE: int = 8
    GRID_WIDTH: int = 80
    GRID_HEIGHT: int = 60
    FPS: int = 60
    HUD_HEIGHT: int = 20
    WINDOW_SCALE: float = 1.0
    FILL_THRESHOLD: float = 0.75
    PLAYER_SPEED: int = 3
    QIX_SPEED: int = 4
    SPARX_SPEED: int = 5
    SPARX_COOLDOWN: int = 3
    
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
# OPTIMIZED GRID
# ============================================================================

class Grid:
    __slots__ = ['width', 'height', 'tiles', '_fill_cache', '_cache_valid']
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.tiles = [[TileState.EMPTY] * width for _ in range(height)]
        self._fill_cache = 0.0
        self._cache_valid = False
        self._initialize_borders()
    
    def _initialize_borders(self):
        for x in range(self.width):
            self.tiles[0][x] = TileState.BORDER
            self.tiles[self.height - 1][x] = TileState.BORDER
        for y in range(self.height):
            self.tiles[y][0] = TileState.BORDER
            self.tiles[y][self.width - 1] = TileState.BORDER
        self._cache_valid = False
    
    def in_bounds(self, y: int, x: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height
    
    def get(self, y: int, x: int) -> TileState:
        if not self.in_bounds(y, x):
            return TileState.BORDER
        return self.tiles[y][x]
    
    def set(self, y: int, x: int, state: TileState):
        if self.in_bounds(y, x):
            self.tiles[y][x] = state
            self._cache_valid = False
    
    def calculate_fill_percentage(self) -> float:
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
        """Optimized flood fill from single start point."""
        if not self.in_bounds(start_y, start_x):
            return set()
        if self.tiles[start_y][start_x] in (TileState.FILLED, TileState.BORDER):
            return set()
        
        visited = set()
        stack = [(start_y, start_x)]
        visited.add((start_y, start_x))
        
        while stack:
            y, x = stack.pop()
            
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
# ENTITIES
# ============================================================================

class Player:
    __slots__ = ['x', 'y', 'vis_x', 'vis_y', 'lives', 'is_drawing', 'trail', 
                 'trail_start', 'last_key', 'move_timer']
    
    def __init__(self, x: int, y: int, lives: int = 9):
        self.x = x
        self.y = y
        self.vis_x = float(x)
        self.vis_y = float(y)
        self.lives = lives
        self.is_drawing = False
        self.trail = []
        self.trail_start = None
        self.last_key = None
        self.move_timer = 0


class Qix:
    __slots__ = ['y', 'x', 'vel_y', 'vel_x', 'vis_x', 'vis_y', 'move_timer']
    
    def __init__(self, y: int, x: int):
        self.y = y
        self.x = x
        self.vel_y = 1
        self.vel_x = 1
        self.vis_x = float(x)
        self.vis_y = float(y)
        self.move_timer = 0


class Sparx:
    __slots__ = ['pos', 'direction', 'index', 'vis_x', 'vis_y', 'cooldown', 'move_timer', 'last_pos']
    
    def __init__(self, pos: Tuple[int, int], direction: int, index: int):
        self.pos = pos
        self.direction = direction
        self.index = index
        self.vis_x = float(pos[1])
        self.vis_y = float(pos[0])
        self.cooldown = 10
        self.move_timer = 0
        self.last_pos = pos


# ============================================================================
# OPTIMIZED GAME
# ============================================================================

class QixGame:
    def __init__(self):
        self.config = GameConfig()
        self.game_state = GameState.MENU
        self.selected_difficulty = Difficulty.NORMAL
        self.menu_selection = 0
        
        pygame.init()
        # Disable resizable and fullscreen
        self.screen = pygame.display.set_mode(
            (self.config.screen_width, self.config.screen_height + self.config.scaled_hud_height)
        )
        pygame.display.set_caption("The Qix Game")
        self.clock = pygame.time.Clock()
        self._update_fonts()
        self._load_assets()
        
        # Game state
        self.grid = None
        self.player = None
        self.qix_list = []
        self.sparx_list = []
        self.perimeter = set()
        self.ordered_perimeter = []
        
        self.running = True
    
    def _update_fonts(self):
        scale = self.config.WINDOW_SCALE
        self.font = pygame.font.SysFont("consolas", int(18 * scale), bold=True)
        self.title_font = pygame.font.SysFont("consolas", int(42 * scale), bold=True)
        self.menu_font = pygame.font.SysFont("consolas", int(24 * scale), bold=True)
    
    def _load_assets(self):
        try:
            self.background_img = pygame.image.load("water.png").convert()
            self.land_img = pygame.image.load("grass.png").convert()
            self.rock_img = pygame.image.load("rock.png").convert_alpha()
            self.player_img = pygame.image.load("bird.png").convert_alpha()
            self.qix_img = pygame.image.load("octopus.png").convert_alpha()
            self.sparx_img = pygame.image.load("starfish.png").convert_alpha()
        except:
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
        self.grid = Grid(self.config.GRID_WIDTH, self.config.GRID_HEIGHT)
        
        start_x = self.config.GRID_WIDTH // 2
        start_y = self.config.GRID_HEIGHT - 1
        self.player = Player(start_x, start_y, lives=9)
        
        # Initialize Qix
        self.qix_list = []
        if difficulty == Difficulty.NORMAL:
            self.qix_list.append(Qix(self.config.GRID_HEIGHT // 3, self.config.GRID_WIDTH // 3))
        else:
            self.qix_list.append(Qix(self.config.GRID_HEIGHT // 3, self.config.GRID_WIDTH // 3))
            self.qix_list.append(Qix(self.config.GRID_HEIGHT * 2 // 3, self.config.GRID_WIDTH * 2 // 3))
        
        # Compute perimeter (used by both player and Sparx)
        self._compute_perimeter()
        
        # Initialize Sparx (no longer needs ordered_perimeter)
        self.sparx_list = []
        self._initialize_sparx(difficulty)
        
        self.game_state = GameState.PLAYING
    
    def _compute_perimeter(self):
        """Fast perimeter computation."""
        self.perimeter = set()
        
        # First pass: find all tiles adjacent to empty space
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                if self.grid.tiles[y][x] == TileState.EMPTY:
                    # Check 8-neighbors for non-empty tiles
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            if dy == 0 and dx == 0:
                                continue
                            ny, nx = y + dy, x + dx
                            if self.grid.in_bounds(ny, nx) and self.grid.tiles[ny][nx] != TileState.EMPTY:
                                self.perimeter.add((ny, nx))
        
        # Build ordered perimeter
        if self.perimeter:
            self.ordered_perimeter = self._build_ordered_perimeter()
        else:
            self.ordered_perimeter = []
    
    def _build_ordered_perimeter(self) -> List[Tuple[int, int]]:
        """Build a smooth contiguous path that visits every perimeter tile exactly once."""
        if not self.perimeter:
            return []
        
        # Start from top-left corner
        start = min(self.perimeter, key=lambda p: (p[0], p[1]))
        
        # Use depth-first search to build a complete path
        ordered = []
        visited = set()
        
        def dfs_build_path(pos):
            """Recursively build path visiting all adjacent tiles."""
            if pos in visited:
                return
            
            visited.add(pos)
            ordered.append(pos)
            
            # Get all adjacent perimeter tiles (4-directional first, then diagonals)
            neighbors = []
            
            # Priority order: right, down, left, up (clockwise from right)
            for dy, dx in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                ny, nx = pos[0] + dy, pos[1] + dx
                if (ny, nx) in self.perimeter and (ny, nx) not in visited:
                    neighbors.append(((ny, nx), 0))  # 4-directional has priority 0
            
            # Add diagonal neighbors with lower priority
            for dy, dx in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
                ny, nx = pos[0] + dy, pos[1] + dx
                if (ny, nx) in self.perimeter and (ny, nx) not in visited:
                    neighbors.append(((ny, nx), 1))  # diagonals have priority 1
            
            # Sort by priority (4-directional first)
            neighbors.sort(key=lambda x: x[1])
            
            # Visit all neighbors
            for neighbor, _ in neighbors:
                dfs_build_path(neighbor)
        
        # Start DFS from starting position
        dfs_build_path(start)
        
        # Handle any disconnected tiles
        unvisited = self.perimeter - visited
        while unvisited:
            # Find closest unvisited to last visited
            if ordered:
                next_start = min(unvisited, 
                               key=lambda p: abs(p[0] - ordered[-1][0]) + abs(p[1] - ordered[-1][1]))
            else:
                next_start = min(unvisited, key=lambda p: (p[0], p[1]))
            
            print(f"Connecting disconnected segment starting at {next_start}")
            dfs_build_path(next_start)
            unvisited = self.perimeter - visited
        
        print(f"Built perimeter: {len(ordered)} tiles (expected {len(self.perimeter)})")
        return ordered
    
    def _is_valid_perimeter_move(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
        """Check if moving between two perimeter tiles is valid (no gap jumping)."""
        fy, fx = from_pos
        ty, tx = to_pos
        
        # Calculate distance
        dy = abs(ty - fy)
        dx = abs(tx - fx)
        
        # Direct neighbors (4-directional) are always valid
        if dy + dx == 1:
            return True
        
        # Diagonal moves (distance = 2 in Manhattan)
        if dy == 1 and dx == 1:
            # Check if the two intermediate tiles provide a valid path
            # For diagonal A to B, check if path A->C->B or A->D->B exists
            adj1 = (fy, tx)  # same row as from, same col as to
            adj2 = (ty, fx)  # same row as to, same col as from
            
            adj1_is_perimeter = adj1 in self.perimeter
            adj2_is_perimeter = adj2 in self.perimeter
            
            # At least one path should exist through perimeter tiles
            return adj1_is_perimeter or adj2_is_perimeter
        
        # Larger jumps are not valid
        return False
    
    def _initialize_sparx(self, difficulty: Difficulty):
        """Initialize Sparx using perimeter positions (same as player)."""
        if not self.perimeter:
            return
        
        # Find position opposite to player
        target_y = 0 if self.player.y > self.config.GRID_HEIGHT // 2 else self.config.GRID_HEIGHT - 1
        target_x = self.config.GRID_WIDTH - 1 - self.player.x
        
        # Find nearest perimeter tile to target
        start_pos = min(self.perimeter, 
                       key=lambda p: abs(p[0] - target_y) + abs(p[1] - target_x))
        
        # Create Sparx with direction indicators (not index-based)
        self.sparx_list.append(Sparx(start_pos, 1, 0))  # Clockwise
        self.sparx_list.append(Sparx(start_pos, -1, 0))  # Counter-clockwise
        
        if difficulty == Difficulty.HARD:
            # Third sparx at opposite side
            opposite_y = self.config.GRID_HEIGHT - 1 - target_y
            opposite_x = self.config.GRID_WIDTH - 1 - target_x
            third_pos = min(self.perimeter,
                           key=lambda p: abs(p[0] - opposite_y) + abs(p[1] - opposite_x))
            self.sparx_list.append(Sparx(third_pos, 1, 0))
    
    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                
                if self.game_state == GameState.MENU:
                    if event.key == pygame.K_UP:
                        self.menu_selection = (self.menu_selection - 1) % 2
                    elif event.key == pygame.K_DOWN:
                        self.menu_selection = (self.menu_selection + 1) % 2
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_1, pygame.K_2):
                        if event.key == pygame.K_1:
                            self.menu_selection = 0
                        elif event.key == pygame.K_2:
                            self.menu_selection = 1
                        
                        difficulty = Difficulty.NORMAL if self.menu_selection == 0 else Difficulty.HARD
                        self.selected_difficulty = difficulty
                        self._initialize_game(difficulty)
                
                elif self.game_state in (GameState.GAMEOVER, GameState.WIN):
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.game_state = GameState.MENU
                        self.menu_selection = 0
        
        if self.game_state != GameState.PLAYING:
            return 0, 0, False
        
        keys = pygame.key.get_pressed()
        key_mapping = {
            pygame.K_LEFT: (-1, 0),
            pygame.K_RIGHT: (1, 0),
            pygame.K_UP: (0, -1),
            pygame.K_DOWN: (0, 1)
        }
        
        for key, (dx, dy) in key_mapping.items():
            if keys[key]:
                if self.player.last_key is None or self.player.last_key != key:
                    self.player.last_key = key
                break
        
        dx, dy = 0, 0
        if self.player.last_key is not None:
            dx, dy = key_mapping[self.player.last_key]
            if not keys[self.player.last_key]:
                self.player.last_key = None
        
        return dx, dy, keys[pygame.K_SPACE]
    
    def update_player(self, dx: int, dy: int, trail_key: bool):
        self.player.move_timer += 1
        if self.player.move_timer < self.config.PLAYER_SPEED:
            return
        self.player.move_timer = 0
        
        if dx == 0 and dy == 0:
            return
        
        nx = self.player.x + dx
        ny = self.player.y + dy
        
        if not self.grid.in_bounds(ny, nx):
            return
        
        current_tile = self.grid.tiles[self.player.y][self.player.x]
        next_tile = self.grid.tiles[ny][nx]
        
        # CRITICAL FIX: Prevent moving between two border/filled tiles (crossing through gaps)
        # Check if current tile is border/filled AND next tile is border/filled
        if current_tile in (TileState.BORDER, TileState.FILLED) and next_tile in (TileState.BORDER, TileState.FILLED):
            # Check if there's an empty tile adjacent to the path - if not, this is a gap crossing
            # Look perpendicular to movement direction
            if dx != 0:  # Horizontal movement
                # Check tiles above and below the path
                check_y1 = self.player.y - 1
                check_y2 = self.player.y + 1
                has_empty_adjacent = (
                    (self.grid.in_bounds(check_y1, self.player.x) and self.grid.tiles[check_y1][self.player.x] == TileState.EMPTY) or
                    (self.grid.in_bounds(check_y2, self.player.x) and self.grid.tiles[check_y2][self.player.x] == TileState.EMPTY) or
                    (self.grid.in_bounds(check_y1, nx) and self.grid.tiles[check_y1][nx] == TileState.EMPTY) or
                    (self.grid.in_bounds(check_y2, nx) and self.grid.tiles[check_y2][nx] == TileState.EMPTY)
                )
            else:  # Vertical movement (dy != 0)
                # Check tiles left and right of the path
                check_x1 = self.player.x - 1
                check_x2 = self.player.x + 1
                has_empty_adjacent = (
                    (self.grid.in_bounds(self.player.y, check_x1) and self.grid.tiles[self.player.y][check_x1] == TileState.EMPTY) or
                    (self.grid.in_bounds(self.player.y, check_x2) and self.grid.tiles[self.player.y][check_x2] == TileState.EMPTY) or
                    (self.grid.in_bounds(ny, check_x1) and self.grid.tiles[ny][check_x1] == TileState.EMPTY) or
                    (self.grid.in_bounds(ny, check_x2) and self.grid.tiles[ny][check_x2] == TileState.EMPTY)
                )
            
            # If no empty tiles adjacent, this is crossing through a gap - block it
            if not has_empty_adjacent:
                return
        
        # Normal movement validation
        can_move = (
            (ny, nx) in self.perimeter or
            (trail_key and next_tile == TileState.EMPTY) or
            next_tile == TileState.TRAIL
        )
        
        if not can_move:
            return
        
        # Start trail
        if not self.player.is_drawing and next_tile == TileState.EMPTY:
            if current_tile in (TileState.BORDER, TileState.FILLED):
                self.player.trail_start = (self.player.y, self.player.x)
                self.player.is_drawing = True
                self.player.trail = []
        
        # Check Qix collision while drawing
        if self.player.is_drawing:
            for qix in self.qix_list:
                if (ny, nx) == (qix.y, qix.x):
                    self._handle_player_death()
                    return
        
        # Move player
        self.player.x, self.player.y = nx, ny
        
        # Handle trail
        if self.player.is_drawing:
            if self.grid.tiles[self.player.y][self.player.x] == TileState.TRAIL:
                # Crossed own trail
                self._handle_player_death()
                return
            elif self.grid.tiles[self.player.y][self.player.x] == TileState.EMPTY:
                self.grid.set(self.player.y, self.player.x, TileState.TRAIL)
                self.player.trail.append((self.player.y, self.player.x))
        
        # Complete trail
        if self.player.is_drawing and self.grid.tiles[self.player.y][self.player.x] in (TileState.BORDER, TileState.FILLED):
            self._complete_trail()
    
    def _handle_player_death(self):
        self.player.lives -= 1
        self._reset_trail()
        if self.player.trail_start:
            self.player.y, self.player.x = self.player.trail_start
    
    def _reset_trail(self):
        for y, x in self.player.trail:
            if self.grid.tiles[y][x] == TileState.TRAIL:
                self.grid.set(y, x, TileState.EMPTY)
        self.player.trail.clear()
        self.player.is_drawing = False
    
    def _complete_trail(self):
        """Optimized trail completion with crash prevention."""
        try:
            if not self.player.trail:
                self.player.is_drawing = False
                return
            
            # Mark trail as filled
            for y, x in self.player.trail:
                self.grid.set(y, x, TileState.FILLED)
            
            # Find all empty regions after trail is marked
            all_empty = []
            for y in range(self.grid.height):
                for x in range(self.grid.width):
                    if self.grid.tiles[y][x] == TileState.EMPTY:
                        all_empty.append((y, x))
            
            # If there are empty tiles, find and fill smallest region
            if all_empty:
                # Find all separate regions
                regions = []
                remaining = set(all_empty)
                
                while remaining:
                    start_y, start_x = remaining.pop()
                    region = self.grid.flood_fill_fast(start_y, start_x)
                    if region:
                        regions.append(region)
                        remaining -= region
                
                # Only fill if we found regions AND there's more than one region OR the region doesn't contain all empty space
                if regions and len(regions) > 1:
                    # Multiple regions - fill the smallest one
                    smallest = min(regions, key=len)
                    print(f"Filling smallest region: {len(smallest)} tiles out of {len(all_empty)} total")
                    for y, x in smallest:
                        self.grid.set(y, x, TileState.FILLED)
                elif regions and len(regions) == 1:
                    # Only one region exists
                    # Check if any Qix are in this region
                    region = regions[0]
                    qix_in_region = any((qix.y, qix.x) in region for qix in self.qix_list)
                    
                    if not qix_in_region:
                        # No Qix in the only region - this means trail enclosed no space
                        # Just keep the trail as border, don't fill anything
                        print("Trail has no interior space - keeping as border only")
                    else:
                        # Qix are in the only region - this is the main play area
                        # Don't fill it
                        print("Trail created but main play area remains")
                else:
                    print("No valid regions to fill")
            else:
                print("No empty tiles remain")
            
            # Clear trail
            self.player.trail.clear()
            self.player.is_drawing = False
            
            # Update perimeter
            self._compute_perimeter()
            self._remap_sparx()
            
            # Relocate trapped Qix
            self._relocate_qix()
            
        except Exception as e:
            print(f"Trail completion error: {e}")
            self._reset_trail()
    
    def _relocate_qix(self):
        """Simple, crash-proof Qix relocation."""
        for qix in self.qix_list:
            if self.grid.tiles[qix.y][qix.x] != TileState.EMPTY:
                # Find nearest empty tile
                empty_tiles = [(y, x) for y in range(self.grid.height) for x in range(self.grid.width)
                              if self.grid.tiles[y][x] == TileState.EMPTY]
                
                if empty_tiles:
                    nearest = min(empty_tiles, key=lambda p: abs(p[0] - qix.y) + abs(p[1] - qix.x))
                    qix.y, qix.x = nearest
                    qix.vis_x = float(qix.x)
                    qix.vis_y = float(qix.y)
                    qix.vel_x = 1 if random.random() > 0.5 else -1
                    qix.vel_y = 1 if random.random() > 0.5 else -1
    
    def _remap_sparx(self):
        """Remap Sparx to nearest perimeter position (same system as player)."""
        if not self.perimeter:
            return
        
        for sparx in self.sparx_list:
            old_pos = sparx.pos
            
            # If current position is still in perimeter, keep it
            if old_pos in self.perimeter:
                print(f"Sparx position {old_pos} still valid")
                continue
            
            # Find nearest perimeter tile
            nearest = min(self.perimeter, 
                         key=lambda p: abs(p[0] - old_pos[0]) + abs(p[1] - old_pos[1]))
            
            sparx.pos = nearest
            # Don't reset visual position - let it interpolate smoothly
            
            print(f"Remapped Sparx from {old_pos} to {nearest}")
    
    def update_qix(self):
        for qix in self.qix_list:
            qix.move_timer += 1
            if qix.move_timer < self.config.QIX_SPEED:
                continue
            qix.move_timer = 0
            
            if random.random() < 0.02:
                if random.random() < 0.5:
                    qix.vel_y *= -1
                if random.random() < 0.5:
                    qix.vel_x *= -1
            
            ny = qix.y + qix.vel_y
            nx = qix.x + qix.vel_x
            
            if not self.grid.in_bounds(ny, nx) or self.grid.tiles[ny][nx] in (TileState.FILLED, TileState.BORDER):
                if not self.grid.in_bounds(ny, nx) or self.grid.tiles[ny][nx] == TileState.BORDER:
                    qix.vel_y *= -1
                    qix.vel_x *= -1
                else:
                    if not self.grid.in_bounds(ny, qix.x) or self.grid.tiles[ny][qix.x] in (TileState.FILLED, TileState.BORDER):
                        qix.vel_y *= -1
                    if not self.grid.in_bounds(qix.y, nx) or self.grid.tiles[qix.y][nx] in (TileState.FILLED, TileState.BORDER):
                        qix.vel_x *= -1
                
                ny = qix.y + qix.vel_y
                nx = qix.x + qix.vel_x
            
            if self.grid.in_bounds(ny, nx) and self.grid.tiles[ny][nx] in (TileState.EMPTY, TileState.TRAIL):
                qix.y, qix.x = ny, nx
            
            if (qix.y, qix.x) in self.player.trail:
                self._handle_player_death()
    
    def update_sparx(self):
        """Update Sparx using the same perimeter movement logic as the player."""
        for sparx in self.sparx_list:
            sparx.move_timer += 1
            if sparx.move_timer < self.config.SPARX_SPEED:
                continue
            sparx.move_timer = 0
            
            if not self.perimeter:
                continue
            
            if sparx.cooldown > 0:
                sparx.cooldown -= 1
            
            old_pos = sparx.pos
            
            # Find all valid adjacent perimeter tiles
            valid_moves = []
            
            for dy, dx in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                ny, nx = old_pos[0] + dy, old_pos[1] + dx
                new_pos = (ny, nx)
                
                if new_pos not in self.perimeter:
                    continue
                
                # Check gap crossing (same as player)
                current_tile = self.grid.tiles[old_pos[0]][old_pos[1]]
                next_tile = self.grid.tiles[ny][nx]
                
                can_move = True
                if current_tile in (TileState.BORDER, TileState.FILLED) and next_tile in (TileState.BORDER, TileState.FILLED):
                    if dx != 0:  # Horizontal
                        check_y1 = old_pos[0] - 1
                        check_y2 = old_pos[0] + 1
                        has_empty = (
                            (self.grid.in_bounds(check_y1, old_pos[1]) and self.grid.tiles[check_y1][old_pos[1]] == TileState.EMPTY) or
                            (self.grid.in_bounds(check_y2, old_pos[1]) and self.grid.tiles[check_y2][old_pos[1]] == TileState.EMPTY) or
                            (self.grid.in_bounds(check_y1, nx) and self.grid.tiles[check_y1][nx] == TileState.EMPTY) or
                            (self.grid.in_bounds(check_y2, nx) and self.grid.tiles[check_y2][nx] == TileState.EMPTY)
                        )
                        can_move = has_empty
                    else:  # Vertical
                        check_x1 = old_pos[1] - 1
                        check_x2 = old_pos[1] + 1
                        has_empty = (
                            (self.grid.in_bounds(old_pos[0], check_x1) and self.grid.tiles[old_pos[0]][check_x1] == TileState.EMPTY) or
                            (self.grid.in_bounds(old_pos[0], check_x2) and self.grid.tiles[old_pos[0]][check_x2] == TileState.EMPTY) or
                            (self.grid.in_bounds(ny, check_x1) and self.grid.tiles[ny][check_x1] == TileState.EMPTY) or
                            (self.grid.in_bounds(ny, check_x2) and self.grid.tiles[ny][check_x2] == TileState.EMPTY)
                        )
                        can_move = has_empty
                
                if can_move:
                    valid_moves.append((new_pos, dy, dx))
            
            # Choose best move based on direction preference and avoiding backtracking
            if valid_moves:
                # Calculate where we came from (reverse of last move)
                last_dy = old_pos[0] - getattr(sparx, 'last_pos', old_pos)[0]
                last_dx = old_pos[1] - getattr(sparx, 'last_pos', old_pos)[1]
                
                # Score each move
                best_move = None
                best_score = -999
                
                for new_pos, dy, dx in valid_moves:
                    score = 0
                    
                    # Heavily penalize going backwards (opposite of last move)
                    if dy == -last_dy and dx == -last_dx:
                        score -= 100
                    
                    # Prefer continuing in same direction
                    if dy == last_dy and dx == last_dx:
                        score += 50
                    
                    # Apply directional preference based on clockwise/counter-clockwise
                    if sparx.direction == 1:  # Clockwise: prefer right, down, left, up
                        if dx == 1: score += 40  # right
                        elif dy == 1: score += 30  # down
                        elif dx == -1: score += 20  # left
                        elif dy == -1: score += 10  # up
                    else:  # Counter-clockwise: prefer left, up, right, down
                        if dx == -1: score += 40  # left
                        elif dy == -1: score += 30  # up
                        elif dx == 1: score += 20  # right
                        elif dy == 1: score += 10  # down
                    
                    if score > best_score:
                        best_score = score
                        best_move = new_pos
                
                if best_move:
                    sparx.last_pos = old_pos  # Remember where we came from
                    sparx.pos = best_move
            else:
                # No valid 4-directional moves, try diagonals
                for dy, dx in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
                    ny, nx = old_pos[0] + dy, old_pos[1] + dx
                    if (ny, nx) in self.perimeter:
                        sparx.last_pos = old_pos
                        sparx.pos = (ny, nx)
                        break
            
            # Check player collision (only when not in cooldown)
            if sparx.cooldown == 0:
                player_pos = (self.player.y, self.player.x)
                
                if player_pos == sparx.pos or player_pos == old_pos:
                    self.player.lives -= 1
                    print(f"Sparx hit player! Lives: {self.player.lives}")
                    sparx.direction *= -1
                    sparx.cooldown = self.config.SPARX_COOLDOWN
                    continue
                
                if self._player_crossed_segment(old_pos, sparx.pos, player_pos):
                    self.player.lives -= 1
                    print(f"Sparx crossed player! Lives: {self.player.lives}")
                    sparx.direction *= -1
                    sparx.cooldown = self.config.SPARX_COOLDOWN
                    continue
            
            # Check trail collision
            if self.player.is_drawing and sparx.pos == self.player.trail_start:
                print("Sparx hit trail start!")
                self._handle_player_death()
                return
    
    def _player_crossed_segment(self, old_pos: Tuple[int, int], new_pos: Tuple[int, int], 
                                player_pos: Tuple[int, int]) -> bool:
        """Check if player crossed between old and new Sparx positions."""
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
        if self.player.lives < 1:
            self.game_state = GameState.GAMEOVER
            return True
        
        if self.grid.calculate_fill_percentage() >= self.config.FILL_THRESHOLD:
            self.game_state = GameState.WIN
            return True
        
        return False
    
    def render(self):
        scale = self.config.WINDOW_SCALE
        tile_size = self.config.scaled_tile_size
        
        # Background
        scaled_bg = pygame.transform.scale(self.background_img, 
                                          (self.config.screen_width, self.config.screen_height))
        self.screen.blit(scaled_bg, (0, 0))
        
        # Grid tiles (optimized)
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                if self.grid.tiles[y][x] in (TileState.BORDER, TileState.FILLED):
                    px = x * tile_size
                    py = y * tile_size
                    tx = (x * self.config.TILE_SIZE) % self.land_img.get_width()
                    ty = (y * self.config.TILE_SIZE) % self.land_img.get_height()
                    
                    source_w = min(self.config.TILE_SIZE, self.land_img.get_width() - tx)
                    source_h = min(self.config.TILE_SIZE, self.land_img.get_height() - ty)
                    
                    texture = self.land_img.subsurface(pygame.Rect(tx, ty, source_w, source_h))
                    scaled = pygame.transform.scale(texture, (tile_size, tile_size))
                    self.screen.blit(scaled, (px, py))
        
        # HUD background (tiled)
        hud_y = self.config.screen_height
        tiles_x = (self.config.screen_width // tile_size) + 1
        tiles_y = (self.config.scaled_hud_height // tile_size) + 1
        
        for ty in range(tiles_y):
            for tx in range(tiles_x):
                tex_x = (tx * self.config.TILE_SIZE) % self.land_img.get_width()
                tex_y = (ty * self.config.TILE_SIZE) % self.land_img.get_height()
                
                source_w = min(self.config.TILE_SIZE, self.land_img.get_width() - tex_x)
                source_h = min(self.config.TILE_SIZE, self.land_img.get_height() - tex_y)
                
                texture = self.land_img.subsurface(pygame.Rect(tex_x, tex_y, source_w, source_h))
                scaled_tile = pygame.transform.scale(texture, (tile_size, tile_size))
                self.screen.blit(scaled_tile, (tx * tile_size, hud_y + ty * tile_size))
        
        # Trail
        for y, x in self.player.trail:
            pygame.draw.rect(self.screen, (255, 200, 0), 
                           pygame.Rect(x * tile_size, y * tile_size, tile_size, tile_size))
        
        # Perimeter
        scaled_rock = pygame.transform.scale(self.rock_img, (tile_size, tile_size))
        for y, x in self.perimeter:
            px = x * tile_size + (tile_size - scaled_rock.get_width()) // 2
            py = y * tile_size + (tile_size - scaled_rock.get_height()) // 2
            self.screen.blit(scaled_rock, (px, py))
        
        # Player
        self.player.vis_x += (self.player.x - self.player.vis_x) * 0.4
        self.player.vis_y += (self.player.y - self.player.vis_y) * 0.4
        scaled_player = pygame.transform.scale(self.player_img, (tile_size + 6, tile_size + 6))
        px = self.player.vis_x * tile_size + tile_size // 2 - scaled_player.get_width() // 2
        py = self.player.vis_y * tile_size + tile_size // 2 - scaled_player.get_height() // 2
        self.screen.blit(scaled_player, (int(px), int(py)))
        
        # Qix
        scaled_qix = pygame.transform.scale(self.qix_img, (tile_size + 8, tile_size + 8))
        for qix in self.qix_list:
            qix.vis_x += (qix.x - qix.vis_x) * 0.3
            qix.vis_y += (qix.y - qix.vis_y) * 0.3
            qx = qix.vis_x * tile_size + tile_size // 2 - scaled_qix.get_width() // 2
            qy = qix.vis_y * tile_size + tile_size // 2 - scaled_qix.get_height() // 2
            self.screen.blit(scaled_qix, (int(qx), int(qy)))
        
        # Sparx
        scaled_sparx = pygame.transform.scale(self.sparx_img, (tile_size + 6, tile_size + 6))
        for sparx in self.sparx_list:
            sparx.vis_x += (sparx.pos[1] - sparx.vis_x) * 0.2
            sparx.vis_y += (sparx.pos[0] - sparx.vis_y) * 0.2
            sx = sparx.vis_x * tile_size + tile_size // 2 - scaled_sparx.get_width() // 2
            sy = sparx.vis_y * tile_size + tile_size // 2 - scaled_sparx.get_height() // 2
            self.screen.blit(scaled_sparx, (int(sx), int(sy)))
        
        # HUD text
        fill_pct = int(self.grid.calculate_fill_percentage() * 100)
        hud_text = self.font.render(f"Lifeforce: {self.player.lives} Filled: {fill_pct}%", True, (0, 0, 0))
        self.screen.blit(hud_text, (int(5 * scale), int(hud_y + 2 * scale)))
        
        pygame.display.flip()
    
    def render_menu(self):
        self.screen.fill((20, 20, 60))
        scale = self.config.WINDOW_SCALE
        center_x = self.config.screen_width // 2
        center_y = self.config.screen_height // 2
        
        title = self.title_font.render("THE QIX GAME", True, (255, 255, 100))
        self.screen.blit(title, title.get_rect(center=(center_x, center_y - int(180 * scale))))
        
        y_offset = center_y - int(100 * scale)
        select = self.menu_font.render("SELECT DIFFICULTY:", True, (255, 255, 100))
        self.screen.blit(select, select.get_rect(center=(center_x, y_offset)))
        
        difficulties = [("NORMAL (2 Sparx, 1 Qix)", 0), ("HARD (3 Sparx, 2 Qix)", 1)]
        y_offset += int(45 * scale)
        
        for text, index in difficulties:
            color = (100, 255, 100) if index == self.menu_selection else (200, 200, 200)
            prefix = "> " if index == self.menu_selection else "  "
            option = self.menu_font.render(f"{prefix}{text}", True, color)
            self.screen.blit(option, option.get_rect(center=(center_x, y_offset)))
            y_offset += int(40 * scale)
        
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
        self.screen.fill((60, 20, 20))
        scale = self.config.WINDOW_SCALE
        center_x = self.config.screen_width // 2
        
        title = self.title_font.render("GAME OVER", True, (255, 100, 100))
        self.screen.blit(title, title.get_rect(center=(center_x, int(150 * scale))))
        
        fill_pct = int(self.grid.calculate_fill_percentage() * 100)
        stats = self.menu_font.render(f"Area Captured: {fill_pct}%", True, (255, 255, 255))
        self.screen.blit(stats, stats.get_rect(center=(center_x, int(250 * scale))))
        
        cont = self.menu_font.render("Press ENTER to Continue", True, (200, 200, 200))
        self.screen.blit(cont, cont.get_rect(center=(center_x, int(350 * scale))))
        
        pygame.display.flip()
    
    def render_win(self):
        self.screen.fill((20, 60, 20))
        scale = self.config.WINDOW_SCALE
        center_x = self.config.screen_width // 2
        
        title = self.title_font.render("VICTORY!", True, (100, 255, 100))
        self.screen.blit(title, title.get_rect(center=(center_x, int(150 * scale))))
        
        diff_names = {Difficulty.NORMAL: "NORMAL", Difficulty.HARD: "HARD"}
        diff = self.menu_font.render(f"Difficulty: {diff_names[self.selected_difficulty]}", True, (255, 255, 255))
        self.screen.blit(diff, diff.get_rect(center=(center_x, int(230 * scale))))
        
        lives = self.menu_font.render(f"Lives Remaining: {self.player.lives}", True, (255, 255, 255))
        self.screen.blit(lives, lives.get_rect(center=(center_x, int(280 * scale))))
        
        fill_pct = int(self.grid.calculate_fill_percentage() * 100)
        stats = self.menu_font.render(f"Area Captured: {fill_pct}%", True, (255, 255, 255))
        self.screen.blit(stats, stats.get_rect(center=(center_x, int(330 * scale))))
        
        cont = self.menu_font.render("Press ENTER to Continue", True, (200, 200, 200))
        self.screen.blit(cont, cont.get_rect(center=(center_x, int(410 * scale))))
        
        pygame.display.flip()
    
    def run(self):
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