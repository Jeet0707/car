import os
import re
from typing import Annotated, Any, Literal, Optional, Union

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from store import consume_pending_command, enqueue_command, get_device_state, is_online

DEVICE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

app = FastAPI(title="Khetix API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "x-api-key"],
)


def verify_api_key(x_api_key: Annotated[Optional[str], Header()] = None) -> None:
    expected = os.environ.get("API_KEY")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def validate_device_id(device_id: str) -> str:
    if not DEVICE_ID_RE.match(device_id):
        raise HTTPException(status_code=400, detail="Invalid deviceId")
    return device_id


class CommandBody(BaseModel):
    deviceId: str
    cmd: str
    angle: Optional[int] = None

    @field_validator("deviceId")
    @classmethod
    def check_device_id(cls, value: str) -> str:
        if not DEVICE_ID_RE.match(value):
            raise ValueError("Invalid deviceId")
        return value


class OkResponse(BaseModel):
    ok: bool = True


class PollEmptyResponse(BaseModel):
    cmd: None = None


class PollCutterResponse(BaseModel):
    cmd: Literal["1", "2"]


class PollServoResponse(BaseModel):
    cmd: Literal["servo"]
    angle: int


class StatusResponse(BaseModel):
    cutter: bool
    servoAngle: int
    online: bool
    updatedAt: str
    lastPollAt: Optional[str] = None


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "khetix-api", "status": "ok"}


@app.post("/api/command", dependencies=[Depends(verify_api_key)], response_model=OkResponse)
def post_command(body: CommandBody) -> OkResponse:
    command: dict[str, Any]

    if body.cmd in ("1", "2"):
        command = {"cmd": body.cmd}
    elif body.cmd == "servo":
        if body.angle is None:
            raise HTTPException(
                status_code=400,
                detail='Invalid command. Use cmd "1", "2", or "servo" with angle 0-180.',
            )
        angle = max(0, min(180, round(body.angle)))
        command = {"cmd": "servo", "angle": angle}
    else:
        raise HTTPException(
            status_code=400,
            detail='Invalid command. Use cmd "1", "2", or "servo" with angle 0-180.',
        )

    try:
        enqueue_command(body.deviceId, command)
    except Exception as exc:
        print(f"command enqueue failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to store command") from exc

    return OkResponse()


@app.get(
    "/api/poll",
    dependencies=[Depends(verify_api_key)],
    response_model=Union[PollEmptyResponse, PollCutterResponse, PollServoResponse],
)
def get_poll(deviceId: str = Query(...)) -> Union[PollEmptyResponse, PollCutterResponse, PollServoResponse]:
    validate_device_id(deviceId)

    try:
        pending = consume_pending_command(deviceId)
    except Exception as exc:
        print(f"poll failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to read command") from exc

    if not pending:
        return PollEmptyResponse()

    cmd = pending.get("cmd")
    if cmd in ("1", "2"):
        return PollCutterResponse(cmd=cmd)
    if cmd == "servo":
        return PollServoResponse(cmd="servo", angle=int(pending["angle"]))

    return PollEmptyResponse()


@app.get("/api/status", dependencies=[Depends(verify_api_key)], response_model=StatusResponse)
def get_status(deviceId: str = Query(...)) -> StatusResponse:
    validate_device_id(deviceId)

    try:
        state = get_device_state(deviceId)
    except Exception as exc:
        print(f"status failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to read status") from exc

    return StatusResponse(
        cutter=state["cutter"],
        servoAngle=state["servoAngle"],
        online=is_online(state),
        updatedAt=state["updatedAt"],
        lastPollAt=state.get("lastPollAt"),
    )
