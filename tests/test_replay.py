"""
Replay: a seed and a command stream reproduce the game exactly.
"""

from __future__ import annotations

import pytest
from conftest import loot_definition, monster_definition, treasure_definition

from fsme.cards import CardInstance
from fsme.commands import Command, CommandType
from fsme.replay import (
    Recorder,
    Recording,
    ReplayDivergence,
    ReplayFormatError,
    ReplayIntegrityError,
    ReplayPlayer,
    ReplayStatus,
    replay,
    state_digest,
)
from fsme.rng.rng import RNG
from fsme.rules.slots import place
from fsme.runtime import Runtime
from fsme.state import GameState, PlayerState

SEED = 4242


def build_state() -> GameState:
    """
    The starting position. Deterministic, and identical every call.
    """
    state = GameState(seed=SEED)

    for index in range(3):
        state.add_player(PlayerState(player_id=index, name=f"player{index}"))

    for index in range(30):
        state.loot_deck.add_top(
            CardInstance(
                definition=loot_definition(f"test.loot{index}"),
                instance_id=f"loot:{index}",
            )
        )

    for index in range(3):
        place(state, 
            CardInstance(
                definition=monster_definition(f"test.monster{index}"),
                instance_id=f"monster:{index}",
                controller=None,
                owner=None,
            )
        )

    for index in range(2):
        state.treasure_shop.add_top(
            CardInstance(
                definition=treasure_definition(f"test.shop{index}"),
                instance_id=f"shop:{index}",
                controller=None,
                owner=None,
            )
        )

    return state


SCRIPT = [
    (CommandType.START_GAME, 0, {}),
    (CommandType.PLAY_LOOT, 0, {"index": 0}),
    (CommandType.END_PHASE, 0, {}),
    (CommandType.ATTACK, 0, {"index": 0}),
    (CommandType.END_TURN, 0, {}),
    (CommandType.PLAY_LOOT, 1, {"index": 0}),
    (CommandType.END_PHASE, 1, {}),
    (CommandType.ATTACK, 1, {"index": 0}),
    (CommandType.END_TURN, 1, {}),
]


def record_a_game() -> tuple[Recorder, Recording]:
    state = build_state()
    runtime = Runtime(state, rng=RNG(state.seed))
    recorder = Recorder(runtime, content_version="test")

    for command_type, player, payload in SCRIPT:
        recorder.submit(
            Command(type=command_type, player=player, payload=dict(payload))
        )

    return recorder, recorder.recording()


def test_a_recorded_game_replays_identically() -> None:
    recorder, recording = record_a_game()

    player = replay(recording, build_state)

    assert player.finished
    assert player.status is ReplayStatus.FINISHED
    assert state_digest(player.state) == state_digest(recorder.runtime.state)


def test_replay_reproduces_the_event_stream() -> None:
    recorder, recording = record_a_game()

    player = replay(recording, build_state)

    original = [
        (event.event_id, str(event.type)) for event in recorder.runtime.history
    ]
    reproduced = [
        (event.event_id, str(event.type)) for event in player.runtime.history
    ]

    assert reproduced == original


def test_replaying_twice_gives_the_same_result() -> None:
    """
    REPLAY_SYSTEM.md section 12: repeated playback must always agree.
    """
    _, recording = record_a_game()

    first = replay(recording, build_state)
    second = replay(recording, build_state)

    assert state_digest(first.state) == state_digest(second.state)


def test_only_accepted_commands_are_recorded() -> None:
    state = build_state()
    runtime = Runtime(state, rng=RNG(state.seed))
    recorder = Recorder(runtime)

    recorder.submit(Command(type=CommandType.START_GAME, player=0))
    rejected = recorder.submit(Command(type=CommandType.END_TURN, player=2))

    assert rejected.rejected
    assert len(recorder) == 1


def test_playback_can_be_stepped_and_reset() -> None:
    _, recording = record_a_game()

    player = ReplayPlayer(recording, build_state)

    assert player.status is ReplayStatus.READY
    assert player.position == 0

    player.step()
    player.step()

    assert player.position == 2
    assert player.state.started is True

    player.reset()

    assert player.position == 0
    assert player.state.started is False


def test_stopping_ends_playback() -> None:
    _, recording = record_a_game()

    player = ReplayPlayer(recording, build_state)
    player.step()
    player.stop()

    assert player.step() is False
    assert player.status is ReplayStatus.STOPPED
    assert player.position == 1


def test_a_recording_survives_a_round_trip_through_a_file(tmp_path) -> None:
    _, recording = record_a_game()

    path = recording.save(tmp_path / "game.fsmr")
    loaded = Recording.load(path)

    assert loaded.seed == recording.seed
    assert loaded.commands == recording.commands
    assert loaded.checksum == recording.checksum

    player = replay(loaded, build_state)

    assert player.finished


def test_a_tampered_recording_is_refused() -> None:
    """
    REPLAY_SYSTEM.md section 10: corruption is caught before playback.
    """
    _, recording = record_a_game()

    tampered = Recording(
        seed=recording.seed + 1,
        commands=recording.commands,
        checksum=recording.checksum,
    )

    with pytest.raises(ReplayIntegrityError):
        tampered.verify()


def test_an_unsupported_format_is_refused() -> None:
    recording = Recording(seed=1, format_version="99")

    with pytest.raises(ReplayFormatError):
        recording.check_compatibility()


def test_divergence_names_the_command_that_diverged() -> None:
    """
    A digest mismatch means the engine stopped being deterministic, so the
    replay points at where it happened instead of failing vaguely at the end.
    """
    _, recording = record_a_game()

    commands = list(recording.commands)
    poisoned = commands[3]
    commands[3] = type(poisoned)(
        type=poisoned.type,
        player=poisoned.player,
        payload=poisoned.payload,
        digest="0" * 32,
    )

    broken = Recording(seed=recording.seed, commands=tuple(commands)).sealed()

    with pytest.raises(ReplayDivergence) as error:
        replay(broken, build_state)

    assert "command 3" in str(error.value)


def test_verification_can_be_switched_off() -> None:
    _, recording = record_a_game()

    commands = list(recording.commands)
    poisoned = commands[3]
    commands[3] = type(poisoned)(
        type=poisoned.type,
        player=poisoned.player,
        payload=poisoned.payload,
        digest="0" * 32,
    )

    broken = Recording(seed=recording.seed, commands=tuple(commands)).sealed()

    player = replay(broken, build_state, verify=False)

    assert player.finished


def test_a_different_seed_produces_a_different_game() -> None:
    _, recording = record_a_game()

    other = Recording(
        seed=recording.seed + 1,
        commands=recording.commands,
    ).sealed()

    with pytest.raises(ReplayDivergence):
        replay(other, build_state)
