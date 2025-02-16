import pathlib
import tempfile
import time

import pytest

from base_loom_server.pattern_database import (
    CACHE_DEFAULT_DICT,
    create_pattern_database,
)
from base_loom_server.reduced_pattern import (
    ReducedPattern,
    read_full_pattern,
    reduced_pattern_from_pattern_data,
)
from base_loom_server.testutils import ALL_PATTERN_PATHS


def read_reduced_pattern(path: pathlib.Path) -> ReducedPattern:
    full_pattern = read_full_pattern(path)
    return reduced_pattern_from_pattern_data(name=path.name, data=full_pattern)


async def test_add_and_get_pattern() -> None:
    with tempfile.NamedTemporaryFile() as f:
        dbpath = pathlib.Path(f.name)
        db = await create_pattern_database(dbpath)

        assert len(ALL_PATTERN_PATHS) > 4
        patternpath1 = ALL_PATTERN_PATHS[-2]
        patternpath2 = ALL_PATTERN_PATHS[1]

        pattern1 = read_reduced_pattern(patternpath1)

        # Check that adding a pattern ignores cache values:
        # * pick_number
        # * pick_repeat_number
        # * end_number0
        # * end_repeat_number
        pattern1.pick_number = 20
        pattern1.pick_repeat_number = 21
        pattern1.end_number0 = 22
        pattern1.end_repeat_number = 25
        await db.add_pattern(pattern1)
        pattern_names = await db.get_pattern_names()
        assert pattern_names == [pattern1.name]
        returned_pattern1 = await db.get_pattern(pattern1.name)

        # Cached values should be set to defaults
        # when reading a newly added pattern
        for field_name, value in CACHE_DEFAULT_DICT.items():
            assert getattr(returned_pattern1, field_name) == value

        # Non-cached values should match the original
        non_cached_fields = set(vars(returned_pattern1)) - set(CACHE_DEFAULT_DICT)
        for field_name in non_cached_fields:
            assert getattr(pattern1, field_name) == getattr(
                returned_pattern1, field_name
            )

        # Adding another pattern puts it to the end of the name list
        pattern2 = read_reduced_pattern(patternpath2)
        await db.add_pattern(pattern2)
        names = await db.get_pattern_names()
        assert names == [pattern1.name, pattern2.name]

        # Re-adding a pattern that is already present moves it
        # to the end of the name list
        await db.add_pattern(pattern1)
        names = await db.get_pattern_names()
        assert names == [pattern2.name, pattern1.name]

        # Cannot get a pattern that does not exist
        with pytest.raises(LookupError):
            await db.get_pattern("no such pattern")

        # Test purging old patterns while adding new ones
        patternpath3 = ALL_PATTERN_PATHS[0]
        pattern3 = read_reduced_pattern(patternpath3)
        await db.add_pattern(pattern3, max_entries=2)
        pattern_names = await db.get_pattern_names()
        assert pattern_names == [pattern1.name, pattern3.name]

        # Adding pattern 3 again has no effect on what is purged
        # because pattern 3 is first deleted, then re-added
        patternpath3 = ALL_PATTERN_PATHS[0]
        pattern3 = read_reduced_pattern(patternpath3)
        await db.add_pattern(pattern3, max_entries=2)
        pattern_names = await db.get_pattern_names()
        assert pattern_names == [pattern1.name, pattern3.name]

        # Update the timestamp for pattern 1, then add pattern 2 again.
        # This should purge pattern 3.
        # Also confirm that max_entries = 1 is changed to 2.
        await db.set_timestamp(pattern1.name, timestamp=time.time())
        await db.add_pattern(pattern2, max_entries=1)
        pattern_names = await db.get_pattern_names()
        assert pattern_names == [pattern1.name, pattern2.name]


