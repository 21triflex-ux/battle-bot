import discord
from discord.ext import commands
from discord.ui import View, button
import random
from dotenv import load_dotenv
import os
import webserver

# ================== SETUP ==================
load_dotenv()
token = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

# ================== DATA ==================
START_CP = 1000
stats = {}        # Tracks user CP, wins, losses, earned
active_battles = {}  # Tracks ongoing battles per user

def get_user(user_id):
    if user_id not in stats:
        stats[user_id] = {"cp": START_CP, "wins": 0, "losses": 0, "earned": 0}
    return stats[user_id]

# ================== ENTITIES ==================
ENTITIES = [
    {"name": "Pidgey", "hp": 20, "atk": (2,5), "rarity": 50, "reward": 50},
    {"name": "Rattata", "hp": 25, "atk": (3,6), "rarity": 30, "reward": 75},
    {"name": "Ekans", "hp": 35, "atk": (4,8), "rarity": 15, "reward": 150},
    {"name": "Dragonite", "hp": 60, "atk": (8,15), "rarity": 5, "reward": 500},
]

def choose_entity():
    roll = random.randint(1,100)
    cumulative = 0
    for ent in ENTITIES:
        cumulative += ent["rarity"]
        if roll <= cumulative:
            return ent.copy()
    return ENTITIES[0].copy()  # fallback

# ================== BATTLE VIEW ==================
class BattleView(View):
    def __init__(self, ctx, entity):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.player_id = ctx.author.id
        self.entity = entity
        self.player_hp = 50
        self.entity_hp = entity["hp"]
        self.special_used = False
        self.done = False

    async def interaction_check(self, interaction):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("❌ Not your battle!", ephemeral=True)
            return False
        return True

    def get_embed(self):
        embed = discord.Embed(title=f"⚔️ Battle vs {self.entity['name']}", color=0x00ff00)
        embed.add_field(name=self.ctx.author.name, value=f"HP: {self.player_hp}/50", inline=True)
        embed.add_field(name=self.entity['name'], value=f"HP: {self.entity_hp}/{self.entity['hp']}", inline=True)
        return embed

    async def end_battle(self, won):
        self.done = True
        self.clear_items()
        user = get_user(self.player_id)
        if won:
            cp_reward = self.entity["reward"]
            user["cp"] += cp_reward
            user["wins"] += 1
            user["earned"] += cp_reward
            result_text = f"🎉 You defeated {self.entity['name']}! Earned {cp_reward} CP"
        else:
            user["losses"] += 1
            result_text = f"💥 You lost to {self.entity['name']}! Better luck next time."
        embed = self.get_embed()
        embed.set_footer(text=result_text)
        await self.ctx.send(embed=embed)
        del active_battles[self.player_id]

    async def entity_attack(self):
        dmg = random.randint(*self.entity["atk"])
        self.player_hp -= dmg
        if self.player_hp <= 0:
            self.player_hp = 0
            await self.end_battle(False)

    @button(label="Attack", style=discord.ButtonStyle.green)
    async def attack(self, interaction, button):
        dmg = random.randint(5,10)
        self.entity_hp -= dmg
        if self.entity_hp <= 0:
            self.entity_hp = 0
            await self.end_battle(True)
        else:
            await self.entity_attack()
            if not self.done:
                await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @button(label="Special", style=discord.ButtonStyle.blurple)
    async def special(self, interaction, button):
        if self.special_used:
            await interaction.response.send_message("Special already used!", ephemeral=True)
            return
        self.special_used = True
        dmg = random.randint(10,20)
        self.entity_hp -= dmg
        if self.entity_hp <= 0:
            self.entity_hp = 0
            await self.end_battle(True)
        else:
            await self.entity_attack()
            if not self.done:
                await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @button(label="Heal", style=discord.ButtonStyle.green)
    async def heal(self, interaction, button):
        heal_amount = random.randint(5,15)
        self.player_hp += heal_amount
        if self.player_hp > 50:
            self.player_hp = 50
        await self.entity_attack()
        if not self.done:
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @button(label="Run", style=discord.ButtonStyle.red)
    async def run(self, interaction, button):
        self.done = True
        self.clear_items()
        await interaction.response.edit_message(content="🏃 You ran away!", embed=None, view=None)
        del active_battles[self.player_id]

# ================== COMMANDS ==================
@bot.command()
async def battle(ctx):
    if ctx.author.id in active_battles:
        await ctx.send("❌ You already have an active battle!")
        return
    entity = choose_entity()
    view = BattleView(ctx, entity)
    active_battles[ctx.author.id] = view
    await ctx.send(embed=view.get_embed(), view=view)

@bot.command()
async def balance(ctx):
    user = get_user(ctx.author.id)
    await ctx.send(f"💰 You have {user['cp']} CP")

@bot.command()
async def leaderboard(ctx):
    if not stats:
        await ctx.send("No data yet.")
        return
    sorted_users = sorted(stats.items(), key=lambda x: x[1]["cp"], reverse=True)
    embed = discord.Embed(title="🏆 Leaderboard", color=0xFFD700)
    for i, (uid, data) in enumerate(sorted_users[:10], start=1):
        user_obj = await bot.fetch_user(uid)
        total = data["wins"] + data["losses"]
        winrate = (data["wins"]/total*100) if total>0 else 0
        embed.add_field(
            name=f"#{i} {user_obj.name}",
            value=f"💰 CP: {data['cp']}\n🏆 Wins: {data['wins']}\n❌ Losses: {data['losses']}\n💸 Total Earned: {data['earned']}\n📊 Win %: {winrate:.1f}%",
            inline=False
        )
    await ctx.send(embed=embed)

# ================== RUN ==================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

if __name__ == "__main__":
    webserver.keep_alive()
    bot.run(token)