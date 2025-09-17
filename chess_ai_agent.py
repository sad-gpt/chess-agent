
import os
import sys
import time
import random
import pygame
import chess
import chess.engine


ENGINE_PATH = os.path.join("engine", "stockfish-windows-x86-64-avx2.exe")
BOARD_SIZE = 640  # smaller than before
SQUARE_SIZE = BOARD_SIZE // 8
FPS = 60
INFO_HEIGHT = 120  # bottom area for moves/status

# Colors
LIGHT = (240, 217, 181)
DARK = (181, 136, 99)
HIGHLIGHT = (100, 200, 255)
LAST_MOVE_COL = (120, 220, 120)
SELECT_COL = (200, 120, 20)
RESULT_COL = (220, 40, 40)
TEXT_COLOR = (20, 20, 20)

# ---------------- Setup ----------------
pygame.init()
pygame.font.init()
FONT = pygame.font.SysFont("DejaVuSans", 36, bold=True)
SMALL_FONT = pygame.font.SysFont("DejaVuSans", 18)
WIN = pygame.display.set_mode((BOARD_SIZE, BOARD_SIZE + INFO_HEIGHT))
pygame.display.set_caption("Play vs Stockfish - Click to move | ← back  → forward  ↓ live  R reset")

# Load piece images with correct knight key
PIECE_IMAGES = {}
PIECE_FOLDER = "pieces"
key_map = {'pawn':'p','knight':'n','bishop':'b','rook':'r','queen':'q','king':'k'}
for color in ["white", "black"]:
    for piece in ["pawn", "knight", "bishop", "rook", "queen", "king"]:
        filename = f"{color}-{piece}.png"
        path = os.path.join(PIECE_FOLDER, filename)
        if os.path.exists(path):
            img = pygame.image.load(path)
            key = color[0] + key_map[piece]
            PIECE_IMAGES[key] = pygame.transform.smoothscale(img, (SQUARE_SIZE, SQUARE_SIZE))
        else:
            print("Missing image:", path)

# Ask difficulty
try:
    level = int(input("Choose Stockfish difficulty (1-20), Enter for default 5: ") or 5)
except Exception:
    level = 5
level = max(1, min(20, level))
print("Skill level set to", level)

# Engine setup
engine = None
time_per_move = max(0.05, 0.05 + level * 0.07)
if os.path.exists(ENGINE_PATH):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
        try:
            engine.configure({'Skill Level': level})
        except Exception:
            try:
                engine.configure({'UCI_LimitStrength': True, 'UCI_Elo': 800 + level * 100})
            except Exception:
                pass
        print("Stockfish launched:", ENGINE_PATH)
    except Exception as e:
        print("Failed to start engine, falling back to random AI. Error:", e)
        engine = None
else:
    print("Engine exe not found at", ENGINE_PATH, "- falling back to random AI.")

# Game state
board = chess.Board()
move_history = []
history_pointer = 0
selected_square = None
legal_moves_for_sel = []
last_player_move_time = None
ai_is_thinking = False
human_color = chess.WHITE

# ---------------- helpers ----------------
def square_to_pixel(sq):
    file = chess.square_file(sq)
    rank = chess.square_rank(sq)
    x = file * SQUARE_SIZE
    y = (7 - rank) * SQUARE_SIZE
    return x, y

def pixel_to_square(pos):
    x, y = pos
    if x < 0 or y < 0 or x >= BOARD_SIZE or y >= BOARD_SIZE:
        return None
    col = x // SQUARE_SIZE
    row = y // SQUARE_SIZE
    rank = 7 - row
    return chess.square(int(col), int(rank))

def update_board_from_history():
    global board
    board = chess.Board()
    for mv in move_history[:history_pointer]:
        board.push(mv)

def push_move_and_record(move):
    global move_history, history_pointer
    board.push(move)
    move_history.append(move)
    history_pointer = len(move_history)

def ai_make_move():
    global ai_is_thinking
    if board.is_game_over():
        return
    ai_is_thinking = True
    try:
        if engine:
            limit = chess.engine.Limit(time=time_per_move)
            res = engine.play(board, limit)
            best = res.move
            if best is None:
                best = random.choice(list(board.legal_moves))
        else:
            best = random.choice(list(board.legal_moves))
        push_move_and_record(best)
    except Exception as e:
        print("AI move error:", e)
        try:
            mv = random.choice(list(board.legal_moves))
            push_move_and_record(mv)
        except Exception:
            pass
    ai_is_thinking = False

def is_light_square(sq):
    file = chess.square_file(sq)
    rank = chess.square_rank(sq)
    return (file + rank) % 2 == 0

