# chess_ai_agent.py
# Requirements: pip install pygame python-chess
# Put stockfish exe in engine/stockfish-windows-x86-64-avx2.exe (or change ENGINE_PATH)

import os
import sys
import time
import random
import pygame
import chess
import chess.engine

# ---------------- CONFIG ----------------
ENGINE_PATH = os.path.join("engine", "stockfish-windows-x86-64-avx2.exe")
BOARD_SIZE = 800
SQUARE_SIZE = BOARD_SIZE // 8
FPS = 60

# Colors
LIGHT = (240, 217, 181)
DARK = (181, 136, 99)
HIGHLIGHT = (100, 200, 255)
LAST_MOVE_COL = (120, 220, 120)
SELECT_COL = (200, 120, 20)
TEXT_LIGHT = (20, 20, 20)
TEXT_DARK = (245, 245, 245)
RESULT_COL = (220, 40, 40)

# two-letter piece labels (lowercase used for black, uppercase shown for white)
PIECE_ABBR = {'p': 'pa', 'n': 'kn', 'b': 'bi', 'r': 'ro', 'q': 'qu', 'k': 'ki'}

# ---------------- Setup ----------------
pygame.init()
pygame.font.init()
FONT = pygame.font.SysFont("DejaVuSans", 40, bold=True)
SMALL_FONT = pygame.font.SysFont("DejaVuSans", 22)
WIN = pygame.display.set_mode((BOARD_SIZE, BOARD_SIZE + 60))
pygame.display.set_caption("Play vs Stockfish - Click to move | ← back  → forward  ↓ live  R reset")

# Ask difficulty in console (no tkinter)
try:
    level = int(input("Choose Stockfish difficulty (1-20), Enter for default 5: ") or 5)
except Exception:
    level = 5
level = max(1, min(20, level))
print("Skill level set to", level)

# Engine setup (use python-chess engine)
engine = None
time_per_move = max(0.05, 0.05 + level * 0.07)  # seconds to give the engine per move (demo)
if os.path.exists(ENGINE_PATH):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
        # try to configure skill (some builds accept 'Skill Level')
        try:
            engine.configure({'Skill Level': level})
        except Exception:
            # fallback: limit strength via elo (best-effort)
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
move_history = []         # list of chess.Move objects (both players)
history_pointer = 0       # how many moves are currently applied (0..len(move_history))
selected_square = None
legal_moves_for_sel = []
last_player_move_time = None
ai_is_thinking = False
human_color = chess.WHITE  # you play White by default

# ---------------- helpers ----------------
def square_to_pixel(sq):
    """Return (x,y) top-left pixel for a chess.square index."""
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
    """Push a move onto board and record in history (used for player and AI)."""
    global move_history, history_pointer
    board.push(move)
    move_history.append(move)
    history_pointer = len(move_history)

def ai_make_move():
    """Make AI move using engine or random fallback. Updates history."""
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
                # fallback
                best = random.choice(list(board.legal_moves))
        else:
            best = random.choice(list(board.legal_moves))
        push_move_and_record(best)
    except Exception as e:
        print("AI move error:", e)
        # fallback random
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
        pygame.draw.rect(WIN, LAST_MOVE_COL, (fx, fy, SQUARE_SIZE, SQUARE_SIZE), 6)
        pygame.draw.rect(WIN, LAST_MOVE_COL, (tx, ty, SQUARE_SIZE, SQUARE_SIZE), 6)

    # highlight selected & legal targets
    if selected_square is not None:
        sx, sy = square_to_pixel(selected_square)
        pygame.draw.rect(WIN, SELECT_COL, (sx, sy, SQUARE_SIZE, SQUARE_SIZE), 6)
        for mv in legal_moves_for_sel:
            tx, ty = square_to_pixel(mv.to_square)
            pygame.draw.circle(WIN, HIGHLIGHT, (tx + SQUARE_SIZE//2, ty + SQUARE_SIZE//2), 14)

    # pieces (draw labels)
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece:
            x, y = square_to_pixel(sq)
            abbr = PIECE_ABBR[piece.symbol().lower()]
            label = abbr.upper() if piece.color == chess.WHITE else abbr.lower()
            # choose contrasting color for text
            text_color = TEXT_LIGHT if is_light_square(sq) else TEXT_DARK
            surf = FONT.render(label, True, text_color)
            rect = surf.get_rect(center=(x + SQUARE_SIZE//2, y + SQUARE_SIZE//2))
            WIN.blit(surf, rect)

    # bottom info
    status = "Your turn" if board.turn == human_color and not board.is_game_over() else ("AI thinking..." if ai_is_thinking else "AI's turn" if not board.is_game_over() else "Game over")
    info_surf = SMALL_FONT.render(f"{status}    (← back  → forward  ↓ live  R reset)", True, (230,230,230))
    WIN.blit(info_surf, (10, BOARD_SIZE + 5))

    # show result if game over
    if board.is_game_over():
        res = board.result()  # "1-0","0-1","1/2-1/2"
        text = "Draw" if res == "1/2-1/2" else ("White wins" if res == "1-0" else "Black wins")
        res_surf = FONT.render(f"Game Over: {text}", True, RESULT_COL)
        rect = res_surf.get_rect(center=(BOARD_SIZE//2, BOARD_SIZE + 30))
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

        # If it's AI's turn and we have just made a player move, wait 1s then make AI move
        if not board.is_game_over() and board.turn != human_color and last_player_move_time is not None:
            if time.time() - last_player_move_time >= 1 and not ai_is_thinking:
                ai_make_move()
                last_player_move_time = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                # history navigation
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
                    # reset game
                    board.reset()
                    move_history = []
                    history_pointer = 0
                    selected_square = None
                    legal_moves_for_sel = []
                    last_player_move_time = None
                    print("Board reset.")

            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Only allow interaction in live mode (history_pointer at latest)
                mx, my = event.pos
                if my >= BOARD_SIZE:
                    continue  # clicked below board (info area)
                if history_pointer != len(move_history):
                    # jump to live automatically when user clicks to play
                    history_pointer = len(move_history)
                    update_board_from_history()

                # only player's turn can select/move (human_color)
                if board.is_game_over():
                    continue

                clicked_sq = pixel_to_square((mx, my))
                if clicked_sq is None:
                    continue

                # selecting
                if selected_square is None:
                    piece = board.piece_at(clicked_sq)
                    if piece and piece.color == human_color and board.turn == human_color:
                        selected_square = clicked_sq
                        # calc legal moves from this square
                        legal_moves_for_sel = [mv for mv in board.legal_moves if mv.from_square == selected_square]
                        # debug:
                        # print("Selected", selected_square, "legal:", [m.uci() for m in legal_moves_for_sel])
                else:
                    # attempt move from selected_square to clicked_sq
                    # handle promotion auto to queen if needed
                    mv = chess.Move(selected_square, clicked_sq)
                    if mv not in board.legal_moves:
                        # try promotion (auto queen) for pawn
                        if (board.piece_at(selected_square) and board.piece_at(selected_square).piece_type == chess.PAWN):
                            mvq = chess.Move(selected_square, clicked_sq, promotion=chess.QUEEN)
                            if mvq in board.legal_moves:
                                mv = mvq
                    if mv in board.legal_moves and board.turn == human_color:
                        push_move_and_record(mv)
                        selected_square = None
                        legal_moves_for_sel = []
                        last_player_move_time = time.time()
                        # if AI should play immediately (we wait 1s above)
                    else:
                        # invalid move or not player's turn: deselect
                        selected_square = None
                        legal_moves_for_sel = []

    # END loop
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
