from __future__ import annotations

import asyncio
import dataclasses
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence
    from logging import Logger

from .utils import run_shell_command

HOTSPOT_PRIORITY = 100
WIFI_PRIORITY = 50
DEFAULT_TIMEOUT = 30  # Default timeout for nmcli commands (seconds)
CONNECT_TIMEOUT = 90


@dataclasses.dataclass
class KnownNetwork:
    """Information about a known WiFi network."""

    name: str
    ssid: str
    active: bool
    autoconnect: bool
    autoconnect_priority: int
    is_hotspot: bool


async def run_nmcli(
    subcmd: str,
    *,
    fields: Sequence[str] = (),
    use_sudo: bool = False,
    timeout: float = DEFAULT_TIMEOUT,  # noqa: ASYNC109
) -> list[dict[str, str]]:
    """Run an nmcli command and return the results.

    Args:
        subcmd: The nmcli sub-command: everything after "nmcli" except
            the --fields and --mode command-line options.
        fields: The full names of fields to return. Case is ignored.
        use_sudo: Run the command with sudo?
        timeout: Time limit for the nmcli command (seconds).

    Returns:
        datalist: a list of data dicts, one per set of fields
            (usually one entry per connection, but this depends on the subcmd).
            The keys are the field name cast to lowercase.
            The values are the data for that field, with leading and trailing whitespace stripped.

    Raises:
        RuntimeError: if the command fails.
    """
    sudo_prefix = "sudo " if use_sudo else ""
    fields_str = ",".join(field.lower() for field in fields)
    fields_args = f' --fields "{fields_str}" --mode multiline' if fields else ""
    data_to_return: list[dict[str, str]] = []
    data_str = await asyncio.wait_for(
        run_shell_command(f"{sudo_prefix}nmcli{fields_args} {subcmd}"),
        timeout=timeout,
    )
    last_field = fields[-1].lower() if fields else "?"
    datadict: dict[str, str] = dict()
    if fields:
        for data_line in data_str.split("\n"):
            if not data_line:
                continue
            raw_name, raw_value = data_line.split(":", maxsplit=1)
            name, value = raw_name.lower(), raw_value.strip()
            datadict[name] = value
            if name == last_field:
                # Reached the end of one entry
                data_to_return.append(datadict)
                datadict = dict()
    return data_to_return


async def enable_autoconnect(network: KnownNetwork) -> None:
    """Configure a network to autoconnect."""
    priority = HOTSPOT_PRIORITY if network.is_hotspot else WIFI_PRIORITY
    if network.autoconnect and network.autoconnect_priority == priority:
        # Already configured; nothing to do
        return
    await run_nmcli(
        f'connection modify "{network.name}" '
        f"connection.autoconnect yes connection.autoconnect-priority {HOTSPOT_PRIORITY}",
        use_sudo=True,
    )
    network.autoconnect = True
    network.autoconnect_priority = priority


async def disable_autoconnect(network: KnownNetwork) -> None:
    """Configure a network to not autoconnect."""
    if not network.autoconnect:
        # Already configured; nothing to do
        return
    await run_nmcli(f'connection modify "{network.name}" connection.autoconnect no', use_sudo=True)
    network.autoconnect = False


async def get_known_networks() -> dict[str, KnownNetwork]:
    """Get information about known (configured) WiFi networks.

    Returns:
        A dict of ssid: known network info
    """
    known_networks_dicts = await run_nmcli(
        subcmd="connection show",
        fields=["name", "type", "active", "autoconnect", "autoconnect-priority"],
    )
    known_networks: dict[str, KnownNetwork] = dict()
    for network_dict in known_networks_dicts:
        name = network_dict["name"]
        if network_dict["type"] != "wifi":
            continue
        extra_data = await run_nmcli(
            subcmd=f'connection show "{name}"',
            fields=["802-11-wireless.mode", "802-11-wireless.ssid"],
        )
        if len(extra_data) != 1:
            raise RuntimeError(
                f'Bug: invalid info for network "{name}": {len(extra_data)} items instead of 1'
            )
        network_dict.update(extra_data[0])
        ssid = network_dict["802-11-wireless.ssid"]
        known_networks[ssid] = KnownNetwork(
            name=name,
            ssid=ssid,
            active=network_dict["active"] == "yes",
            autoconnect=network_dict["autoconnect"] == "yes",
            autoconnect_priority=int(network_dict["autoconnect-priority"]),
            is_hotspot=network_dict["802-11-wireless.mode"] == "ap",
        )

    return known_networks


