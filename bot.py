import logging
import os
import re
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

from action_network import check_membership
from database import add_member, deactivate_member, get_member, get_member_by_email, init_db
from email_verification import generate_and_send, has_pending, verify_code
from sync import run_sync

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID"))
MEMBER_ROLE_NAME = "DSA Member"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


def get_member_role(guild: discord.Guild) -> discord.Role | None:
    return discord.utils.get(guild.roles, name=MEMBER_ROLE_NAME)


@client.event
async def on_ready():
    init_db()
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    weekly_sync.start()
    log.info(f"Logged in as {client.user} — ready.")


@tree.command(
    name="verify",
    description="Verify your DSA membership to receive the DSA Member role.",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.describe(email="The email address associated with your DSA membership")
async def verify(interaction: discord.Interaction, email: str):
    await interaction.response.defer(ephemeral=True)
    discord_id = str(interaction.user.id)

    if not EMAIL_RE.match(email):
        await interaction.followup.send(
            "That doesn't look like a valid email address. Please try again.",
            ephemeral=True,
        )
        return

    existing = get_member(discord_id)
    if existing and existing["is_active"]:
        await interaction.followup.send(
            "You're already verified as a DSA member!", ephemeral=True
        )
        return

    existing_by_email = get_member_by_email(email)
    if existing_by_email and existing_by_email["discord_id"] != discord_id:
        await interaction.followup.send(
            "That email is already linked to another Discord account. "
            "If you think this is a mistake, please reach out to an organizer.",
            ephemeral=True,
        )
        return

    if has_pending(discord_id):
        await interaction.followup.send(
            "A verification code was already sent to your email. "
            "Use `/confirm` to enter it, or wait 10 minutes to request a new one.",
            ephemeral=True,
        )
        return

    try:
        generate_and_send(discord_id, email)
    except Exception as e:
        log.error(f"Failed to send verification email to discord_id={discord_id}: {e}")
        await interaction.followup.send(
            "Failed to send the verification email. Please try again or contact an organizer.",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        f"A 6-digit verification code has been sent to **{email}**.\n"
        "Use `/confirm` with that code to complete verification. It expires in 10 minutes.",
        ephemeral=True,
    )


@tree.command(
    name="confirm",
    description="Enter the verification code sent to your email.",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.describe(code="The 6-digit code from your verification email")
async def confirm(interaction: discord.Interaction, code: str):
    await interaction.response.defer(ephemeral=True)
    discord_id = str(interaction.user.id)

    valid, email = verify_code(discord_id, code)
    if not valid:
        await interaction.followup.send(
            "That code is invalid or has expired. Use `/verify` to request a new one.",
            ephemeral=True,
        )
        return

    try:
        is_member = check_membership(email)
    except Exception as e:
        log.error(f"Action Network API error for discord_id={discord_id}: {e}")
        await interaction.followup.send(
            "Could not check your membership status right now. Please try again later.",
            ephemeral=True,
        )
        return

    if not is_member:
        await interaction.followup.send(
            "Your email was verified, but your DSA membership doesn't appear to be active. "
            "If you think this is a mistake, please reach out to an organizer.",
            ephemeral=True,
        )
        return

    guild = client.get_guild(GUILD_ID)
    role = get_member_role(guild)
    guild_member = guild.get_member(interaction.user.id)

    if role and guild_member:
        await guild_member.add_roles(role, reason="Verified DSA member via /verify")

    add_member(discord_id, email)

    await interaction.followup.send(
        "Verified! You've been given the **DSA Member** role. Welcome, comrade!",
        ephemeral=True,
    )


@tree.command(
    name="lookup",
    description="Look up the DSA email address linked to a Discord member. (Mods only)",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.describe(member="The Discord member to look up")
@app_commands.checks.has_role("Moderator")
async def lookup(interaction: discord.Interaction, member: discord.Member):
    row = get_member(str(member.id))
    if not row:
        await interaction.response.send_message(
            f"{member.display_name} has no verified membership on record.",
            ephemeral=True,
        )
        return

    status = "active" if row["is_active"] else "inactive (membership lapsed)"
    await interaction.response.send_message(
        f"**{member.display_name}** — `{row['email']}` ({status})",
        ephemeral=True,
    )


@tree.command(
    name="unlink",
    description="Unlink a Discord member's DSA membership record so they can re-verify. (Mods only)",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.describe(member="The Discord member to unlink")
@app_commands.checks.has_role("Moderator")
async def unlink(interaction: discord.Interaction, member: discord.Member):
    row = get_member(str(member.id))
    if not row or not row["is_active"]:
        await interaction.response.send_message(
            f"{member.display_name} has no active membership record to unlink.",
            ephemeral=True,
        )
        return

    role = get_member_role(interaction.guild)
    if role and role in member.roles:
        await member.remove_roles(role, reason=f"Membership unlinked by moderator {interaction.user}")

    deactivate_member(str(member.id))

    try:
        await member.send(
            "Your DSA membership verification in the Boston DSA Discord has been unlinked by a moderator. "
            "You can re-verify at any time using `/verify`."
        )
    except discord.Forbidden:
        pass  # User has DMs disabled — not a blocker

    await interaction.response.send_message(
        f"Unlinked **{member.display_name}**. They can now re-verify with a new account.",
        ephemeral=True,
    )


@unlink.error
async def unlink_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingRole):
        await interaction.response.send_message(
            "You don't have permission to use this command.", ephemeral=True
        )


@lookup.error
async def lookup_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingRole):
        await interaction.response.send_message(
            "You don't have permission to use this command.", ephemeral=True
        )


@tasks.loop(hours=24)
async def weekly_sync():
    # Run every Saturday at noon UTC (gives National's Friday data update time to propagate)
    if datetime.now(timezone.utc).weekday() != 5:  # 5 = Saturday
        return
    guild = client.get_guild(GUILD_ID)
    role = get_member_role(guild)
    if guild and role:
        await run_sync(guild, role)
    else:
        log.warning("Weekly sync skipped — could not find guild or DSA Member role.")


@weekly_sync.before_loop
async def before_weekly_sync():
    await client.wait_until_ready()


client.run(DISCORD_TOKEN)
