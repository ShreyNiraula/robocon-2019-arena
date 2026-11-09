"""Constants for the arena, robots and animation.

Distances are in arena units (the field is about 13.4 x 10.1 units, roughly
metres) and times in seconds.
"""

from __future__ import annotations

import os
from pathlib import Path

from pyglm import glm

ASSETS_DIR = Path(os.environ.get("ROBOCON_ASSETS", Path(__file__).resolve().parents[2] / "assets"))

MODELS = {
    "arena": "models/arena/arena.obj",
    "robot_red": "models/robot/TeamARobot.obj",
    "robot_blue": "models/robot/TeamBRobot.obj",
    "spider_red": "models/spider/TeamASpider.obj",
    "spider_blue": "models/spider/TeamBSpider.obj",
}

# --- window -----------------------------------------------------------------
WINDOW_SIZE = (1280, 720)
WINDOW_TITLE = "ABU Robocon 2019 - Great Urtuu"
BACKGROUND = (0.05, 0.05, 0.05)

# --- lighting ---------------------------------------------------------------
LIGHT_COLOR = glm.vec3(1.0, 1.0, 1.0)
LIGHT_HEIGHT = 5.0
LIGHT_ORBIT_RADIUS = 6.0
LIGHT_ORBIT_RATE = 1.0  # radians per second
AMBIENT = 0.5
SPECULAR_STRENGTH = 0.3

# --- start positions (x, y, z) ----------------------------------------------
# Red (team A) plays on -x, blue (team B) on +x. The start zones are at -z.
# MR1 starts on the end of the white guideline in Khangai urtuu.
ROBOT_RED_START = glm.vec3(-6.15, 0.04, -4.55)
ROBOT_BLUE_START = glm.vec3(6.15, 0.04, -4.55)
# MR2 starts on the cross in Gobi urtuu, at the top of its guideline.
SPIDER_RED_START = glm.vec3(-1.22, 0.0, 2.45)
SPIDER_BLUE_START = glm.vec3(1.22, 0.0, 2.45)

# --- cameras: (position, yaw, pitch) ----------------------------------------
OVERVIEW_CAMERA = (glm.vec3(0.0, 9.5, -14.5), 90.0, -32.0)

# --- showcase modes (1-3) -----------------------------------------------------
# The exhibit turns slowly in place.
SHOWCASE_SPIN_RATE = 0.25  # radians per second (about 25 s per turn)
ARENA_SHOWCASE_CAMERA = (glm.vec3(0.0, 12.5, -15.5), 90.0, -38.0)  # fits the arena at any angle
SHOWCASE_ROBOT_SCALE = 10.0

# --- simulation -------------------------------------------------------------
MAX_FRAME_TIME = 0.1  # clamp long frames (window drags, breakpoints) so nothing jumps

# --- match mode (4) ---------------------------------------------------------
# MR1 is a line follower: full speed on straights, braking to a stop at each corner.
MR1_MAX_SPEED = 2.0  # units (about metres) per second
MR1_ACCEL = 2.0  # units per second squared, for speeding up and braking
MR2_WALK_SPEED = 0.6  # across the Gobi area
MR2_CLIMB_SPEED = 0.4  # up the mountain
# Rule 1.8.2: MR2 may climb only after MR1 scores 50 points throwing the Shagai. The
# Shagai is not modelled, so MR2 simply waits this long at Mountain urtuu.
MR2_URTUU_WAIT = 3.0
SPIDER_SWAY_ANGLE = 45.0  # degrees either side while waiting
SPIDER_SWAY_PERIOD = 8.3  # seconds for one sway back and forth

# --- robot's-eye view (5) ---------------------------------------------------
RIDE_SPEED = 0.6  # slower than the match so the forest is easy to follow
MR1_EYE_HEIGHT = 0.16
MR2_EYE_HEIGHT = 0.15
RIDE_LOOKAHEAD = 0.8  # aim the camera this far along the route to smooth the weave
RIDE_TURN_RATE = 4.0  # how quickly the camera turns towards the route (1/s)

# --- time trial (6) ---------------------------------------------------------
CHECKPOINT_RADIUS = 0.45  # pass within this distance of each guideline corner
TRIAL_CAMERA = (glm.vec3(-4.9, 10.5, -8.0), 90.0, -60.0)  # looks down on the red half

# --- manual driving and collision -------------------------------------------
MR1_RADIUS = 0.35  # half the chassis width, from the model's bounding box
