# qix_like.py
import pygame
import random
from collections import deque
import math

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

# === Qix Settings ===
QIX_SPEED = 3   # frames between moves (higher = slower)
qix_timer = 0   # timer for Qix movement

# === Sparx Settings ===
SPARX_SPEED = 4   # frames between moves (higher = slower)
sparx_timer = 0   # timer for Sparx movement
sparx_list = []


# place opposite side of player (for now top center)
sparx_y, sparx_x = 0, GRID_W // 2
sparx_dir = (0, 1)  # move along border to the right initially
# visual (for smooth movement)
sparx_vis_x = sparx_x * TILE_SIZE
sparx_vis_y = sparx_y * TILE_SIZE

# === Game setup ===
pygame.init()
#screen = pygame.display.set_mode((SCREEN_W + 16, SCREEN_H + 16))
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("The Qix Game")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 24)

background_img = pygame.image.load("water_background.png").convert()
land_img = pygame.image.load("grass.png").convert()
pixel_rock = pygame.image.load("larger_rock.png").convert_alpha()
player_image = pygame.image.load("purple_player.png").convert_alpha()
qix_image = pygame.image.load("octopus.png").convert_alpha()


# create grid and set borders
grid = [[EMPTY for _ in range(GRID_W)] for _ in range(GRID_H)]
for x in range(GRID_W):
    grid[0][x] = BORDER
    grid[GRID_H-1][x] = BORDER
for y in range(GRID_H):
    grid[y][0] = BORDER
    grid[y][GRID_W-1] = BORDER

# helper functions
# everything with grid_w and grid_h will need to be redifned if width and length is to be increased
def in_bounds(y, x):
    return 0 <= x < GRID_W and 0 <= y < GRID_H

def draw_grid():
    for y in range(GRID_H):
        for x in range(GRID_W):
            rect = pygame.Rect(x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE)
            val = grid[y][x]

            if val == BORDER:
                # Draw the corresponding part of the land texture
                tx = (x * TILE_SIZE) % land_img.get_width()
                ty = (y * TILE_SIZE) % land_img.get_height()
                screen.blit(land_img, rect, pygame.Rect(tx, ty, TILE_SIZE, TILE_SIZE))
            elif val == FILLED:
                # Draw the corresponding part of the land texture
                tx = (x * TILE_SIZE) % land_img.get_width()
                ty = (y * TILE_SIZE) % land_img.get_height()
                screen.blit(land_img, rect, pygame.Rect(tx, ty, TILE_SIZE, TILE_SIZE))

            elif val == TRAIL:
                pygame.draw.rect(screen, COL_TRAIL, rect)

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

def init_sparx():
    global sparx_list, ordered_perimeter
    sparx_list = []
    if not ordered_perimeter:
        return

    # choose opposite x coordinate on top/bottom border relative to player
    target_y = 0 if player_y > GRID_H // 2 else GRID_H - 1
    target_x = GRID_W - 1 - player_x

    # find nearest tile on ordered_perimeter
    best_i = min(range(len(ordered_perimeter)),
                 key=lambda i: abs(ordered_perimeter[i][0] - target_y) + abs(ordered_perimeter[i][1] - target_x))
    start_pos = ordered_perimeter[best_i]

    sparx_list.append({
        "pos": start_pos,
        "dir": 1,                # 1 clockwise, -1 counterclockwise
        "idx": best_i,
        "vis_pos": [start_pos[1]*TILE_SIZE, start_pos[0]*TILE_SIZE]
    })


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
qix_vis_pos = [qix_pos[1] * TILE_SIZE, qix_pos[0] * TILE_SIZE]  # [x, y] in pixels


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

def move_sparx():
    global sparx_list, lifeforce, drawing, player_x, player_y, ordered_perimeter

    if not ordered_perimeter:
        return

    L = len(ordered_perimeter)
    for sparx in sparx_list:
        # advance index by dir (one step along the ordered path)
        idx = (sparx["idx"] + sparx["dir"]) % L
        sparx["idx"] = idx
        next_pos = ordered_perimeter[idx]
        sparx["pos"] = next_pos

        # collisions
        if (player_y, player_x) == next_pos:
            lifeforce -= 1
            print("Hit by Sparx!")
            teleport_to_nearest_perimeter() #not needed
            # reverse direction for interest
            sparx["dir"] *= -1

        if drawing and next_pos in trail_cells:
            print("Sparx hit trail! Trail cancelled.")
            lifeforce -= 1
            reset_trail()
            drawing = False
            teleport_to_nearest_perimeter()

def build_ordered_perimeter(perim_set):
    """Return a contiguous ordered list of perimeter tiles by walking around it."""
    if not perim_set:
        return []

    perim = set(perim_set)
    ordered = []

    # Start from the top-leftmost tile (deterministic)
    start = min(perim, key=lambda p: (p[0], p[1]))
    current = start
    prev = None
    ordered.append(current)

    # Directions (clockwise)
    dirs = [(-1,0), (0,1), (1,0), (0,-1)]

    while True:
        # find next neighbor that is in perim
        for dy, dx in dirs:
            ny, nx = current[0] + dy, current[1] + dx
            if (ny, nx) in perim and (ny, nx) != prev:
                prev, current = current, (ny, nx)
                ordered.append(current)
                break
        else:
            # no unvisited neighbor → stop
            break

        # stop if we’ve looped back
        if current == start:
            break

    return ordered

