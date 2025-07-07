__all__ = ["PatternDatabase", "create_pattern_database"]

import dataclasses
import json
import pathlib
import time

import aiosqlite

from .reduced_pattern import ReducedPattern

FIELD_TYPE_DICT = dict(
    id="integer primary key",
    pattern_name="text",
    pattern_json="text",
    pick_number="integer",
    pick_repeat_number="integer",
    end_number0="integer",
    end_number1="integer",
    end_repeat_number="integer",
    thread_group_size="integer",
    separate_weaving_repeats="integer",
    separate_threading_repeats="integer",
    timestamp_sec="real",
)

FIELDS_STR = ", ".join(f"{key} {value}" for key, value in FIELD_TYPE_DICT.items())


def _make_insert_str() -> str:
    """Make the value for INSERT_STR from FIELD_TYPE_DICT."""
    field_names = [field_name for field_name in FIELD_TYPE_DICT if field_name != "id"]
    field_names_str = ", ".join(field_names)
    placeholders_str = ", ".join(["?"] * len(field_names))
    return f"insert into patterns ({field_names_str}) values ({placeholders_str})"  # noqa: S608


INSERT_STR = _make_insert_str()

CACHE_FIELD_NAMES = (
    "pick_number",
    "pick_repeat_number",
    "end_number0",
    "end_number1",
    "end_repeat_number",
    "thread_group_size",
    "separate_weaving_repeats",
    "separate_threading_repeats",
)

REPEAT_FIELD_NAMES = {
    "pick_repeat_number",
    "end_repeat_number",
}