def draw_board():
    WIN.fill((10,10,10))
    # squares
    for r in range(8):
        for c in range(8):
            x = c * SQUARE_SIZE
            y = r * SQUARE_SIZE
            color = LIGHT if (r + c) % 2 == 0 else DARK
            pygame.draw.rect(WIN, color, (x, y, SQUARE_SIZE, SQUARE_SIZE))

    # highlight last move
    if history_pointer > 0:
        last = move_history[history_pointer - 1]
        fx, fy = square_to_pixel(last.from_square)
        tx, ty = square_to_pixel(last.to_square)
        pygame.draw.rect(WIN, LAST_MOVE_COL, (fx, fy, SQUARE_SIZE, SQUARE_SIZE), 4)
        pygame.draw.rect(WIN, LAST_MOVE_COL, (tx, ty, SQUARE_SIZE, SQUARE_SIZE), 4)

    # highlight selected & legal targets
    if selected_square is not None:
        sx, sy = square_to_pixel(selected_square)
        pygame.draw.rect(WIN, SELECT_COL, (sx, sy, SQUARE_SIZE, SQUARE_SIZE), 4)
        for mv in legal_moves_for_sel:
            tx, ty = square_to_pixel(mv.to_square)
            pygame.draw.circle(WIN, HIGHLIGHT, (tx + SQUARE_SIZE//2, ty + SQUARE_SIZE//2), 10)

    # pieces (draw images)
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece:
            x, y = square_to_pixel(sq)
            color = 'w' if piece.color == chess.WHITE else 'b'
            name = ''
            if piece.piece_type == chess.PAWN: name = 'p'
            elif piece.piece_type == chess.KNIGHT: name = 'n'
            elif piece.piece_type == chess.BISHOP: name = 'b'
            elif piece.piece_type == chess.ROOK: name = 'r'
            elif piece.piece_type == chess.QUEEN: name = 'q'
            elif piece.piece_type == chess.KING: name = 'k'
            key = color + name
            img = PIECE_IMAGES.get(key)
            if img:
                WIN.blit(img, (x, y))

    # bottom info area
    pygame.draw.rect(WIN, (50,50,50), (0, BOARD_SIZE, BOARD_SIZE, INFO_HEIGHT))
    
    # status line
    status = "Your turn" if board.turn == human_color and not board.is_game_over() else ("AI thinking..." if ai_is_thinking else "AI's turn" if not board.is_game_over() else "Game over")
    info_surf = SMALL_FONT.render(f"{status}", True, (230,230,230))
    WIN.blit(info_surf, (10, BOARD_SIZE + 5))

    # move history display
    moves_text = " ".join([mv.uci() for mv in move_history])
    moves_lines = [moves_text[i:i+80] for i in range(0, len(moves_text), 80)]  # wrap text
    for idx, line in enumerate(moves_lines):
        line_surf = SMALL_FONT.render(line, True, (240,240,240))
        WIN.blit(line_surf, (10, BOARD_SIZE + 30 + idx*20))

    # show result if game over
    if board.is_game_over():
        res = board.result()
        text = "Draw" if res == "1/2-1/2" else ("White wins" if res == "1-0" else "Black wins")
        res_surf = FONT.render(f"Game Over: {text}", True, RESULT_COL)
        rect = res_surf.get_rect(center=(BOARD_SIZE//2, BOARD_SIZE + INFO_HEIGHT//2))
        WIN.blit(res_surf, rect)

    pygame.display.flip()

# ---------------- Main Loop ----------------
def main():
    global selected_square, legal_moves_for_sel, last_player_move_time, history_pointer, move_history, board, ai_is_thinking
    clock = pygame.time.Clock()
    running = True

    print("Controls: Click a piece to select, click destination to move.")
    print("Arrow keys: ← back  → forward  ↓ jump to live. Press R to reset. Ctrl+C to quit.")

    while running:
        clock.tick(FPS)
        draw_board()

        if not board.is_game_over() and board.turn != human_color and last_player_move_time is not None:
            if time.time() - last_player_move_time >= 1 and not ai_is_thinking:
                ai_make_move()
                last_player_move_time = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    if history_pointer > 0:
                        history_pointer -= 1
                        update_board_from_history()
                elif event.key == pygame.K_RIGHT:
                    if history_pointer < len(move_history):
                        history_pointer += 1
                        update_board_from_history()
                elif event.key == pygame.K_DOWN:
                    history_pointer = len(move_history)
                    update_board_from_history()
                elif event.key == pygame.K_r:
                    board.reset()
                    move_history = []
                    history_pointer = 0
                    selected_square = None
                    legal_moves_for_sel = []
                    last_player_move_time = None
                    print("Board reset.")

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if my >= BOARD_SIZE:
                    continue
                if history_pointer != len(move_history):
                    history_pointer = len(move_history)
                    update_board_from_history()

                if board.is_game_over():
                    continue

                clicked_sq = pixel_to_square((mx, my))
                if clicked_sq is None:
                    continue

                if selected_square is None:
                    piece = board.piece_at(clicked_sq)
                    if piece and piece.color == human_color and board.turn == human_color:
                        selected_square = clicked_sq
                        legal_moves_for_sel = [mv for mv in board.legal_moves if mv.from_square == selected_square]
                else:
                    mv = chess.Move(selected_square, clicked_sq)
                    if mv not in board.legal_moves:
                        if (board.piece_at(selected_square) and board.piece_at(selected_square).piece_type == chess.PAWN):
                            mvq = chess.Move(selected_square, clicked_sq, promotion=chess.QUEEN)
                            if mvq in board.legal_moves:
                                mv = mvq
                    if mv in board.legal_moves and board.turn == human_color:
                        push_move_and_record(mv)
                        selected_square = None
                        legal_moves_for_sel = []
                        last_player_move_time = time.time()
                    else:
                        selected_square = None
                        legal_moves_for_sel = []

    pygame.quit()
    if engine:
        try:
            engine.quit()
        except Exception:
            pass
    print("Exited cleanly.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted by user. Exiting.")
        pygame.quit()
        if engine:
            try:
                engine.quit()
            except Exception:
                pass
        sys.exit(0)
