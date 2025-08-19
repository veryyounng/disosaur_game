# backend/main.py

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import random
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

class DirectionRequest(BaseModel):
    direction: str

# Game 상태
BOARD_SIZE = 5
DIRECTION = [1, 0]  # 오른쪽
SNAKE = [[1, 2], [1, 1], [1, 0]]  # [머리, 몸1, 몸2]
WALLS = [(3, 1), (4, 2)]  # 고정 벽

# API용
class GameState(BaseModel):
    board: list

def reset_game():
    global SNAKE, WALLS, DIRECTION
    DIRECTION = [1, 0]  # 오른쪽
    SNAKE = [[0, 0]]  # 몸 길이 1칸
    WALLS = []

    while len(WALLS) < 3:  # 랜덤 벽 3개 생성
        x, y = random.randint(0, BOARD_SIZE - 1), random.randint(0, BOARD_SIZE - 1)
        if [x, y] not in SNAKE and (x, y) not in WALLS:
            WALLS.append((x, y))

reset_game()


@app.post("/api/change_direction")
def change_direction(req: DirectionRequest):
    global DIRECTION
    dir_map = {
        "up": [0, -1],
        "down": [0, 1],
        "left": [-1, 0],
        "right": [1, 0]
    }
    if req.direction in dir_map:
        DIRECTION = dir_map[req.direction]
        return {"status": "ok", "direction": DIRECTION}
    else:
        return {"status": "invalid direction"}


@app.post("/api/reset")
def reset():
    reset_game()
    return {"status": "reset", "snake": SNAKE, "walls": WALLS}


@app.get("/api/state")
def get_state():
    board = [["" for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    
    # 벽 표시
    for x, y in WALLS:
        board[y][x] = "🧱"
    
    # 뱀 표시
    for i, (x, y) in enumerate(SNAKE):
        board[y][x] = "🦖" if i == 0 else "🦕"
    
    return {"board": board, "snake": SNAKE}

@app.post("/api/move")
def move():
    global SNAKE
    dx, dy = DIRECTION
    head_x, head_y = SNAKE[0]
    nx, ny = head_x + dx, head_y + dy

    if (nx, ny) in WALLS or not (0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE):
        return {"status": "crash"}

    new_head = [nx, ny]
    SNAKE = [new_head] + SNAKE[:-1]  # 이동: 머리 추가, 꼬리 삭제
    return {"status": "ok", "snake": SNAKE}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.mount("/", StaticFiles(directory=os.path.join(BASE_DIR, "frontend"), html=True), name="static")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=port)