async def scan_for_networks(*, rescan: bool) -> list[str]:
    """Scan for WiFi networks.

    Using sudo is necessary in order to see unknown networks.
    """
    suffix = " --rescan yes" if rescan else ""
    wifi_dicts = await run_nmcli(subcmd=f"device wifi list{suffix}", fields=["ssid"], use_sudo=True)
    # Use a dict as an intermediate representation to eliminate duplicates
    return list({data["ssid"]: None for data in wifi_dicts if data["ssid"] != "--"}.keys())


class WiFiManager:
    """Manage WiFI using nmcli commands.

    Args:
        log: A logger.
        callback: An function to call whenever the data changes, or None.
            If a function, it receives one argument: the WiFiManager.
        verbose: Log details?
    """

    def __init__(
        self, *, log: Logger, callback: Callable[[WiFiManager], Awaitable[None]] | None, verbose: bool = False
    ) -> None:
        self.log = log
        self.callback = callback
        self.verbose = verbose
        self.detected_network_ssids: list[str] = []  # A list of SSIDs
        self.known_networks: dict[str, KnownNetwork] = dict()  # a dict of SSID: KnownNetwork
        self.update_detected_task: asyncio.Future = asyncio.Future()
        self.update_detected_task.set_result(None)
        self.update_known_task: asyncio.Future = asyncio.Future()
        self.update_known_task.set_result(None)
        self.callback_task: asyncio.Future = asyncio.Future()
        self.callback_task.set_result(None)

    def start_updating_all(self, *, rescan: bool = True) -> None:
        """Start updating detected and known networks."""
        self.start_updating_detected(rescan=rescan)
        self.start_updating_known()

    def start_updating_known(self) -> None:
        """Start getting information for WiFi networks."""
        if not self.update_known_task.done():
            return
        self.known_networks = dict()
        self.update_known_task = asyncio.create_task(self._update_known())

    def start_updating_detected(self, *, rescan: bool) -> None:
        """Start scanning for WiFi networks."""
        if not self.update_detected_task.done():
            return
        self.detected_network_ssids = []
        self.update_detected_task = asyncio.create_task(self._update_detected(rescan=rescan))

    async def forget_network(self, ssid: str) -> None:
        """Forget the specified network."""
        if not self.update_known_task.done():
            await self.update_known_task
        network = self.known_networks.pop(ssid, None)
        if network is None:
            self.log.warning(
                f"WiFiManager: cannot forget network with SSID={ssid}; not found in known networks"
            )
            return
        if self.verbose:
            self.log.info(f"WiFiManager: forget network with SSID={ssid}, name={network.name}")
        await self.basic_forget_network(network.name)

    async def basic_forget_network(self, name: str) -> None:
        """Forget a network by name (not ssid).

        Do not touch self.known_networks.
        """
        await run_nmcli(subcmd=f'connection delete "{name}"', use_sudo=True)
        self.start_updating_all()
        await self.update_known_task

    async def bring_up_network(self, network: KnownNetwork) -> None:
        """Bring up the specified network."""
        self.log.info(f"WiFiManager: bring up network SSID={network.ssid!r}, name={network.name!r}")
        t0 = time.monotonic()
        await run_nmcli(subcmd=f'connection up "{network.name}"', use_sudo=True)
        dt = time.monotonic() - t0
        self.log.info(f"WiFiManager: success; network is up: SSID={network.ssid!r}, name={network.name!r}")
        if self.verbose:
            self.log.info(f"WiFiManager: it took {dt:0.1f} seconds to bring up the network.")

    async def use_network(self, ssid: str, password: str) -> None:
        """Use the specified network.

        The network may be any of:

        * Unknown: the ssid is not checked.
            This is the only option that pays attention to the password.
        * A known hotspot: the network is set to auto-connect,
            and all other known networks are set to not auto-connect.
        * A known WiFI network: the network is set to auto-connect
            and a suitable hotspot (if found) is set to auto-connect at a lower priority.
            The hotspot chosen is the first one found that already has auto-connect enabled,
            if any, else the first one found.
            All other networks are set to not auto-connect.

        Always start by bringing up the network (except if the network is unknown,
        in which case registr it first), because if it cannot be brought up
        then no other changes should be made.

        Args:
            ssid: Network SSID.
            password: Password. Ignored if the named network is known.
                Note: to change the password of a known network, you must
                first forget it, then connect to it as an unknown network.
        """
        if not self.update_known_task.done():
            await self.update_known_task
        network_to_use = self.known_networks.get(ssid)
        if network_to_use is None:
            if self.verbose:
                self.log.info(f"WiFiManager: use unknown network SSID={ssid!r}")
            # Unknown network_to_use; add it and create a preliminary known network_to_use for it
            network_to_use = KnownNetwork(
                name=ssid,
                ssid=ssid,
                active=False,
                autoconnect=False,
                is_hotspot=False,
                autoconnect_priority=0,
            )
            try:
                await run_nmcli(
                    f'device wifi connect "{ssid}" password "{password}"',
                    use_sudo=True,
                    timeout=CONNECT_TIMEOUT,
                )
            except Exception:
                # If the connection fails the remembered network is left in a weird state,
                # so ditch it.
                if self.verbose:
                    self.log.info(
                        f"WiFiManager: failed to connect to unknown network SSID={ssid} so forget it"
                    )
                await self.basic_forget_network(name=ssid)
                raise
            await self.bring_up_network(network_to_use)
            await enable_autoconnect(network_to_use)
        elif network_to_use.is_hotspot:
            if self.verbose:
                self.log.info(f"WiFiManager: use hotspot SSID={ssid!r} name={network_to_use.name!r}")
            await self.bring_up_network(network_to_use)
            for n in self.known_networks.values():
                if n.ssid == ssid:
                    await enable_autoconnect(n)
                else:
                    await disable_autoconnect(n)
        else:
            if self.verbose:
                self.log.info(f"WiFiManager: use known network SSID={ssid!r}")
            await self.bring_up_network(network_to_use)
            # Figure out which hotspot to use as a fallback:
            # * The preferred choice is the first hotspot seen that is set to autoconnect.
            # * The less favored choice is the first hotspot seen.
            # * The last choice is that there is no hotspot to fall back to.
            fallback_hotspot_name = ""
            first_hotspot_name = ""
            for n in self.known_networks.values():
                if n.is_hotspot:
                    if first_hotspot_name is None:
                        first_hotspot_name = n.name
                    if n.autoconnect:
                        fallback_hotspot_name = n.name
                        break
            if not fallback_hotspot_name:
                fallback_hotspot_name = first_hotspot_name
            for n in self.known_networks.values():
                if n.ssid == ssid:
                    await enable_autoconnect(n)
                elif n.is_hotspot and n.name == fallback_hotspot_name:
                    if self.verbose:
                        self.log.info(
                            f"WiFiManager: use hotspot SSID={n.ssid!r} name={n.name!r} as a fallback"
                        )
                    await enable_autoconnect(n)
                else:
                    await disable_autoconnect(network_to_use)
        self.start_updating_known()
        await self.update_known_task

    async def _update_known(self) -> None:
        """Update self.known_networks and call the callback.

        Ignores self.update_known_task.
        """
        if self.verbose:
            self.log.info("WiFiManager: get nmcli configuration")
        self.known_networks = await get_known_networks()
        self.call_callback_shortly()

    async def _update_detected(self, *, rescan: bool) -> None:
        """Update self.detected_network_ssids and call the callback.

        Ignores self.update_detected_task.
        """
        if self.verbose:
            self.log.info("WiFiManager: scan for networks")
        self.detected_network_ssids = await scan_for_networks(rescan=rescan)
        self.call_callback_shortly()

    def call_callback_shortly(self) -> None:
        """Schedule the callback function to be called shortly.

        Intended to allow an update method to trigger the callback
        *after* the associated update task is done.
        """
        if not self.callback_task.done():
            return
        self.callback_task = asyncio.create_task(self.call_callback())

    async def call_callback(self) -> None:
        """Call the callback function after purging known networks from detected networks."""
        self.detected_network_ssids = [
            name for name in self.detected_network_ssids if name not in self.known_networks
        ]
        if self.callback is not None:
            await self.callback(self)
