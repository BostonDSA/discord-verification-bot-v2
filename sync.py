import logging

import discord

from action_network import check_membership
from database import deactivate_member, get_all_active_members, update_last_checked

log = logging.getLogger(__name__)

LAPSE_MESSAGE = (
    "Hi! Your Boston DSA membership no longer appears to be active, "
    "so your **DSA Member** role in the Boston DSA Discord has been removed.\n\n"
    "To rejoin as a DSA member, go to https://dsausa.org/join.\n\n"
    "If you think this is a mistake, please re-verify with `/verify` or reach out to an organizer."
)


async def run_sync(guild: discord.Guild, member_role: discord.Role, lapsed_role: discord.Role | None = None):
    """
    Checks all verified members against Action Network.
    Removes the DSA Member role, assigns the Lapsed Member role, and DMs anyone whose membership has lapsed.
    """
    members = get_all_active_members()
    log.info(f"Weekly sync started — checking {len(members)} members.")

    removed = 0
    errors = 0

    for row in members:
        discord_id = row["discord_id"]
        email = row["email"]

        try:
            still_member = check_membership(email)
            update_last_checked(discord_id)
        except Exception as e:
            log.error(f"AN API error for {discord_id} ({email}): {e}")
            errors += 1
            continue

        if still_member:
            continue

        # Membership lapsed — remove role and notify
        guild_member = guild.get_member(int(discord_id))
        if guild_member:
            try:
                roles_to_remove = [r for r in [member_role] if r in guild_member.roles]
                roles_to_add = [r for r in [lapsed_role] if r and r not in guild_member.roles]
                if roles_to_remove:
                    await guild_member.remove_roles(*roles_to_remove, reason="Membership lapsed (weekly sync)")
                if roles_to_add:
                    await guild_member.add_roles(*roles_to_add, reason="Membership lapsed (weekly sync)")
            except discord.Forbidden:
                log.warning(f"Missing permissions to update roles for {discord_id}")

            try:
                await guild_member.send(LAPSE_MESSAGE)
            except discord.Forbidden:
                log.warning(f"Could not DM {discord_id} — DMs may be disabled")

        deactivate_member(discord_id)
        removed += 1
        log.info(f"Removed DSA Member role from {discord_id} ({email})")

    log.info(f"Weekly sync complete — removed: {removed}, errors: {errors}")
    return removed, errors
