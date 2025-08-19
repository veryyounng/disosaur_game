from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== 게임 전역 상태 ======
BOARD_SIZE = 5
N_WALLS = 3
GOAL = (4, 4)           # ✅ 목표 지점 (x=4, y=4)
GAME_OVER = False       # ✅ 게임 종료 상태


# 방향 벡터
DIR_MAP = {
    "up":    (0, -1),
    "down":  (0,  1),
    "left":  (-1, 0),
    "right": (1,  0),
}
DIRECTION = DIR_MAP["right"]  # 시작 방향

# 스네이크, 벽, 사과
SNAKE = [[0, 0]]  # 머리만 1칸으로 시작
WALLS = []        # [(x,y), ...]
APPLE = None      # (x,y)

# ====== 유틸 ======
def in_bounds(x: int, y: int) -> bool:
    return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE

def random_empty_cell(excludes: set[tuple[int, int]]) -> tuple[int, int]:
    # 빈 칸 하나 무작위 선택 (보드가 아주 좁으니 무한루프 방지 시도 제한)
    candidates = [(x, y) for x in range(BOARD_SIZE) for y in range(BOARD_SIZE) if (x, y) not in excludes]
    if not candidates:
        return None
    return random.choice(candidates)

def reset_game():
    global SNAKE, WALLS, DIRECTION, APPLE, GAME_OVER
    DIRECTION = DIR_MAP["right"]
    SNAKE = [[0, 0]]
    WALLS = []
    GAME_OVER = False  # ✅ 리셋 시 게임오버 해제

    occupied = {(x, y) for (x, y) in SNAKE}
    occupied.add(GOAL)  # ✅ 집 위치엔 아무것도 생성하지 않기

    # 랜덤 벽 생성 (집/뱀 제외)
    tries = 0
    while len(WALLS) < N_WALLS and tries < 200:
        x = random.randint(0, BOARD_SIZE - 1)
        y = random.randint(0, BOARD_SIZE - 1)
        if (x, y) not in occupied and (x, y) not in WALLS:
            WALLS.append((x, y))
            occupied.add((x, y))
        tries += 1

    # 사과도 집/뱀/벽 제외
    APPLE = random_empty_cell(occupied)

def opposite(a: tuple[int,int], b: tuple[int,int]) -> bool:
    # 정반대 방향인지 체크
    return a[0] == -b[0] and a[1] == -b[1]

# 앱 시작 시 초기화
reset_game()

# ====== 모델 ======
class DirectionRequest(BaseModel):
    direction: str

# ====== API ======
def reset_game():
    global SNAKE, WALLS, DIRECTION, APPLE, GAME_OVER
    DIRECTION = DIR_MAP["right"]
    SNAKE = [[1, 1]]
    WALLS = []
    GAME_OVER = False  # ✅ 리셋 시 게임오버 해제

    occupied = {(x, y) for (x, y) in SNAKE}
    occupied.add(GOAL)  # ✅ 집 위치엔 아무것도 생성하지 않기

    # 랜덤 벽 생성 (집/뱀 제외)
    tries = 0
    while len(WALLS) < N_WALLS and tries < 200:
        x = random.randint(0, BOARD_SIZE - 1)
        y = random.randint(0, BOARD_SIZE - 1)
        if (x, y) not in occupied and (x, y) not in WALLS:
            WALLS.append((x, y))
            occupied.add((x, y))
        tries += 1

    # 사과도 집/뱀/벽 제외
    APPLE = random_empty_cell(occupied)
@app.get("/api/state")
def get_state():
    board = [["" for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]

    # 벽
    for (wx, wy) in WALLS:
        board[wy][wx] = "🧱"

    # 집(목표)
    gx, gy = GOAL
    board[gy][gx] = "🏠"

    # 사과
    if APPLE is not None:
        ax, ay = APPLE
        board[ay][ax] = "🍎"

    # 스네이크 (머리/몸)
    for i, (sx, sy) in enumerate(SNAKE):
        board[sy][sx] = "🦖" if i == 0 else "🦕"

    return {
        "board": board,
        "snake": SNAKE,
        "apple": APPLE,
        "walls": WALLS,
        "direction": DIRECTION,
        "goal": GOAL,
        "game_over": GAME_OVER,
    }

@app.post("/api/reset")
def reset():
    reset_game()
    return {"status": "reset", "snake": SNAKE, "apple": APPLE, "walls": WALLS}

@app.post("/api/change_direction")
def change_direction(req: DirectionRequest):
    global DIRECTION
    if GAME_OVER:  # ✅ 종료 후 입력 무시(프론트는 메시지로 처리)
        return {"status": "finished"}

    d = req.direction.lower()
    if d not in DIR_MAP:
        return {"status": "invalid", "reason": "unknown direction"}
    new_dir = DIR_MAP[d]
    if len(SNAKE) >= 2 and opposite(new_dir, DIRECTION):
        return {"status": "invalid", "reason": "opposite turn not allowed"}

    DIRECTION = new_dir
    return {"status": "ok", "direction": DIRECTION}

@app.post("/api/move")
def move():
    global SNAKE, APPLE, GAME_OVER

    if GAME_OVER:  # ✅ 종료 후 이동 무시
        return {"status": "finished", "game_over": True}

    dx, dy = DIRECTION
    head_x, head_y = SNAKE[0]
    nx, ny = head_x + dx, head_y + dy

    # 경계/벽 충돌
    if not in_bounds(nx, ny) or (nx, ny) in WALLS:
        GAME_OVER = True
        return {"status": "crash", "game_over": True}

    # ✅ 목표 도달 체크 (먹이 처리보다 선행)
    if (nx, ny) == GOAL:
        SNAKE = [[nx, ny]] + SNAKE[:-1] if len(SNAKE) > 0 else [[nx, ny]]
        GAME_OVER = True
        return {
            "status": "goal",
            "game_over": True,
            "snake": SNAKE,
            "apple": APPLE,
        }

    will_grow = (APPLE is not None and (nx, ny) == APPLE)

    # 자기충돌(꼬리 빠질 예외 허용)
    body_set = set(map(tuple, SNAKE))
    tail = tuple(SNAKE[-1])
    if (nx, ny) in body_set and not (not will_grow and (nx, ny) == tail):
        GAME_OVER = True
        return {"status": "crash", "game_over": True}

    new_head = [nx, ny]
    if will_grow:
        SNAKE = [new_head] + SNAKE
        occupied = set(map(tuple, SNAKE)).union(WALLS)
        occupied.add(GOAL)  # ✅ 집에는 사과 재생성 금지
        APPLE = random_empty_cell(occupied)
        return {"status": "ok", "event": "eat", "snake": SNAKE, "apple": APPLE}
    else:
        SNAKE = [new_head] + SNAKE[:-1]
        return {"status": "ok", "event": "move", "snake": SNAKE, "apple": APPLE}


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.mount("/", StaticFiles(directory=os.path.join(BASE_DIR, "frontend"), html=True), name="static")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
