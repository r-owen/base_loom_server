import dataclasses
import json
import pathlib
import time

import aiosqlite

from .reduced_pattern import ReducedPattern


class PatternDatabase:
    FIELDS_STR = ", ".join(
        (
            "id integer primary key",
            "pattern_name text",
            "pattern_json text",
            "pick_number integer",
            "repeat_number integer",
            "timestamp_sec real",
        )
    )

    def __init__(self, dbpath: pathlib.Path) -> None:
        self.dbpath = dbpath

    async def init(self) -> None:
        async with aiosqlite.connect(self.dbpath) as db:
            await db.execute(f"create table if not exists patterns ({self.FIELDS_STR})")
            await db.commit()

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

        Parameters
        ----------
        pattern : ReducedPattern
            The pattern to add. The pick_number and repeat_number are ignored.
        max_patterns : int
            Maximum number of patterns to keep; if 0 then no limit.
            If there are more than this many patterns in the database,
            the oldest are purged. If keep_name is not None then its
            timestamp is set to a bit later than now.
            and a value of 1 is silently changed to 2,
            so the most recent pattern (which is the current pattern)
            and the new one are both kept.
        """

        pattern_json = json.dumps(dataclasses.asdict(pattern))
        current_time = time.time()
        async with aiosqlite.connect(self.dbpath) as db:
            await db.execute(
                "delete from patterns where pattern_name = ?", (pattern.name,)
            )
            # If limiting the number of entries, make sure to allow
            # at least two, to save the most recent pattern,
            # since it is likely to be the current pattern.
            if max_entries > 0:
                max_entries = max(max_entries, 2)
            await db.execute(
                "insert into patterns "
                "(pattern_name, pattern_json, pick_number, repeat_number, timestamp_sec) "
                "values (?, ?, ?, ?, ?)",
                (pattern.name, pattern_json, 0, 1, current_time),
            )
            await db.commit()

            pattern_names = await self.get_pattern_names()
            names_to_delete = pattern_names[0:-max_entries]

            if len(names_to_delete) > 0:
                # Purge old patterns
                for pattern_name in names_to_delete:
                    await db.execute(
                        "delete from patterns where pattern_name = ?", (pattern_name,)
                    )
                await db.commit()

    async def clear_database(self) -> None:
        """Remove all patterns from the database."""
        async with aiosqlite.connect(self.dbpath) as db:
            await db.execute("delete from patterns")
            await db.commit()

    async def get_pattern(self, pattern_name: str) -> ReducedPattern:
        async with aiosqlite.connect(self.dbpath) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "select * from patterns where pattern_name = ?", (pattern_name,)
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            raise LookupError(f"{pattern_name} not found")
        pattern_dict = json.loads(row["pattern_json"])
        pattern = ReducedPattern.from_dict(pattern_dict)
        pattern.pick_number = row["pick_number"]
        pattern.repeat_number = row["repeat_number"]
        return pattern

    async def get_pattern_names(self) -> list[str]:
        async with aiosqlite.connect(self.dbpath) as db:
            async with db.execute(
                "select pattern_name from patterns order by timestamp_sec asc, id asc"
            ) as cursor:
                rows = await cursor.fetchall()

        return [row[0] for row in rows]

    async def update_pick_number(
        self, pattern_name: str, pick_number: int, repeat_number: int
    ) -> None:
        """Update the pick and repeat numbers for the specified pattern."""
        async with aiosqlite.connect(self.dbpath) as db:
            await db.execute(
                "update patterns "
                "set pick_number = ?, repeat_number = ?, timestamp_sec = ?"
                "where pattern_name = ?",
                (pick_number, repeat_number, time.time(), pattern_name),
            )
            await db.commit()

    async def set_timestamp(self, pattern_name: str, timestamp: float) -> None:
        """Set the timestamp for the specified pattern.

        Parameters
        ----------
        pattern_name : str
            Pattern name
        timestamp : float
            Timestamp in unix seconds, e.g. from time.time()
        """
        async with aiosqlite.connect(self.dbpath) as db:
            await db.execute(
                "update patterns set timestamp_sec = ? where pattern_name = ?",
                (timestamp, pattern_name),
            )
            await db.commit()


async def create_pattern_database(dbpath: pathlib.Path) -> PatternDatabase:
    db = PatternDatabase(dbpath=dbpath)
    await db.init()
    return db
