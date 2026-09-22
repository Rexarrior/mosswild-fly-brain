"""Frozen stateless control: same eight sensory channels, no map or goal access.

An equal-weight bilateral reflex replaces the entire connectome + readout.
Needs, scent geometry, avoidance encoding and the body remain in Unreal.
These gains are declared before embodied evaluation, not fitted to its outcomes.
"""
import math

VERSION = 'reactive-v1'


def motor(channels):
    if len(channels) != 8 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in channels):
        raise ValueError('Expected eight finite sensory channels in [0,1]')
    # Each modality already includes its need and distance weighting in C++.
    lateral = sum(channels[i] - channels[i + 1] for i in (0, 2, 4))
    turn = max(-1., min(1., 4. * lateral))
    # Arousal increases speed, turning and looming reduce it. No extra resource
    # detection, target selection, hidden coordinates, state or randomness.
    drive = min(1., 2. * channels[6]) * (1. - .5 * channels[7]) / (1. + abs(turn))
    return dict(turn=turn, drive=drive, escape=0., left_hz=0., right_hz=0., forward_hz=0.,
                neural_ms=0, decoder=VERSION)
