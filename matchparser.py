from datetime import datetime


class Agent:
    def __init__(self, name):
        self.name = name
        self.abilities = []

    def __str__(self):
        return self.name + " with abilities " + str(self.abilities)

    def __repr__(self):
        return self.name + " with abilities " + str(self.abilities)


class Ability:
    def __init__(self, name, cost):
        self.name = name
        self.cost = cost

    def __str__(self):
        return self.name + " with price $" + str(self.cost)

    def __repr__(self):
        return self.name + " with price $" + str(self.cost)


class Weapon:
    def __init__(self, name, cost):
        self.name = name
        self.cost = cost

    def __str__(self):
        return self.name + " with price $" + str(self.cost)

    def __repr__(self):
        return self.name + " with price $" + str(self.cost)


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

    def get_armor_name(self, armorId):
        return armorId

    def get_weapon_name(self, weaponId):
        datajson = self.fetch_data("weapons")
        for i in datajson["data"]:
            if i["uuid"] == weaponId:
                return i["displayName"]
        return None

    def get_card_icon(self, cardId):
        datajson = self.fetch_data("playercards")
        for i in datajson["data"]:
            if i["uuid"] == cardId:
                return i["displayIcon"]
        return None

    def get_formatted_queue_name(self, queueId):
        validQueueNames = {
            "competitive": "Competitive",
            "custom": "Custom",
            "": "Custom",
            "deathmatch": "Deathmatch",
            "ggteam": "Escalation",
            "newmap": "Pearl",
            "onefa": "Replication",
            "snowball": "Snowball Fight",
            "spikerush": "SpikeRush",
            "unrated": "Unrated",
            "swiftplay": "Swift Play",
        }
        return validQueueNames.get(queueId, "Unknown")

    def get_map_name_from_url(self, mapurl):
        datajson = self.fetch_data("maps")
        for i in datajson["data"]:
            if mapurl == i["mapUrl"]:
                return i["displayName"]
        return None

    def get_map_thumbnail(self, mapname):
        datajson = self.fetch_data("maps")
        for i in datajson["data"]:
            if mapname == i["displayName"]:
                return i["splash"]
        return None

    def get_agent_from_id(self, agentId):
        datajson = self.fetch_data("agents")
        for i in datajson["data"]:
            if i["uuid"] == agentId:
                return i["displayName"]
        return None

    def get_agent_abilities(self, agentname):
        datajson = self.fetch_data("agents")
        for i in datajson["data"]:
            if agentname == i["displayName"]:
                abilities = i["abilities"]
                return {a["slot"]: a["displayName"] for a in abilities}
        return None

    def get_weapon_prices(self):
        datajson = self.fetch_data("weapons")
        weapons = []
        for i in datajson["data"]:
            if i["displayName"] != "Melee" and i["shopData"]["cost"] > 0:
                weapons.append(
                    {"name": i["displayName"], "cost": i["shopData"]["cost"]}
                )
        return weapons

    def get_weapon_price(self, weaponname):
        datajson = self.fetch_data("weapons")
        for i in datajson["data"]:
            if i["displayName"] == weaponname:
                return {"name": i["displayName"], "cost": i["shopData"]["cost"]}
        return None

    def get_possible_weapons(self, pricelimit):
        weapons = self.get_weapon_prices()
        return [w for w in weapons if w["cost"] <= pricelimit]


class Matches:
    def __init__(self):
        self.matchlist = []

    def add_match(self, match):
        self.matchlist.append(match)

    def __str__(self):
        matchnames = ""
        for match in self.matchlist:
            matchnames += match.__str__() + ","
        return ".".join(matchnames.rsplit(",", 1))


