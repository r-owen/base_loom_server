import pathlib
import tempfile
import time

import aiosqlite
import pytest
from dtx_to_wif import read_pattern_file

from base_loom_server.pattern_database import (
    FIELD_TYPE_DICT,
    PatternDatabase,
    create_pattern_database,
)
from base_loom_server.reduced_pattern import (
    ReducedPattern,
    reduced_pattern_from_pattern_data,
)
from base_loom_server.testutils import ALL_PATTERN_PATHS


def read_reduced_pattern(path: pathlib.Path) -> ReducedPattern:
    full_pattern = read_pattern_file(path)
    return reduced_pattern_from_pattern_data(name=path.name, data=full_pattern)


async def test_add_and_get_pattern() -> None:
    with tempfile.NamedTemporaryFile() as f:
        dbpath = pathlib.Path(f.name)
        db = await create_pattern_database(dbpath)

        assert len(ALL_PATTERN_PATHS) > 4
        patternpath1 = ALL_PATTERN_PATHS[-2]
        patternpath2 = ALL_PATTERN_PATHS[1]

        pattern1 = read_reduced_pattern(patternpath1)

        await db.add_pattern(pattern1)
        pattern_names = await db.get_pattern_names()
        assert pattern_names == [pattern1.name]
        returned_pattern1 = await db.get_pattern(pattern1.name)

        # All attributes should match the original
        for field_name in vars(returned_pattern1):
            assert getattr(pattern1, field_name) == getattr(returned_pattern1, field_name)

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


async def test_check_schema() -> None:
    with tempfile.NamedTemporaryFile() as f:
        dbpath = pathlib.Path(f.name)
        db = await create_pattern_database(dbpath)
        assert await db.check_schema()

    # Create a database with missing or wrong-typed fields
    # (set wrong_type to None to delete the field)
    for field_name, wrong_type in (
        ("pattern_name", None),
        ("pick_number", None),
        ("pattern_json", "integer"),
        ("end_number0", "real"),
    ):
        bad_field_type_dict = FIELD_TYPE_DICT.copy()
        if wrong_type is None:
            del bad_field_type_dict[field_name]
        else:
            bad_field_type_dict[field_name] = wrong_type
        fields_str = ", ".join(f"{key} {value}" for key, value in bad_field_type_dict.items())
        with tempfile.NamedTemporaryFile() as f:
            dbpath = pathlib.Path(f.name)
            db = PatternDatabase(dbpath=dbpath)
            async with aiosqlite.connect(db.dbpath) as conn:
                await conn.execute(f"create table if not exists patterns ({fields_str})")
                await conn.commit()
            assert not await db.check_schema()


async def test_clear_database() -> None:
    with tempfile.NamedTemporaryFile() as f:
        dbpath = pathlib.Path(f.name)
        db = await create_pattern_database(dbpath)

        num_to_add = 3
        for patternpath in ALL_PATTERN_PATHS[0:num_to_add]:
            pattern = read_reduced_pattern(patternpath)
            await db.add_pattern(pattern)

        pattern_names = await db.get_pattern_names()
        expected_pattern_names = [patternpath.name for patternpath in ALL_PATTERN_PATHS[0:num_to_add]]
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
        expected_pattern_names = [patternpath.name for patternpath in ALL_PATTERN_PATHS[0:num_to_add]]
        assert pattern_names == expected_pattern_names

        # Test that a re-created database has the saved information
        dbpath = pathlib.Path(f.name)
        db = await create_pattern_database(dbpath)
        initial_pattern_names = await db.get_pattern_names()
        assert initial_pattern_names == expected_pattern_names


async def test_update_end_number() -> None:
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
        expected_pattern_names = [patternpath.name for patternpath in ALL_PATTERN_PATHS[0:num_to_add]]
        assert pattern_names == expected_pattern_names

        for pattern_name, end_number0, end_number1, end_repeat_number in (
            (pattern_names[0], 50, 51, 0),
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
        expected_pattern_names = [patternpath.name for patternpath in ALL_PATTERN_PATHS[0:num_to_add]]
        assert pattern_names == expected_pattern_names

        for pattern_name, pick_number, pick_repeat_number in (
            (pattern_names[0], 50, 0),
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


async def test_update_separate_threading_repeats() -> None:
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
        expected_pattern_names = [patternpath.name for patternpath in ALL_PATTERN_PATHS[0:num_to_add]]
        assert pattern_names == expected_pattern_names

        for pattern_name, separate_threading_repeats in (
            (pattern_names[0], True),
            (pattern_names[1], False),
            (pattern_names[0], True),
            (pattern_names[2], False),
        ):
            separate_weaving_repeats = not separate_threading_repeats
            await db.update_separate_threading_repeats(
                pattern_name=pattern_name,
                separate_threading_repeats=separate_threading_repeats,
            )
            await db.update_separate_weaving_repeats(
                pattern_name=pattern_name,
                separate_weaving_repeats=not separate_threading_repeats,
            )
            pattern = await db.get_pattern(pattern_name)
            assert pattern.name == pattern_name
            assert pattern.separate_threading_repeats == separate_threading_repeats
            assert pattern.separate_weaving_repeats == separate_weaving_repeats


async def test_update_thread_group_size() -> None:
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
        expected_pattern_names = [patternpath.name for patternpath in ALL_PATTERN_PATHS[0:num_to_add]]
        assert pattern_names == expected_pattern_names

        for pattern_name, thread_group_size in (
            (pattern_names[0], 50),
            (pattern_names[1], 3),
            (pattern_names[0], 4),
            (pattern_names[2], 15),
        ):
            await db.update_thread_group_size(
                pattern_name=pattern_name,
                thread_group_size=thread_group_size,
            )
            pattern = await db.get_pattern(pattern_name)
            assert pattern.name == pattern_name
            assert pattern.thread_group_size == thread_group_size
