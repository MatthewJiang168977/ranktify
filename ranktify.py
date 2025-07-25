import discord
from collections import defaultdict

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queues = defaultdict(list)
        self.player_skill = defaultdict(lambda: {
            "rank": None,
            "division": None,
            "games_played": 0,
            "mmr": 1000  # Default MMR
        })
        
      # Supported ranking tiers
        self.tiers = [
            "IRON", "BRONZE", "SILVER", "GOLD",
            "PLATINUM", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"
        ]

    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))
        await self.change_presence(activity=discord.Game(name="Type $help for commands"))

    async def on_message(self, message): 
        if message.author == self.user:
            return 
        # if message.content.startswith("$hello"):
        #     await message.channel.send("Hello World!") for testing
        content = message.content.lower()
        args = content.split()

        # help command
        if content.startswith("$help"):
            embed = discord.Embed(title="Universal Game Balancer", color=0x00ff00)
            embed.add_field(name="$setrank [tier] [division]", 
                         value="Set competitive rank (e.g., $setrank gold 3)", inline=False)
            embed.add_field(name="$setgames [number]", 
                         value="Set casual experience (e.g., $setgames 50)", inline=False)
            embed.add_field(name="$join", value="Join queue", inline=False)
            embed.add_field(name="$balance", value="Create balanced teams", inline=False)
            embed.add_field(name="$myskill", value="Check your skill rating", inline=False)
            await message.channel.send(embed=embed)

        if content.startswith("$setrank"):
            if len(args) < 3:
                await message.channel.send("Usage: $setrank [tier] [division]\nExample: $setrank gold 3")
                return

            try:
                tier = args[1].upper()
                division = int(args[2])
                
                if tier not in self.tiers:
                    await message.channel.send(f"Invalid tier. Available: {', '.join(self.tiers)}")
                    return
                if not 1 <= division <= 4:
                    await message.channel.send("Division must be 1-4 (1=highest, 4=lowest)")
                    return

                # Calculate MMR based on rank (higher tiers/divisions = higher MMR)
                tier_index = self.tiers.index(tier)
                mmr = 1000 + (tier_index * 200) + ((4 - division) * 50)
                
                self.player_skill[message.author.id] = {
                    "rank": tier,
                    "division": division,
                    "games_played": max(self.player_skill[message.author.id]["games_played"], 10),
                    "mmr": mmr
                }
                
                await message.channel.send(f"Set rank to {tier} {division} (MMR: {mmr})")
            except ValueError:
                await message.channel.send("Division must be a number (1-4)")

        if content.startswith("$setgames"):
            if len(args) < 2:
                await message.channel.send("Usage: $setgames [number]\nExample: $setgames 50")
                return

            try:
                games = int(args[1])
                if games < 0:
                    await message.channel.send("Games played cannot be negative")
                    return

                # Calculate MMR based on games played (capped at 100 games for balance)
                effective_games = min(games, 1000)
                mmr = 800 + (effective_games * 4)  
                
                self.player_skill[message.author.id] = {
                    "rank": None,
                    "division": None,
                    "games_played": games,
                    "mmr": mmr
                }
                
                await message.channel.send(f"Recorded {games} games played (MMR: {mmr})")
            except ValueError:
                await message.channel.send("Games played must be a number")

        if content.startswith("$join"):
            if message.author.id not in self.queues[message.guild.id]:
                self.queues[message.guild.id].append(message.author.id)
                await message.channel.send(f"{message.author.mention} joined queue! ({len(self.queues[message.guild.id])} players)")
            else:
                await message.channel.send("You're already in queue!")

        if content.startswith("$balance"):
            queue = self.queues[message.guild.id]
            if len(queue) < 2:
                await message.channel.send("Need at least 2 players!")
                return

            n = len(queue)
            best_diff = float('inf')
            best_split = None

            # Recursive combinations generator 
            def generate_combinations(players, size):
                result = []
                def backtrack(start, path):
                    if len(path) == size:
                        result.append(path[:])  
                        return
                    for i in range(start, len(players)):
                        path.append(players[i])
                        backtrack(i + 1, path)
                        path.pop()
                backtrack(0, [])
                return result

            # Try all non-trivial team splits
            for size in range(1, n):
                combinations = generate_combinations(queue, size)
                for team1 in combinations:
                    team2 = [p for p in queue if p not in team1]
                    team1_total = sum(self.player_skill[p]["mmr"] for p in team1)
                    team2_total = sum(self.player_skill[p]["mmr"] for p in team2)
                    diff = abs(team1_total - team2_total)
                    if diff < best_diff:
                        best_diff = diff
                        best_split = (team1, team2)

            team1, team2 = best_split
            avg1 = sum(self.player_skill[p]["mmr"] for p in team1) / len(team1)
            avg2 = sum(self.player_skill[p]["mmr"] for p in team2) / len(team2)

            def win_prob(a, b):
                return 1 / (1 + 10 ** ((b - a) / 400))

            team1_win_prob = round(win_prob(avg1, avg2) * 100)
            team2_win_prob = 100 - team1_win_prob

            embed = discord.Embed(
                title="⚔️ Balanced Teams",
                color=0x3498db,
                description=f"**{len(queue)} players** | MMR difference: **{abs(avg1 - avg2):.0f}**"
            )

            embed.add_field(
                name=f"🔵 Team 1 (Avg: {int(avg1)} MMR) • {team1_win_prob}% win",
                value=self._format_team(team1),
                inline=True
            )

            embed.add_field(
                name=f"🔴 Team 2 (Avg: {int(avg2)} MMR) • {team2_win_prob}% win",
                value=self._format_team(team2),
                inline=True
            )

            await message.channel.send(embed=embed)
            self.queues[message.guild.id].clear()

        if content.startswith("$myskill"):
            skill = self.player_skill[message.author.id]
            if skill["rank"]:
                await message.channel.send(
                    f"Your skill: {skill['rank']} {skill['division']} "
                    f"(MMR: {skill['mmr']}, Games: {skill['games_played']})"
                )
            else:
                await message.channel.send(
                    f"Your skill: {skill['games_played']} games played "
                    f"(MMR: {skill['mmr']})"
                )

    def _format_team(self, players):
        return "\n".join(
            f"<@{p}>: " + (
                f"{self.player_skill[p]['rank']} {self.player_skill[p]['division']}" 
                if self.player_skill[p]["rank"] else 
                f"{self.player_skill[p]['games_played']} games"
            )
            for p in players
        )


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = MyClient(intents=intents)
client.run("insert token here")

hi