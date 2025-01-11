from quart import Quart, request, render_template, redirect, session
import aiohttp
import os
from dotenv import load_dotenv
import asyncpg
import pickle
import asyncio
from asyncio import Event
from matchparser import Match


load_dotenv()
app = Quart(__name__)
app.secret_key = os.getenv("SECRET_KEY")
shutdown_event = Event()

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
RIOT_AUTH = os.getenv("RIOT_AUTH_BASE64")
RIOT_API_AUTH = {"X-Riot-Token": RIOT_API_KEY}
DATABASE_URL = os.getenv("DATABASE_URL")
pool = None
session_aiohttp = None
MAX_MATCHES = 20


async def background_task():
    global pool, session_aiohttp
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1)
    session_aiohttp = aiohttp.ClientSession()
    try:
        while not shutdown_event.is_set():
            await valorantMatchesSave()
            await asyncio.sleep(30)
    except asyncio.CancelledError:
        print("Background task cancelled")
    finally:
        await pool.close()


@app.before_serving
async def start_background_task():
    asyncio.create_task(background_task())


@app.after_serving
async def stop_background_task():
    shutdown_event.set()


async def getAiohttp(url, headers=None):
    global session_aiohttp
    async with session_aiohttp.get(url, headers=headers) as response:
        if response.status == 200:
            response_body = await response.json()
            return (200, response_body)
        else:
            return (response.status, None)
    return (-1, None)


async def valorantMatchSave(id):
    response = await getAiohttp(
        f"https://ap.api.riotgames.com/val/match/v1/matches/{id}",
        RIOT_API_AUTH,
    )
    if response[0] == 200:
        await saveParsedMatch(Match(response[1]), id)


async def saveParsedMatch(match, id):
    try:
        async with pool.acquire() as con:
            results = "INSERT INTO valorantmatches (id, data) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING"
            await con.execute(results, id, pickle.dumps(match))
    except asyncpg.exceptions.UniqueViolationError:
        pass
    except TimeoutError:
        print("Retrying {}".format(id))
        await saveParsedMatch(match)


async def valorantAccountSave(account, unique_match_ids):
    puuid = account["puuid"]
    response = await getAiohttp(
        f"https://ap.api.riotgames.com/val/match/v1/matchlists/by-puuid/{puuid}",
        RIOT_API_AUTH,
    )

    if response[0] != 200:
        response = await getAiohttp(
            f"https://ap.api.riotgames.com/val/match/v1/matchlists/by-puuid/{puuid}",
            RIOT_API_AUTH,
        )
        if response[0] != 200:
            return []

    coroutines = []
    for match in response[1]["history"]:
        match_id = match["matchId"]
        if match_id not in unique_match_ids:
            unique_match_ids.add(match_id)
            coroutines.append(valorantMatchSave(match_id))

    return coroutines


async def valorantMatchesSave():
    async with pool.acquire() as con:
        accounts = await con.fetch("SELECT * FROM riotaccounts")
        existing_match_ids = await con.fetch("SELECT id FROM valorantmatches")
        unique_match_ids = {record["id"] for record in existing_match_ids}

    all_match_coroutines = []
    for account in accounts:
        match_coroutines = await valorantAccountSave(account, unique_match_ids)
        all_match_coroutines.extend(match_coroutines)

    await asyncio.gather(*all_match_coroutines)


async def getAccountPUUIDName(puuid):
    response = await getAiohttp(
        f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}",
        RIOT_API_AUTH,
    )
    if response[0] == 200:
        return f'{response[1]["gameName"]}#{response[1]["tagLine"]}'
    return None


@app.route("/")
async def home_or_stats():
    if session.get("logged_in"):
        puuid = session.get("puuid")
        response = await getAiohttp(
            f"https://ap.api.riotgames.com/val/match/v1/matchlists/by-puuid/{puuid}",
            RIOT_API_AUTH,
        )
        if response[0] != 200:
            return await render_template("stats.html", matches=[])

        match_count = 0
        match_summaries = []
        for match in response[1]["history"]:
            match_id = match["matchId"]
            async with pool.acquire() as con:
                match_data = await con.fetchrow(
                    "SELECT data FROM valorantmatches WHERE id = $1", match_id
                )
            if match_data is None:
                continue
            if match_count >= MAX_MATCHES:
                break
            match_summaries.append(pickle.loads(match_data["data"]))
            match_count += 1

        return await render_template(
            "stats.html",
            matches=match_summaries,
            username=await getAccountPUUIDName(puuid),
        )
    else:
        return await render_template("index.html")


@app.route("/privacyPolicy")
async def privacyPolicy():
    return await render_template("privacyPolicy.html")


@app.route("/termsOfService")
async def termsOfService():
    return await render_template("termsOfService.html")


@app.route("/login")
async def valorantLogin():
    code = request.args.get("code")
    if code is None:
        return "Invalid request, missing code parameter!", 400

    params = {
        "grant_type": "authorization_code",
        "redirect_uri": "https://valorant.yashasviallen.is-a.dev/login",
        "code": code,
    }
    headers = {"Authorization": "Basic {}".format(RIOT_AUTH)}
    async with session_aiohttp.post(
        "https://auth.riotgames.com/token", data=params, headers=headers
    ) as response:
        access_resp = await response.json()
        async with session_aiohttp.get(
            "https://asia.api.riotgames.com/riot/account/v1/accounts/me",
            headers={"Authorization": f"Bearer {access_resp['access_token']}"},
        ) as response:
            if response.status == 200:
                account_resp = await response.json()
                async with pool.acquire() as con:
                    results = f"INSERT INTO riotaccounts (puuid) VALUES ($1)"
                    try:
                        await con.execute(results, account_resp["puuid"])
                    except asyncpg.exceptions.UniqueViolationError:
                        pass
                session["logged_in"] = True
                session["puuid"] = account_resp["puuid"]
                return redirect("/")
    return await render_template("riotaccountNotLinked.html")


def login_required(func):
    async def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/")
        return await func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


@app.route("/logout")
async def logout():
    session.pop("logged_in", None)
    session.pop("puuid", None)
    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port="27004")