async def test_clear_database() -> None:
    with tempfile.NamedTemporaryFile() as f:
        dbpath = pathlib.Path(f.name)
        db = await create_pattern_database(dbpath)

        num_to_add = 3
        for patternpath in ALL_PATTERN_PATHS[0:num_to_add]:
            pattern = read_reduced_pattern(patternpath)
            await db.add_pattern(pattern)
            pattern_names = await db.get_pattern_names()

        expected_pattern_names = [
            patternpath.name for patternpath in ALL_PATTERN_PATHS[0:num_to_add]
        ]
        assert pattern_names == expected_pattern_names

        await db.clear_database()
        pattern_names_after_clear = await db.get_pattern_names()
        assert pattern_names_after_clear == []


async def test_create_database() -> None:
    with tempfile.NamedTemporaryFile() as f:
        dbpath = pathlib.Path(f.name)
        db = await create_pattern_database(dbpath)
        initial_pattern_names = await db.get_pattern_names()
        assert initial_pattern_names == []

        num_to_add = 3
        for patternpath in ALL_PATTERN_PATHS[0:num_to_add]:
            pattern = read_reduced_pattern(patternpath)
            await db.add_pattern(pattern)
            pattern_names = await db.get_pattern_names()

        expected_pattern_names = [
            patternpath.name for patternpath in ALL_PATTERN_PATHS[0:num_to_add]
        ]
        assert pattern_names == expected_pattern_names

        # Test that a re-created database has the saved information
        dbpath = pathlib.Path(f.name)
        db = await create_pattern_database(dbpath)
        initial_pattern_names = await db.get_pattern_names()
        assert initial_pattern_names == expected_pattern_names


async def test_update_threading_end_number() -> None:
    with tempfile.NamedTemporaryFile() as f:
        dbpath = pathlib.Path(f.name)
        db = await create_pattern_database(dbpath)
        initial_pattern_names = await db.get_pattern_names()
        assert initial_pattern_names == []

        num_to_add = 3
        for patternpath in ALL_PATTERN_PATHS[0:num_to_add]:
            pattern = read_reduced_pattern(patternpath)
            await db.add_pattern(pattern)
            pattern_names = await db.get_pattern_names()

        expected_pattern_names = [
            patternpath.name for patternpath in ALL_PATTERN_PATHS[0:num_to_add]
        ]
        assert pattern_names == expected_pattern_names

        for pattern_name, end_number0, end_number1, end_repeat_number in (
            (pattern_names[0], 50, 51, -5),
            (pattern_names[1], 3, 42, 49),
            (pattern_names[0], 0, 0, 1),
            (pattern_names[2], 15, 60, 101),
        ):
            await db.update_end_number(
                pattern_name=pattern_name,
                end_number0=end_number0,
                end_number1=end_number1,
                end_repeat_number=end_repeat_number,
            )
            pattern = await db.get_pattern(pattern_name)
            assert pattern.name == pattern_name
            assert pattern.end_number0 == end_number0
            assert pattern.end_number1 == end_number1
            assert pattern.end_repeat_number == end_repeat_number


async def test_update_pick_number() -> None:
    with tempfile.NamedTemporaryFile() as f:
        dbpath = pathlib.Path(f.name)
        db = await create_pattern_database(dbpath)
        initial_pattern_names = await db.get_pattern_names()
        assert initial_pattern_names == []

        num_to_add = 3
        for patternpath in ALL_PATTERN_PATHS[0:num_to_add]:
            pattern = read_reduced_pattern(patternpath)
            await db.add_pattern(pattern)
            pattern_names = await db.get_pattern_names()

        expected_pattern_names = [
            patternpath.name for patternpath in ALL_PATTERN_PATHS[0:num_to_add]
        ]
        assert pattern_names == expected_pattern_names

        for pattern_name, pick_number, pick_repeat_number in (
            (pattern_names[0], 50, -5),
            (pattern_names[1], 3, 49),
            (pattern_names[0], 0, 1),
            (pattern_names[2], 15, 101),
        ):
            await db.update_pick_number(
                pattern_name=pattern_name,
                pick_number=pick_number,
                pick_repeat_number=pick_repeat_number,
            )
            pattern = await db.get_pattern(pattern_name)
            assert pattern.name == pattern_name
            assert pattern.pick_number == pick_number
            assert pattern.pick_repeat_number == pick_repeat_number
