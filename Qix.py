# qix_like.py
import pygame
import random
from collections import deque

# === Config ===
TILE_SIZE = 8
GRID_W = 80   # number of tiles across
GRID_H = 60   # number of tiles down
SCREEN_W = GRID_W * TILE_SIZE
SCREEN_H = GRID_H * TILE_SIZE

FPS = 60
FILL_THRESHOLD = 0.75  # win at 75% filled

# Tile states
EMPTY = 0       # empty playfield
BORDER = 1      # perimeter border
FILLED = 2      # claimed area
TRAIL = 3       # current trail being drawn

# Colors
COL_EMPTY = (10, 10, 40)
COL_BORDER = (40, 150, 40)
COL_FILLED = (40, 150, 40)
COL_TRAIL = (255, 200, 0)
COL_PLAYER = (255, 255, 255)
COL_QIX = (200, 50, 50)
COL_PERIMETER = (200, 200, 200)

# Player movement speed (tiles per move)
PLAYER_SPEED = 1
last_key = None  # "x" or "y" or None
trail_start_pos = (GRID_W//2, GRID_H-1)  # (y, x) where the trail began



# === Game setup ===
pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("The Qix Game")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 24)

background_img = pygame.image.load("water_background.png").convert()
land_img = pygame.image.load("land_texture.png").convert()


# create grid and set borders
grid = [[EMPTY for _ in range(GRID_W)] for _ in range(GRID_H)]
for x in range(GRID_W):
    grid[0][x] = BORDER
    grid[GRID_H-1][x] = BORDER
for y in range(GRID_H):
    grid[y][0] = BORDER
    grid[y][GRID_W-1] = BORDER

# helper functions
def in_bounds(y, x):
    return 0 <= x < GRID_W and 0 <= y < GRID_H

def draw_grid():
    for y in range(GRID_H):
        for x in range(GRID_W):
            rect = pygame.Rect(x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE)
            val = grid[y][x]
            if val == EMPTY:
                #color = COL_EMPTY
                continue  # skip drawing empty to show background
            elif val == BORDER:
                color = COL_BORDER
            elif val == FILLED:
                color = COL_FILLED
            elif val == TRAIL:
                color = COL_TRAIL
            pygame.draw.rect(screen, color, rect)

def grid_fill_from_points(starts):
    """Return set of tiles reachable from any start tile via 4-neighbor moves across tiles that are not FILLED or BORDER."""
    visited = set()
    q = deque()
    for (sy, sx) in starts:
        if not in_bounds(sy, sx): continue
        if (sy, sx) in visited: continue
        if grid[sy][sx] == FILLED or grid[sy][sx] == BORDER:
            continue
        visited.add((sy, sx))
        q.append((sy, sx))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
            ny, nx = y+dy, x+dx
            if not in_bounds(ny, nx): continue
            if (ny, nx) in visited: continue
            if grid[ny][nx] == FILLED or grid[ny][nx] == BORDER:
                continue
            visited.add((ny, nx))
            q.append((ny, nx))
    return visited

def percent_filled():
    total = 0
    filled = 0
    for row in grid:
        for val in row:
            if val != BORDER:
                total += 1
                if val == FILLED:
                    filled += 1
    return filled / total if total>0 else 0

def compute_player_perimeter():
    allowed = set()
    for y in range(GRID_H):
        for x in range(GRID_W):
            if grid[y][x] == EMPTY:
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if in_bounds(ny, nx) and grid[ny][nx] != EMPTY:
                            allowed.add((ny, nx))
    return allowed

def teleport_to_nearest_perimeter():
    global player_x, player_y
    if (player_y, player_x) in player_perimeter:
        return  # player is fine

    # Find the nearest perimeter tile using Manhattan distance
    nearest = None
    nearest_dist = float('inf')
    for (py, px) in player_perimeter:
        dist = abs(py - player_y) + abs(px - player_x)
        if dist < nearest_dist:
            nearest = (py, px)
            nearest_dist = dist

    if nearest:
        player_y, player_x = nearest

# Player starts at bottom-center border
player_x = GRID_W//2
player_y = GRID_H-1
on_border = True
lifeforce = 9
score = 0
drawing = False
trail_cells = []  # list of (y,x) in trail order
# global variable storing allowed perimeter tiles
player_perimeter = compute_player_perimeter()

