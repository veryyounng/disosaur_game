from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os, random

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ====== 게임 전역 상태 ======
BOARD_SIZE = 5
N_WALLS = 3
GOAL = (4, 4)              # 집 좌표
START_POS = (0, 0)         # 시작 좌표 (지금 코드 기준)
GAME_OVER = False

DIR_MAP = {
    "up": (0, -1), "down": (0, 1),
    "left": (-1, 0), "right": (1, 0)
}
DIRECTION = DIR_MAP["right"]

SNAKE = [list(START_POS)]  # 머리만 1칸으로 시작
WALLS: list[tuple[int,int]] = []
APPLE: tuple[int,int] | None = None

# ====== 유틸 ======
def in_bounds(x: int, y: int) -> bool:
    return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE

def random_empty_cell(excludes: set[tuple[int, int]]) -> tuple[int, int] | None:
    cells = [(x, y) for x in range(BOARD_SIZE) for y in range(BOARD_SIZE)
             if (x, y) not in excludes]
    return random.choice(cells) if cells else None

def opposite(a: tuple[int,int], b: tuple[int,int]) -> bool:
    return a[0] == -b[0] and a[1] == -b[1]

def reset_game():
    """게임 상태를 한 번에 초기화"""
    global SNAKE, WALLS, DIRECTION, APPLE, GAME_OVER
    DIRECTION = DIR_MAP["right"]
    SNAKE = [list(START_POS)]
    WALLS = []
    GAME_OVER = False

    occupied = {tuple(SNAKE[0]), GOAL}

    # 랜덤 벽
    tries = 0
    while len(WALLS) < N_WALLS and tries < 200:
        x = random.randint(0, BOARD_SIZE - 1)
        y = random.randint(0, BOARD_SIZE - 1)
        if (x, y) not in occupied:
            WALLS.append((x, y))
            occupied.add((x, y))
        tries += 1

    # 사과
    APPLE = random_empty_cell(occupied)

# 앱 시작 시 한 번 초기화
reset_game()

# ====== 모델 ======
class DirectionRequest(BaseModel):
    direction: str

# ====== API ======
@app.get("/api/state")
def get_state():
    board = [["" for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    for (wx, wy) in WALLS:
        board[wy][wx] = "🧱"
    gx, gy = GOAL
    board[gy][gx] = "🏠"
    if APPLE is not None:
        ax, ay = APPLE
        board[ay][ax] = "🍎"
    for i, (sx, sy) in enumerate(SNAKE):
        board[sy][sx] = "🦖" if i == 0 else "🦕"
    return {
        "board": board, "snake": SNAKE, "apple": APPLE,
        "walls": WALLS, "direction": DIRECTION,
        "goal": GOAL, "game_over": GAME_OVER,
    }

@app.post("/api/reset")
def reset():
    reset_game()
    return {"status": "reset", "snake": SNAKE, "apple": APPLE, "walls": WALLS}

@app.post("/api/change_direction")
def change_direction(req: DirectionRequest):
    global DIRECTION
    if GAME_OVER:
        return {"status": "finished"}
    d = req.direction.lower()
    if d not in DIR_MAP:
        return {"status": "invalid", "reason": "unknown direction"}
    new_dir = DIR_MAP[d]
    # 길이 2칸 이상일 때 즉시 U턴 금지 (기본 룰)
    if len(SNAKE) >= 2 and opposite(new_dir, DIRECTION):
        return {"status": "invalid", "reason": "opposite turn not allowed"}
    DIRECTION = new_dir
    return {"status": "ok", "direction": DIRECTION}

@app.post("/api/move")
def move():
    global SNAKE, APPLE, GAME_OVER
    if GAME_OVER:
        return {"status": "finished", "game_over": True}

    dx, dy = DIRECTION
    head_x, head_y = SNAKE[0]
    nx, ny = head_x + dx, head_y + dy

    # 경계/벽 충돌
    if not in_bounds(nx, ny) or (nx, ny) in WALLS:
        GAME_OVER = True
        return {"status": "crash", "game_over": True}

    # 집 도착
    if (nx, ny) == GOAL:
        SNAKE = [[nx, ny]] + SNAKE[:-1] if len(SNAKE) > 0 else [[nx, ny]]
        GAME_OVER = True
        return {"status": "goal", "game_over": True, "snake": SNAKE}

    will_grow = (APPLE is not None and (nx, ny) == APPLE)

    # 자기충돌 (이번 턴에 성장하지 않으면서 '꼬리 자리'로 가는 경우는 허용)
    body_set = set(map(tuple, SNAKE))
    tail = tuple(SNAKE[-1])
    if (nx, ny) in body_set and not (not will_grow and (nx, ny) == tail):
        GAME_OVER = True
        return {"status": "crash", "game_over": True}

    new_head = [nx, ny]
    if will_grow:
        SNAKE = [new_head] + SNAKE                      # 꼬리 유지 → 길이 +1
        occupied = set(map(tuple, SNAKE)).union(WALLS, {GOAL})
        APPLE = random_empty_cell(occupied)             # 새 사과
        return {"status": "ok", "event": "eat", "snake": SNAKE, "apple": APPLE}
    else:
        SNAKE = [new_head] + SNAKE[:-1]                 # 꼬리 제거 → 길이 유지
        return {"status": "ok", "event": "move", "snake": SNAKE, "apple": APPLE}

# 정적 파일 서빙 (항상 라우트 정의들 **뒤에** 둬야 /api가 먹히지 않음)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/", StaticFiles(directory=os.path.join(BASE_DIR, "frontend"), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=True)