class Match:
    def __init__(self, mdict):
        self.raw = mdict
        mapName = ValorantAPI().get_map_name_from_url(mdict["matchInfo"]["mapId"])
        self.name = mapName
        self.thumbnail = ValorantAPI().get_map_thumbnail(self.name)
        self.id = mdict["matchInfo"]["matchId"]
        self.mode = ValorantAPI().get_formatted_queue_name(
            mdict["matchInfo"]["queueId"]
        )
        self.start_raw = mdict["matchInfo"]["gameStartMillis"]
        self.start = datetime.fromtimestamp(self.start_raw // 1000)
        self.rounds = Rounds(mdict, self.name, self)
        self.winningteam = FormatData().get_rounds_won(self.rounds.roundlist)
        self.players = Players(mdict["players"])

    def __str__(self):
        return f"{self.mode} on {self.name} resulting in {FormatData().get_rounds_stats(self.rounds.roundlist)}."


class Players:
    def __init__(self, mdict):
        self.playerlist = []
        self.raw = mdict
        for playerm in self.raw:
            playerdata = Player(playerm)
            self.playerlist.append(playerdata)

    def __str__(self):
        playernames = ""
        for player in self.playerlist:
            playernames += player.display_name + f"({player.currenttier}),"
        return ".".join(playernames.rsplit(",", 1))


class Player:
    def __init__(self, mdict):
        self.raw = mdict
        self.id = mdict["puuid"]
        self.name = mdict["gameName"]
        self.tag = mdict["tagLine"]
        self.display_name = f"{self.name}#{self.tag}"
        self.currenttier = mdict["competitiveTier"]
        self.character = self.Character(mdict)
        self.team_id = mdict.get("team")
        self.party_id = mdict.get("party_id")
        self.playtime = self.MatchTime(mdict["stats"]["playtimeMillis"])
        self.cardId = mdict["playerCard"]
        self.icon = ValorantAPI().get_card_icon(self.cardId)
        self.iconId = mdict["playerTitle"]
        self.stats = self.Stats(mdict["stats"])
        self.ability_stats = self.AbilityStats(mdict["stats"]["abilityCasts"])

    class AbilityStats:
        def __init__(self, mdict):
            self.raw = mdict
            try:
                self.c_casts = mdict["grenadeCasts"]
            except Exception as ex:
                self.c_casts = 0
            try:
                self.q_casts = mdict["ability1Casts"]
            except Exception as ex:
                self.q_casts = 0
            try:
                self.e_casts = mdict["ability2Casts"]
            except Exception as ex:
                self.e_casts = 0
            try:
                self.ultimate_casts = mdict["ultimateCasts"]
            except Exception as ex:
                self.ultimate_casts = 0
            try:
                self.x_casts = mdict["ultimateCasts"]
            except Exception as ex:
                self.x_casts = 0

    class Stats:
        def __init__(self, mdict):
            self.raw = mdict
            self.score = mdict["score"]
            self.kills = mdict["kills"]
            self.deaths = mdict["deaths"]
            self.assists = mdict["assists"]

    class Character:
        def __init__(self, mdict):
            self.raw = mdict
            self.id = mdict["characterId"]
            self.name = ValorantAPI().get_agent_from_id(self.id)
            # self.icon = mdict["assets"]["agent"]["small"]
            # self.full_icon = mdict["assets"]["agent"]["full"]
            # self.kill_icon = mdict["assets"]["agent"]["killfeed"]

    class MatchTime:
        def __init__(self, mdict):
            self.raw = mdict
            try:
                self.minutes = mdict["minutes"]
            except:
                pass
            try:
                self.seconds = mdict["seconds"]
            except:
                pass
            try:
                self.milliseconds = mdict["milliseconds"]
            except:
                pass


class Rounds:
    def __init__(self, mdict, mapname=None, match=None):
        self.roundlist = []
        self.match = match
        try:
            self.mapname = mapname
        except:
            pass
        self.raw = mdict
        self.list = mdict["roundResults"]
        for roundm in self.list:
            rounddata = Round(roundm, mapname)
            self.roundlist.append(rounddata)


class Round:
    def __init__(self, mdict, mapname=None):
        self.raw = mdict
        self.winnerteam = self.WinnerTeam(mdict)
        self.spike = self.SpikeInfo(mdict)
        self.stats = self.RoundStats(mdict)
        self.mapname = mapname

    class RoundStats:
        def __init__(self, mdict):
            self.raw = mdict
            self.playerlist = []
            self.blueeco = 0
            self.redeco = 0
            for player in mdict["playerStats"]:
                playerdata = self.RoundPlayer(player)
                self.playerlist.append(playerdata)

        class RoundPlayer:
            def __init__(self, mdict):
                self.raw = mdict
                self.id = mdict["puuid"]
                self.damagelist = []
                self.killist = []
                for damage in mdict["damage"]:
                    damagedata = self.DamageEvent(damage)
                    self.damagelist.append(damagedata)
                for kill in mdict["kills"]:
                    killdata = self.KillEvent(kill)
                    self.killist.append(killdata)
                self.ecospent = mdict["economy"]["spent"]
                self.ecoremaining = mdict["economy"]["remaining"]
                self.ecosteal = mdict["economy"]["loadoutValue"]
                self.weapon = self.Weapon(mdict["economy"])
                self.armor = self.Armor(mdict["economy"])
                self.ability = self.Ability(mdict["ability"])

            class Ability:
                def __init__(self, mdict):
                    self.raw = mdict
                    try:
                        self.c_casts = mdict["c_casts"]
                    except:
                        self.c_casts = 0
                    try:
                        self.q_casts = mdict["q_casts"]
                    except:
                        self.q_casts = 0
                    try:
                        self.e_casts = mdict["e_cast"]
                    except:
                        self.e_casts = 0
                    try:
                        self.ultimate_casts = mdict["x_cast"]
                    except:
                        self.ultimate_casts = 0
                    try:
                        self.x_casts = mdict["x_cast"]
                    except:
                        self.x_casts = 0

            class Armor:
                def __init__(self, mdict):
                    self.raw = mdict
                    self.id = mdict["armor"]
                    self.name = ValorantAPI().get_armor_name(self.id)
                    # self.name = mdict["name"]

            class Weapon:
                def __init__(self, mdict):
                    self.raw = mdict
                    self.id = mdict["weapon"]
                    self.name = ValorantAPI().get_weapon_name(self.id)
                    # self.name = mdict["name"]

            class DamageEvent:
                def __init__(self, mdict):
                    self.raw = mdict
                    self.id = mdict["receiver"]
                    # self.display_name = mdict["receiver_display_name"]
                    # self.team = mdict["receiver_team"]
                    self.damage = mdict["damage"]
                    self.headshots = mdict["headshots"]
                    self.bodyshots = mdict["bodyshots"]
                    self.legshots = mdict["legshots"]

            class KillEvent:
                def __init__(self, mdict):
                    self.raw = mdict
                    self.kill_time_in_round = mdict["timeSinceRoundStartMillis"]
                    self.kill_time_in_match = mdict["timeSinceGameStartMillis"]
                    self.killer = self.Killer(mdict)
                    self.victim = self.Victim(mdict)
                    self.assistantlist = mdict["assistants"]

                class Killer:
                    def __init__(self, mdict):
                        self.raw = mdict
                        self.id = mdict["killer"]
                        # self.display_name = mdict["killer_display_name"]

                class Victim:
                    def __init__(self, mdict):
                        self.raw = mdict
                        self.id = mdict["victim"]
                        # self.display_name = mdict["victim_display_name"]
                        self.death_location = self.DeathLocation(
                            mdict["victimLocation"]
                        )
                        self.weapon = self.Weapon(mdict)

                    class DeathLocation:
                        def __init__(self, mdict):
                            self.raw = mdict
                            self.x = mdict["x"]
                            self.y = mdict["y"]

                    class Weapon:
                        def __init__(self, mdict):
                            self.raw = mdict
                            self.type = mdict["finishingDamage"]["damageType"]
                            self.id = mdict["finishingDamage"]["damageItem"]
                            self.secondary_fire_mode = mdict["finishingDamage"][
                                "isSecondaryFireMode"
                            ]

    class WinnerTeam:
        def __init__(self, mdict):
            self.raw = mdict
            self.raw_name = mdict["winningTeam"]
            self.name = FormatData().format_team(mdict["winningTeam"])
            self.reason = mdict["roundResult"].lower()

    class SpikeInfo:
        def __init__(self, mdict):
            self.raw = mdict
            self.planted = mdict["bombPlanter"] is not None
            self.defused = mdict["bombDefuser"] is not None
            try:
                self.x = mdict["plantLocation"]["x"]
                self.y = mdict["plantLocation"]["y"]
            except:
                pass
            try:
                self.plant = self.PlantInfo(mdict)
            except:
                pass
            try:
                self.defuse = self.DefuseInfo(mdict)
            except:
                pass

        class PlantInfo:
            def __init__(self, mdict):
                self.id = mdict["bombPlanter"]
                # To be implemented yet #Name of the planter
                self.site = mdict["plantSite"]
                formatobj = FormatData().PlantTime()
                formatobj.format_time_ms(mdict)
                self.time = formatobj.display_time

        class DefuseInfo:
            def __init__(self, mdict):
                self.id = mdict["bombDefuser"]
                self.site = mdict["plantSite"]
                formatobj = FormatData().DefuseTime()
                formatobj.format_time_ms(mdict)
                self.time = formatobj.display_time


class FormatData:
    class DefuseTime:
        def format_time_ms(self, mdict: dict):
            self.ms = mdict["defuseRoundTime"]
            self.total_s = mdict["defuseRoundTime"] // 1000
            self.m = mdict["defuseRoundTime"] // 1000
            self.s = self.total_s - (60 * self.m)
            self.display_time = f"{self.m}:{self.s}"

    class PlantTime:
        def format_time_ms(self, mdict: dict):
            self.ms = mdict["plantRoundTime"]
            self.total_s = mdict["plantRoundTime"] // 1000
            self.m = mdict["plantRoundTime"] // 1000
            self.s = self.total_s - (60 * self.m)
            self.display_time = f"{self.m}:{self.s}"

    def format_team(self, team: str) -> str:
        if team == "Blue":
            return "Defenders"
        elif team == "Red":
            return "Attackers"
        else:
            return "NA"

    def format_side(self, team: str) -> str:
        if team == "Blue":
            return "Defending"
        elif team == "Red":
            return "Attacking"
        else:
            return "NA"

    def get_rounds_won(self, rounds: list[Round]) -> str:
        attcount = 0
        defcount = 0
        for round in rounds:
            if round.winnerteam.name == "Defenders":
                defcount += 1
            elif round.winnerteam.name == "Attackers":
                attcount += 1
        if defcount == attcount:
            return "Tie!"
        return (
            f"Defenders - {defcount}"
            if defcount > attcount
            else f"Attackers - {attcount}"
        )

    def get_rounds_stats(self, rounds: Rounds) -> str:
        attcount = 0
        defcount = 0
        for round in rounds:
            if round.winnerteam.name == "Defenders":
                defcount += 1
            elif round.winnerteam.name == "Attackers":
                attcount += 1
        return f"{defcount} Defenders/{attcount} Attackers"

    def get_player_side(self, currentplayerid: str, mdict: dict) -> str:
        players = mdict["players"]["all_players"]
        for player in players:
            playerdata = Player(player)
            playerteam = playerdata.team_id
            if playerdata.id == currentplayerid:
                return playerteam
        return None

    def check_match_won(self, currentplayerid: str, mdict: dict) -> str:
        rounds = mdict["rounds"]
        currentplayerside = self.get_player_side(currentplayerid, mdict)
        currentrounds = 0
        enemyrounds = 0
        for round in rounds:
            rounddata = Round(round)
            if rounddata.winnerteam == currentplayerside:
                currentrounds += 1
            else:
                enemyrounds += 1
        if currentrounds > enemyrounds:
            return "Won"
        elif enemyrounds > currentrounds:
            return "Lost"
        else:
            return "Tie"

    def get_average_kda(self, matches: Matches, currentplayerid: str) -> float:
        totalkills = 0
        totaldeaths = 0
        totalassists = 0
        for match in matches:
            if match.mode == "Deathmatch":
                continue
            if match.mode == "Escalation":
                continue
            if match.mode == "Replication":
                continue
            for player in match.players.playerlist:
                kills = player.stats.kills
                deaths = player.stats.deaths
                assists = player.stats.assists
                if player.id == currentplayerid:
                    totalkills += kills
                    totaldeaths += deaths
                    totalassists += assists
        if totaldeaths == 0:
            totaldeaths = 1
        return (totalkills + (0.5 * totalassists)) / totaldeaths

    def get_average_econ(self, matches: Matches, currentplayerid: str) -> int:
        totaleco = 0
        matchcount = 0
        for match in matches:
            if match.mode == "Spike Rush":
                continue
            if match.mode == "Deathmatch":
                continue
            if match.mode == "Escalation":
                continue
            if match.mode == "Replication":
                continue
            pass
        if matchcount == 0:
            matchcount = 1
        return totaleco / matchcount

    def get_freq_weapon(self, matches: Matches, currentplayerid: str) -> list:
        weaponsused = {"data": []}

        def get_duplicate_json(origjson, key):
            for data in origjson["data"]:
                if data["name"] == key:
                    return data
            return {}

        def merge_dicts(*dicts):
            d = {}
            for dict in dicts:
                for key in dict:
                    try:
                        if key == "uses":
                            d[key] += dict[key]
                        else:
                            d[key] = dict[key]
                    except KeyError:
                        d[key] = dict[key]
                    except TypeError:
                        pass
            return d

        def remove_duplicate_json(origjson, key):
            ad = {"data": []}
            for data in origjson["data"]:
                if data["name"] != key:
                    ad["data"].append(data)
            return ad

        for match in matches:
            if match.mode == "Deathmatch":
                continue
            if match.mode == "Escalation":
                continue
            if match.mode == "Replication":
                continue
            for round in match.rounds.roundlist:
                for rplayer in round.stats.playerlist:
                    if rplayer.id == currentplayerid:
                        currentdata = {"name": rplayer.weapon.name, "uses": 1}
                        if rplayer.weapon is None:
                            continue
                        dupdict = get_duplicate_json(weaponsused, currentdata["name"])
                        weaponsused = remove_duplicate_json(
                            weaponsused, currentdata["name"]
                        )
                        weaponsused["data"].append(merge_dicts(dupdict, currentdata))
        return sorted(weaponsused["data"], key=lambda x: x["uses"], reverse=True)

    def get_most_kills_weapon(self, matches, currentplayerid):
        weaponsused = {"data": []}

        def get_duplicate_json(origjson, key):
            for data in origjson["data"]:
                if data["name"] == key:
                    return data
            return {}

        def merge_dicts(*dicts):
            d = {}
            for dict in dicts:
                for key in dict:
                    try:
                        if key == "kills":
                            d[key] += dict[key]
                        else:
                            d[key] = dict[key]
                    except KeyError:
                        d[key] = dict[key]
                    except TypeError:
                        pass
            return d

        def remove_duplicate_json(origjson, key):
            ad = {"data": []}
            for data in origjson["data"]:
                if data["name"] != key:
                    ad["data"].append(data)
            return ad

        for match in matches:
            if match.mode == "Deathmatch":
                continue
            if match.mode == "Escalation":
                continue
            if match.mode == "Replication":
                continue
            for round in match.rounds.roundlist:
                for rplayer in round.stats.playerlist:
                    if rplayer.id == currentplayerid:
                        currentdata = {
                            "name": rplayer.weapon.name,
                            "kills": len(rplayer.killist),
                        }
                        if rplayer.weapon is None or str(rplayer.weapon.name) == "None":
                            continue
                        dupdict = get_duplicate_json(weaponsused, currentdata["name"])
                        weaponsused = remove_duplicate_json(
                            weaponsused, currentdata["name"]
                        )
                        weaponsused["data"].append(merge_dicts(dupdict, currentdata))
        return sorted(weaponsused["data"], key=lambda x: x["kills"], reverse=True)

    def get_round_losing_reason(self, matches, currentplayerid):
        roundlosingreasons = {"data": []}

        def get_duplicate_json(origjson, key):
            for data in origjson["data"]:
                if data["name"] == key:
                    return data
            return {}

        def merge_dicts(*dicts):
            d = {}
            for dict in dicts:
                for key in dict:
                    try:
                        if key == "uses":
                            d[key] += dict[key]
                        else:
                            d[key] = dict[key]
                    except KeyError:
                        d[key] = dict[key]
                    except TypeError:
                        pass
            return d

        def remove_duplicate_json(origjson, key):
            ad = {"data": []}
            for data in origjson["data"]:
                if data["name"] != key:
                    ad["data"].append(data)
            return ad

        for match in matches:
            if match.mode == "Deathmatch":
                continue
            if match.mode == "Escalation":
                continue
            if match.mode == "Replication":
                continue
            currentplayerteam = "None"
            for playerdata in match.players.playerlist:
                playerteam = playerdata.team_id
                if playerdata.id == currentplayerid:
                    currentplayerteam = playerteam
                    break
            for round in match.rounds.roundlist:
                if round.winnerteam.raw_name != currentplayerteam:
                    roundlosingreason = round.winnerteam.reason
                    currentdata = {"name": roundlosingreason, "uses": 1}
                    dupdict = get_duplicate_json(
                        roundlosingreasons, currentdata["name"]
                    )
                    roundlosingreasons = remove_duplicate_json(
                        roundlosingreasons, currentdata["name"]
                    )
                    roundlosingreasons["data"].append(merge_dicts(dupdict, currentdata))
            return sorted(
                roundlosingreasons["data"], key=lambda x: x["uses"], reverse=True
            )

    def get_player_kills(self, stats, currentplayerid):
        killist = []
        for rplayer in stats.playerlist:
            for kill in rplayer.killist:
                puuid = kill.killer.id
                if puuid == currentplayerid:
                    killist.append(kill)
        return killist

    def get_player_death(self, stats, currentplayerid):
        for rplayer in stats.playerlist:
            for kill in rplayer.killist:
                puuid = kill.victim.id
                if puuid == currentplayerid:
                    return kill
        return None

    def get_team_kills(self, stats, currentplayerid):
        currentplayerteam = None
        for rplayer in stats.playerlist:
            if rplayer.id == currentplayerid:
                currentplayerteam = rplayer.team
        teamids = []
        for rplayer in stats.playerlist:
            if rplayer.team != currentplayerteam:
                continue
            for kill in rplayer.killist:
                if not kill.killer.id in teamids:
                    teamids.append(kill.killer.id)
        killist = []
        for puid in teamids:
            playerkills = self.get_player_kills(stats, puid)
            killist.append(playerkills[-1])
        return killist
