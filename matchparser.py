from datetime import datetime
import requests
from functools import lru_cache


class ValorantAPI:
    BASE_URL = "https://valorant-api.com/v1/"

    @staticmethod
    @lru_cache(maxsize=None)
    def fetch_data(endpoint):
        """Fetch data from the Valorant API and cache it."""
        url = f"{ValorantAPI.BASE_URL}{endpoint}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        raise Exception(
            f"Failed to fetch data from {url}: {response.status_code} {response.text}"
        )

    def get_armor(self, armor_id):
        json_data = self.fetch_data("gear")
        for i in json_data["data"]:
            if i["uuid"] == armor_id:
                return Armor(i)
        return None

    def get_weapon(self, weapon_id):
        json_data = self.fetch_data("weapons")
        for i in json_data["data"]:
            if i["uuid"] == weapon_id:
                return Weapon(i)
        return None

    def get_card(self, card_id):
        json_data = self.fetch_data("playercards")
        for i in json_data["data"]:
            if i["uuid"] == card_id:
                return Card(i)
        return None

    def get_title(self, title_id):
        json_data = self.fetch_data("playertitles")
        for i in json_data["data"]:
            if i["uuid"] == title_id:
                return Title(i)
        return None

    def get_formatted_team_name(self, team_id):
        team_names = {
            "Red": "Attackers",
            "Blue": "Defenders",
            "FreeForAll": "Free For All",
        }
        return team_names.get(team_id, "Unknown")

    def get_formatted_queue_name(self, queue_id):
        queue_names = {
            "unrated": "Unrated",
            "competitive": "Competitive",
            "spikerush": "Spike Rush",
            "deathmatch": "Deathmatch",
            "ggteam": "Escalation",
            "onefa": "Replication",
            "snowball": "Snowball Fight",
            "swiftplay": "Swift Play",
            "hurm": "Team Deathmatch",
            "": "Custom",
        }
        return queue_names.get(queue_id, "Unknown")

    def get_map(self, map_url):
        json_data = self.fetch_data("maps")
        for i in json_data["data"]:
            if map_url == i["mapUrl"]:
                return Map(i)
        return None

    def get_agent(self, agent_id):
        json_data = self.fetch_data("agents?isPlayableCharacter=true")
        for i in json_data["data"]:
            if i["uuid"] == agent_id:
                return Agent(i)
        return None


class Agent:
    def __init__(self, json_data):
        self.id = json_data["uuid"]
        self.name = json_data["displayName"]
        self.icon = json_data["displayIcon"]

        self.role = json_data["role"]["displayName"]
        self.description = json_data["description"]
        self.abilities = self.Abilities(json_data["abilities"])

    class Abilities:
        def __init__(self, json_data):
            self.abilities = [self.Ability(ability_data) for ability_data in json_data]

        def __iter__(self):
            return iter(self.abilities)

        def __len__(self):
            return len(self.abilities)

        def __getitem__(self, index):
            return self.abilities[index]

        class Ability:
            def __init__(self, json_data):
                self.slot = json_data["slot"]
                self.name = json_data["displayName"]
                self.description = json_data["description"]
                self.icon = json_data["displayIcon"]


class Map:
    def __init__(self, json_data):
        self.id = json_data["uuid"]
        self.url = json_data["mapUrl"]
        self.name = json_data["displayName"]
        self.splash = json_data["splash"]
        self.icon = json_data["displayIcon"]

        self.tactical_description = json_data["tacticalDescription"]
        self.coordinates = json_data["coordinates"]


class Armor:
    def __init__(self, json_data):
        self.id = json_data["uuid"]
        self.name = json_data["displayName"]
        self.icon = json_data["displayIcon"]

        self.cost = json_data["shopData"]["cost"]
        self.damage_reduction = json_data["details"][1]["value"]


class Weapon:
    def __init__(self, json_data):
        self.id = json_data["uuid"]
        self.name = json_data["displayName"]
        self.icon = json_data["displayIcon"]

        self.cost = json_data["shopData"]["cost"]
        self.category = json_data["shopData"]["category"]


class Card:
    def __init__(self, json_data):
        self.id = json_data["uuid"]
        self.name = json_data["displayName"]
        self.icon = json_data["displayIcon"]

        self.small_image = json_data["smallArt"]
        self.wide_image = json_data["wideArt"]
        self.large_image = json_data["largeArt"]