class PatternDatabase:
    """sqlite database to hold ReducedPattern instances.

    The patterns are stored as json strings, but the
    the associated cache fields are saved in separate fields
    so they can be updated as they change (the values in the json
    strings are ignored during pattern retrieval).
    """

    def __init__(self, dbpath: pathlib.Path) -> None:
        self.dbpath = dbpath

    async def init(self) -> None:
        """Create the database, if it does not exist."""
        async with aiosqlite.connect(self.dbpath) as conn:
            await conn.execute(f"create table if not exists patterns ({FIELDS_STR})")
            await conn.commit()

    async def check_schema(self) -> bool:
        """Return True if the patterns table schema is as expected.

        Extra fields in the table are ignored.
        """
        async with (
            aiosqlite.connect(self.dbpath) as conn,
            conn.execute("pragma table_info(patterns)") as cursor,
        ):
            field_info_list = await cursor.fetchall()

        field_info_dict = {
            field_info[1]: (field_info[2].lower(), bool(field_info[-1])) for field_info in field_info_list
        }
        for field_name, expected_field_type in FIELD_TYPE_DICT.items():
            field_type_is_primary = field_info_dict.get(field_name)
            if field_type_is_primary is None:
                return False
            if field_name == "id":
                if field_type_is_primary != ("integer", True):
                    return False
            elif field_type_is_primary != (expected_field_type, False):
                return False

        return True

    async def add_pattern(
        self,
        pattern: ReducedPattern,
        max_entries: int = 0,
    ) -> None:
        """Add a new pattern to the database.

        Add the specified pattern to the database, overwriting
        any existing pattern by that name (with a new id number,
        so the new pattern is the most recent).
        Prune excess patterns and return the resulting pattern names.

        Args:
            pattern: The pattern to add. The associated cache fields
                are set to values from the pattern:

                * pick_number
                * pick_repeat_number
                * end_number0
                * end_number1
                * end_repeat_number
                * thread_group_size
                * separate_weaving_repeats
                * separate_threading_repeats

            max_entries: Maximum number of patterns to keep; no limit if 0.
                If >0 and there are more patterns in the database,
                the oldest are purged.
        """
        pattern_json = json.dumps(dataclasses.asdict(pattern))
        cache_values = tuple(getattr(pattern, field) for field in CACHE_FIELD_NAMES)
        current_time = time.time()
        async with aiosqlite.connect(self.dbpath) as conn:
            await conn.execute("delete from patterns where pattern_name = ?", (pattern.name,))
            # If limiting the number of entries, make sure to allow
            # at least two, to save the most recent pattern,
            # since it is likely to be the current pattern.
            if max_entries > 0:
                max_entries = max(max_entries, 2)
            await conn.execute(
                INSERT_STR,
                (pattern.name, pattern_json, *cache_values, current_time),
            )
            await conn.commit()

            pattern_names = await self.get_pattern_names()
            names_to_delete = pattern_names[0:-max_entries]

            if len(names_to_delete) > 0:
                # Purge old patterns
                for pattern_name in names_to_delete:
                    await conn.execute("delete from patterns where pattern_name = ?", (pattern_name,))
                await conn.commit()

    async def clear_database(self) -> None:
        """Remove all patterns from the database."""
        async with aiosqlite.connect(self.dbpath) as conn:
            await conn.execute("delete from patterns")
            await conn.commit()

    async def get_pattern(self, pattern_name: str) -> ReducedPattern:
        """Get the named pattern."""
        async with aiosqlite.connect(self.dbpath) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "select * from patterns where pattern_name = ?", (pattern_name,)
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            raise LookupError(f"{pattern_name} not found")
        pattern_dict = json.loads(row["pattern_json"])
        pattern = ReducedPattern.from_dict(pattern_dict)
        for field_name in CACHE_FIELD_NAMES:
            value = row[field_name]
            if field_name in REPEAT_FIELD_NAMES and value < 0:
                # From an older version that allowed jump numbers < 0
                value = 0
            setattr(pattern, field_name, value)
        return pattern

    async def get_pattern_names(self) -> list[str]:
        """Get all pattern names."""
        async with (
            aiosqlite.connect(self.dbpath) as conn,
            conn.execute("select pattern_name from patterns order by timestamp_sec asc, id asc") as cursor,
        ):
            rows = await cursor.fetchall()

        return [row[0] for row in rows]

    async def update_pick_number(
        self, *, pattern_name: str, pick_number: int, pick_repeat_number: int
    ) -> None:
        """Update weaving pick and repeat numbers for the specified pattern."""
        async with aiosqlite.connect(self.dbpath) as conn:
            await conn.execute(
                "update patterns "
                "set pick_number = ?, pick_repeat_number = ?, timestamp_sec = ?"
                "where pattern_name = ?",
                (pick_number, pick_repeat_number, time.time(), pattern_name),
            )
            await conn.commit()

    async def update_end_number(
        self,
        *,
        pattern_name: str,
        end_number0: int,
        end_number1: int,
        end_repeat_number: int,
    ) -> None:
        """Update threading end & repeat numbers for the specified pattern."""
        async with aiosqlite.connect(self.dbpath) as conn:
            await conn.execute(
                "update patterns "
                "set end_number0 = ?, end_number1 = ?, end_repeat_number = ?, timestamp_sec = ?"
                "where pattern_name = ?",
                (
                    end_number0,
                    end_number1,
                    end_repeat_number,
                    time.time(),
                    pattern_name,
                ),
            )
            await conn.commit()

    async def update_separate_threading_repeats(
        self,
        *,
        pattern_name: str,
        separate_threading_repeats: bool,
    ) -> None:
        """Update separate_threading_repeats for the specified pattern."""
        async with aiosqlite.connect(self.dbpath) as conn:
            await conn.execute(
                "update patterns set separate_threading_repeats = ?, timestamp_sec = ?where pattern_name = ?",
                (int(separate_threading_repeats), time.time(), pattern_name),
            )
            await conn.commit()

    async def update_separate_weaving_repeats(
        self,
        *,
        pattern_name: str,
        separate_weaving_repeats: bool,
    ) -> None:
        """Update separate_weaving_repeats for the specified pattern."""
        async with aiosqlite.connect(self.dbpath) as conn:
            await conn.execute(
                "update patterns set separate_weaving_repeats = ?, timestamp_sec = ?where pattern_name = ?",
                (int(separate_weaving_repeats), time.time(), pattern_name),
            )
            await conn.commit()

    async def update_thread_group_size(self, pattern_name: str, thread_group_size: int) -> None:
        """Update thread_group_size for the specified pattern."""
        async with aiosqlite.connect(self.dbpath) as conn:
            await conn.execute(
                "update patterns set thread_group_size = ?, timestamp_sec = ?where pattern_name = ?",
                (thread_group_size, time.time(), pattern_name),
            )
            await conn.commit()

    async def set_timestamp(self, pattern_name: str, timestamp: float) -> None:
        """Set the timestamp for the specified pattern.

        Args:
        pattern_name: Pattern name.
        timestamp: Timestamp in unix seconds, e.g. from time.time().
        """
        async with aiosqlite.connect(self.dbpath) as conn:
            await conn.execute(
                "update patterns set timestamp_sec = ? where pattern_name = ?",
                (timestamp, pattern_name),
            )
            await conn.commit()


async def create_pattern_database(dbpath: pathlib.Path) -> PatternDatabase:
    """Create the pattern database."""
    db = PatternDatabase(dbpath=dbpath)
    await db.init()
    return db