#this may be causing the teleport issues with sparx
def remap_sparx_indices():
    """When ordered_perimeter changes, map each sparx to nearest index in the new path."""
    global sparx_list, ordered_perimeter
    if not ordered_perimeter:
        return
    for sparx in sparx_list:
        sy, sx = sparx["pos"]
        # find nearest tile index
        best_i = min(range(len(ordered_perimeter)),
                     key=lambda i: abs(ordered_perimeter[i][0] - sy) + abs(ordered_perimeter[i][1] - sx))
        sparx["idx"] = best_i
        sparx["pos"] = ordered_perimeter[best_i]

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
    #fix redundancies here
    ordered_perimeter = build_ordered_perimeter(player_perimeter)
    remap_sparx_indices()
    #this may help reduce computation, in the future use trail_start_pos
    if (player_x, player_y) not in player_perimeter:
        teleport_to_nearest_perimeter()


def reset_trail():
    global trail_cells
    for (y,x) in trail_cells:
        if grid[y][x] == TRAIL:
            grid[y][x] = EMPTY
    trail_cells = []

# Initialize Sparx on the opposite side of the player
ordered_perimeter = build_ordered_perimeter(player_perimeter)
init_sparx()

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
                ordered_perimeter = build_ordered_perimeter(player_perimeter)
                remap_sparx_indices()
                trail_cells = []
                drawing = False

            # If we returned into FILLED area (closing by touching filled) -> commit
            if drawing and grid[player_y][player_x] == FILLED:
                commit_trail_and_fill()
                player_perimeter = compute_player_perimeter()
                ordered_perimeter = build_ordered_perimeter(player_perimeter)
                remap_sparx_indices()
                trail_cells = []
                drawing = False

    # Move qix
    #move_qix()

    # === Move Qix slowly ===
    qix_timer += 1
    if qix_timer >= QIX_SPEED:
        #print("Moving Qix")
        move_qix()
        qix_timer = 0
    
    # === Move Sparx slowly ===
    sparx_timer += 1
    if sparx_timer >= SPARX_SPEED:
        #print("Moving Sparx")
        move_sparx()
        sparx_timer = 0
    
    #move_sparx()
    # Collisions: qix intersects trail -> lose life
    if tuple(qix_pos) in trail_cells:
        lifeforce -= 1
        reset_trail()
        drawing = False
        player_y, player_x = trail_start_pos
        

    # Draw
    #screen.fill((0,0,0))
    #make it (8,8) if need to centre background on bigger scale to fit player
    screen.blit(background_img, (0, 0))
    draw_grid()

    # draw trail overlay (in case trail set)
    for (y,x) in trail_cells:
        rect = pygame.Rect(x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE)
        pygame.draw.rect(screen, COL_TRAIL, rect)

    #(x * tilesize - 1 or 2) is used to centre larger player and rock images on 8x8 tile

    # draw perimeter outline
    for (y, x) in player_perimeter:
        pos = ((x * TILE_SIZE) -1, (y * TILE_SIZE) -1)
        screen.blit(pixel_rock, pos)

    '''
    for (y,x) in player_perimeter:
        rect = pygame.Rect(x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE)
        pygame.draw.rect(screen, COL_PERIMETER, rect, 1)
    '''

    # draw player
    #pygame.draw.rect(screen, COL_PLAYER, pygame.Rect(player_x*TILE_SIZE, player_y*TILE_SIZE, TILE_SIZE, TILE_SIZE))
    screen.blit(player_image, ((player_x * TILE_SIZE) - 3, (player_y * TILE_SIZE) - 3))

    # draw qix
    #pygame.draw.rect(screen, COL_QIX, pygame.Rect(qix_pos[1]*TILE_SIZE, qix_pos[0]*TILE_SIZE, TILE_SIZE, TILE_SIZE))
        # === Smooth Qix movement ===
    target_x = qix_pos[1] * TILE_SIZE
    target_y = qix_pos[0] * TILE_SIZE
    # Interpolate toward target (0.2 controls smoothness; smaller = slower, smoother)
    qix_vis_pos[0] += (target_x - qix_vis_pos[0]) * 0.3
    qix_vis_pos[1] += (target_y - qix_vis_pos[1]) * 0.3

    # Draw Qix at interpolated position
    screen.blit(qix_image, (qix_vis_pos[0] - 4, qix_vis_pos[1] - 4))

    # HUD
    txt = font.render(f"Lifeforce: {lifeforce}  Score: {score}  Filled: {int(percent_filled()*100)}%", True, (255,255,255))

    screen.blit(txt, (0, 0))
    for sparx in sparx_list:
        target_x = sparx["pos"][1] * TILE_SIZE
        target_y = sparx["pos"][0] * TILE_SIZE
        sparx["vis_pos"][0] += (target_x - sparx["vis_pos"][0]) * 0.2
        sparx["vis_pos"][1] += (target_y - sparx["vis_pos"][1]) * 0.2
        pygame.draw.circle(screen, (255, 0, 0), (int(sparx["vis_pos"][0]) +5, int(sparx["vis_pos"][1]) +5), 4)

    pygame.display.flip()

    # check game over / win
    if lifeforce <= 0:
        print("Game Over")
        running = False
    if percent_filled() >= FILL_THRESHOLD:
        print("You Win!")
        running = False

pygame.quit()