class Title:
    def __init__(self, json_data):
        self.id = json_data["uuid"]
        self.text = json_data["titleText"]


class Match:
    def __init__(self, json_data):
        self.id = json_data["matchInfo"]["matchId"]

        self.map_url = json_data["matchInfo"]["mapId"]
        self.map = ValorantAPI().get_map(self.map_url)

        self.mode_raw = json_data["matchInfo"]["queueId"]
        self.mode = ValorantAPI().get_formatted_queue_name(self.mode_raw)
        self.is_ranked = json_data["matchInfo"]["isRanked"]

        self.start_time_raw = json_data["matchInfo"]["gameStartMillis"]
        self.start_time = datetime.fromtimestamp(self.start_time_raw // 1000)
        self.end_time_raw = (
            self.start_time_raw + json_data["matchInfo"]["gameLengthMillis"]
        )
        self.end_time = datetime.fromtimestamp(self.end_time_raw // 1000)

        self.teams = Teams(json_data["teams"])
        self.winner = None
        for team in self.teams:
            if team.won:
                self.winner = team
                break

        self.players = Players(json_data["players"], self.teams)
        self.rounds = Rounds(json_data["roundResults"], self.players, self.teams)


class Teams:
    def __init__(self, json_data):
        self.teams = [Team(team_data) for team_data in json_data]

    def get_team_by_id(self, team_id):
        if team_id is None:
            return None

        for team in self.teams:
            if team.id == team_id:
                return team
        return None

    def __iter__(self):
        return iter(self.teams)

    def __len__(self):
        return len(self.teams)

    def __getitem__(self, index):
        return self.teams[index]


class Team:
    def __init__(self, json_data):
        self.id = json_data["teamId"]

        self.name = ValorantAPI().get_formatted_team_name(self.id)
        self.score = json_data["numPoints"]
        self.won = json_data["won"]


class Players:
    def __init__(self, json_data, teams: Teams):
        self.players = [Player(player_data, teams) for player_data in json_data]
        self.players.sort(key=lambda x: x.overall_stats.score, reverse=True)

    def get_player_by_id(self, player_id):
        if player_id is None:
            return None

        for player in self.players:
            if player.id == player_id:
                return player
        return None

    def __iter__(self):
        return iter(self.players)

    def __len__(self):
        return len(self.players)

    def __getitem__(self, index):
        return self.players[index]


class Player:
    def __init__(self, json_data, teams: Teams):
        self.id = json_data["puuid"]
        self.name = json_data["gameName"]
        self.tag = json_data["tagLine"]
        self.display_name = f"{self.name}#{self.tag}"

        self.card_id = json_data["playerCard"]
        self.card = ValorantAPI().get_card(self.card_id)
        self.title_id = json_data["playerTitle"]
        self.title = ValorantAPI().get_title(self.title_id)
        self.level = json_data["accountLevel"]

        self.party_id = json_data.get("partyId")
        self.tier = json_data.get("competitiveTier")

        self.is_observer = json_data.get("isObserver")
        self.team_id = json_data.get("teamId")
        self.team = teams.get_team_by_id(self.team_id)

        self.character_id = json_data["characterId"]
        self.character = ValorantAPI().get_agent(self.character_id)

        self.overall_stats = self.Stats(json_data.get("stats", {}))
        self.ability_stats = self.AbilityStats(
            json_data.get("stats", {}).get("abilityCasts", {}), self.character
        )

    class Stats:
        def __init__(self, json_data):
            self.score = json_data.get("score", 0)
            self.kills = json_data.get("kills", 0)
            self.deaths = json_data.get("deaths", 0)
            self.assists = json_data.get("assists", 0)

        def __str__(self):
            return (
                f"Score: {self.score}, K/D/A: {self.kills}/{self.deaths}/{self.assists}"
            )

    class AbilityStats:
        def __init__(self, json_data, character: Agent):
            self.character = character
            if json_data is None:
                self.grenade_casts = 0
                self.ability1_casts = 0
                self.ability2_casts = 0
                self.ultimate_casts = 0
                return

            self.grenade_casts = json_data.get("grenadeCasts", 0)
            self.ability1_casts = json_data.get("ability1Casts", 0)
            self.ability2_casts = json_data.get("ability2Casts", 0)
            self.ultimate_casts = json_data.get("ultimateCasts", 0)

        def __str__(self):
            ability_summary = ""
            for ability in self.character.abilities:
                if ability.slot.lower() == "passive":
                    continue

                ability_summary += f"{ability.name}: {getattr(self, ability.slot.lower() + '_casts')} \n"
            return ability_summary


class Rounds:
    def __init__(self, json_data, players: Players, teams: Teams):
        self.rounds = [Round(round_data, players, teams) for round_data in json_data]

    def __iter__(self):
        return iter(self.rounds)

    def __len__(self):
        return len(self.rounds)

    def __getitem__(self, index):
        return self.rounds[index]


class Coordinate:
    def __init__(self, json_data):
        self.x = json_data["x"]
        self.y = json_data["y"]


class PlayerStats:
    def __init__(self, json_data, players: Players):
        self.player_stats = [
            self.PlayerStat(player_data, players) for player_data in json_data
        ]

    def get_player_by_id(self, player_id):
        if player_id is None:
            return None

        for player in self.player_stats:
            if player.id == player_id:
                return player
        return None

    def __iter__(self):
        return iter(self.player_stats)

    def __len__(self):
        return len(self.player_stats)

    def __getitem__(self, index):
        return self.player_stats[index]

    class PlayerStat:
        def __init__(self, json_data, players: Players):
            self.id = json_data["puuid"]
            self.player = players.get_player_by_id(self.id)
            self.score = json_data["score"]

            self.economy = self.Economy(json_data["economy"])

            self.killed_players = self.KilledPlayers(json_data["kills"], players)
            self.damaged_players = self.DamagedPlayers(json_data["damage"], players)

        class Economy:
            def __init__(self, json_data):
                self.spent = json_data["spent"]
                self.remaining = json_data["remaining"]

                self.weapon_id = json_data["weapon"]
                self.weapon = ValorantAPI().get_weapon(self.weapon_id)
                self.armor_id = json_data["armor"]
                self.armor = ValorantAPI().get_armor(self.armor_id)

        class KilledPlayers:
            def __init__(self, json_data, players: Players):
                self.killed_players = [
                    self.KilledPlayer(data, players) for data in json_data
                ]

            def __iter__(self):
                return iter(self.killed_players)

            def __len__(self):
                return len(self.killed_players)

            def __getitem__(self, index):
                return self.killed_players[index]

            class KilledPlayer:
                def __init__(self, json_data, players: Players):
                    self.victim_id = json_data["victim"]
                    self.victim = players.get_player_by_id(self.victim_id)
                    self.location = Coordinate(json_data["victimLocation"])

                    self.assistants = [
                        players.get_player_by_id(player_id)
                        for player_id in json_data["assistants"]
                    ]
                    self.weapon_used_id = json_data["finishingDamage"]["damageItem"]
                    self.weapon_used = ValorantAPI().get_weapon(self.weapon_used_id)

        class DamagedPlayers:
            def __init__(self, json_data, players: Players):
                self.damaged_players = [
                    self.DamagedPlayer(data, players) for data in json_data
                ]
                self.total_damage = sum(
                    [player.damage for player in self.damaged_players]
                )

            def __iter__(self):
                return iter(self.damaged_players)

            def __len__(self):
                return len(self.damaged_players)

            def __getitem__(self, index):
                return self.damaged_players[index]

            class DamagedPlayer:
                def __init__(self, json_data, players: Players):
                    self.receiver_id = json_data["receiver"]
                    self.receiver = players.get_player_by_id(self.receiver_id)

                    self.damage = json_data["damage"]
                    self.headshots = json_data["headshots"]
                    self.bodyshots = json_data["bodyshots"]
                    self.legshots = json_data["legshots"]


class Round:
    def __init__(self, json_data, players: Players, teams: Teams):
        self.serial = json_data["roundNum"]
        self.winner = teams.get_team_by_id(json_data["winningTeam"])

        self.spike_info = self.Spike(json_data, players)
        self.player_stats = PlayerStats(json_data["playerStats"], players)

        self.result_code = json_data["roundResultCode"]

    class Spike:
        def __init__(self, json_data, players: Players):
            self.planter = players.get_player_by_id(json_data["bombPlanter"])
            if self.planter:
                self.site = json_data["plantSite"]

                self.plant_time = json_data["plantRoundTime"]
                self.plant_location = Coordinate(json_data["plantLocation"])

            self.defuser = players.get_player_by_id(json_data["bombDefuser"])
            if self.defuser:
                self.defuse_time = json_data["defuseRoundTime"]
                self.defuse_location = Coordinate(json_data["defuseLocation"])