# Qix enemy - a single moving point
qix_pos = [GRID_H//3, GRID_W//3]
qix_vel = [1, 1]

def move_qix():
    # simple random-walk with occasional random direction tweak
    if random.random() < 0.02:
        qix_vel[0] *= -1 if random.random() < 0.5 else 1
        qix_vel[1] *= -1 if random.random() < 0.5 else 1

    ny = qix_pos[0] + qix_vel[0]
    nx = qix_pos[1] + qix_vel[1]

    # bounce only if next tile is FILLED or BORDER
    if not in_bounds(ny, nx) or grid[ny][nx] in (FILLED, BORDER):
        # reverse velocities as in your original code
        if not in_bounds(ny, nx) or grid[ny][nx] == BORDER:
            qix_vel[0] *= -1
            qix_vel[1] *= -1
        else:
            # reverse only the offending axis
            if not in_bounds(ny, qix_pos[1]) or grid[ny][qix_pos[1]] in (FILLED, BORDER):
                qix_vel[0] *= -1
            if not in_bounds(qix_pos[0], nx) or grid[qix_pos[0]][nx] in (FILLED, BORDER):
                qix_vel[1] *= -1

        ny = qix_pos[0] + qix_vel[0]
        nx = qix_pos[1] + qix_vel[1]

    # final move: only apply move if empty or trail (do not enter FILLED/BORDER)
    if in_bounds(ny, nx) and grid[ny][nx] in (EMPTY, TRAIL):
        qix_pos[0], qix_pos[1] = ny, nx

def commit_trail_and_fill():
    global score, player_perimeter
    if not trail_cells:
        return

    # If trail is just a single tile, check adjacent perimeter tiles
    if len(trail_cells) == 1:
        y, x = trail_cells[0]
        # Count adjacent tiles that are in the current perimeter
        adjacent_count = 0
        for dy, dx in ((0,1),(0,-1),(1,0),(-1,0)):
            ny, nx = y + dy, x + dx
            if (ny, nx) in player_perimeter:
                adjacent_count += 1
        if adjacent_count < 3:
            # Single tile not connected enough then ignore
            grid[y][x] = EMPTY
            trail_cells.clear()
            return
    
    # Treat trail as temporary barrier for flood-fill
    for (y, x) in trail_cells:
        grid[y][x] = FILLED  # mark trail as filled immediately

    # lood-fill from Qix to find reachable empty tiles
    reachable_from_qix = grid_fill_from_points([(qix_pos[0], qix_pos[1])])

    # Any empty tile not reachable becomes FILLED
    newly_filled = 0
    for y in range(GRID_H):
        for x in range(GRID_W):
            if grid[y][x] == EMPTY and (y, x) not in reachable_from_qix:
                grid[y][x] = FILLED
                newly_filled += 1

    # Trail is already marked FILLED
    score += newly_filled * 10
    trail_cells.clear()
    # dynamically recompute player perimeter
    player_perimeter = compute_player_perimeter()

    teleport_to_nearest_perimeter()


def reset_trail():
    global trail_cells
    for (y,x) in trail_cells:
        if grid[y][x] == TRAIL:
            grid[y][x] = EMPTY
    trail_cells = []

# Main loop
running = True
move_delay = 0
while running:
    dt = clock.tick(FPS)
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                running = False

    keys = pygame.key.get_pressed()
    

    # Defining the trail key
    TRAIL_KEY = pygame.K_SPACE

    # Inside main loop, after keys = pygame.key.get_pressed():
    trail_pressed = keys[TRAIL_KEY]

    # Player movement with single-axis and last-key lock
    dx = dy = 0
    pressed_keys = {
        pygame.K_LEFT: (-1, 0),
        pygame.K_RIGHT: (1, 0),
        pygame.K_UP: (0, -1),
        pygame.K_DOWN: (0, 1)
    }

    # Update last_key if a new key is pressed
    for key in pressed_keys:
        if keys[key]:
            if last_key is None or last_key != key:
                last_key = key
            break

    # Apply movement along last_key only
    if last_key is not None:
        dx, dy = pressed_keys[last_key]
        # Reset last_key if key released
        if not keys[last_key]:
            last_key = None

    # move player at controlled rate
    if dx != 0 or dy != 0:
        nx = player_x + dx
        ny = player_y + dy
        #if in_bounds(ny, nx) and (ny, nx) in player_perimeter:
        if in_bounds(ny, nx) and ((ny, nx) in player_perimeter or (trail_pressed and grid[ny][nx] == EMPTY) or grid[ny][nx] == TRAIL):

        #if in_bounds(ny, nx) and ((ny, nx) in player_perimeter or grid[ny][nx] in (EMPTY, BORDER)):

        #if in_bounds(ny, nx):
            # If currently on border and move off border into EMPTY/FILLED:
            if grid[player_y][player_x] == BORDER and grid[ny][nx] == EMPTY:
                trail_start_pos = (player_y, player_x)
                print(trail_start_pos)
                # start drawing trail
                drawing = True
                trail_cells = []

            if grid[player_y][player_x] == FILLED and grid[ny][nx] == EMPTY:
                trail_start_pos = (player_y, player_x)
                print(trail_start_pos)
                # start drawing trail
                drawing = True
                trail_cells = []
                

            # If drawing and moving onto Qix (player's square hits the qix not the trail) -> lose life
            if drawing and (ny, nx) == (qix_pos[0], qix_pos[1]):
                lifeforce -= 1
                reset_trail()
                drawing = False
                player_y, player_x = trail_start_pos
            else:
                player_x, player_y = nx, ny
                # add trail if we're in empty playfield
                if drawing:
                    if grid[player_y][player_x] == TRAIL:
                        # crossing own trail -> death
                        print("Crossed own trail!")
                        lifeforce -= 1
                        reset_trail()
                        drawing = False
                        player_y, player_x = trail_start_pos

                    else:
                        # mark trail
                        if grid[player_y][player_x] == EMPTY:
                            grid[player_y][player_x] = TRAIL
                            trail_cells.append((player_y, player_x))
                else:
                    # if not drawing and we moved along border or into filled area, nothing special
                    pass

            # If we returned to border while drawing -> commit trail
            if drawing and grid[player_y][player_x] == BORDER:
                commit_trail_and_fill()
                player_perimeter = compute_player_perimeter()
                trail_cells = []
                drawing = False

            # If we returned into FILLED area (closing by touching filled) -> commit
            if drawing and grid[player_y][player_x] == FILLED:
                commit_trail_and_fill()
                player_perimeter = compute_player_perimeter()
                trail_cells = []
                drawing = False

    # Move qix
    move_qix()

    # Collisions: qix intersects trail -> lose life
    if tuple(qix_pos) in trail_cells:
        lifeforce -= 1
        reset_trail()
        drawing = False
        player_y, player_x = trail_start_pos
        

    # Draw
    #screen.fill((0,0,0))
    screen.blit(background_img, (0, 0))
    draw_grid()

    # draw trail overlay (in case trail set)
    for (y,x) in trail_cells:
        rect = pygame.Rect(x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE)
        pygame.draw.rect(screen, COL_TRAIL, rect)

    # draw perimeter outline
    for (y,x) in player_perimeter:
        rect = pygame.Rect(x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE)
        pygame.draw.rect(screen, COL_PERIMETER, rect, 1)

    # draw player
    pygame.draw.rect(screen, COL_PLAYER, pygame.Rect(player_x*TILE_SIZE, player_y*TILE_SIZE, TILE_SIZE, TILE_SIZE))
    # draw qix
    pygame.draw.rect(screen, COL_QIX, pygame.Rect(qix_pos[1]*TILE_SIZE, qix_pos[0]*TILE_SIZE, TILE_SIZE, TILE_SIZE))

    # HUD
    txt = font.render(f"Lifeforce: {lifeforce}  Score: {score}  Filled: {int(percent_filled()*100)}%", True, (255,255,255))

    screen.blit(txt, (10, 10))
    

    pygame.display.flip()

    # check game over / win
    if lifeforce <= 0:
        print("Game Over")
        running = False
    if percent_filled() >= FILL_THRESHOLD:
        print("You Win!")
        running = False

pygame.quit()
