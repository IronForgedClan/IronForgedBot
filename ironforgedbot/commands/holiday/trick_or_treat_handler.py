import logging
import random
from enum import Enum

import discord

from ironforgedbot.common.helpers import find_emoji
from ironforgedbot.common.responses import build_response_embed, send_error_response
from ironforgedbot.database.database import db
from ironforgedbot.decorators import singleton
from ironforgedbot.services.ingot_service import IngotService
from ironforgedbot.services.member_service import MemberService
from ironforgedbot.state import STATE

logger = logging.getLogger(__name__)

GIFS = [
    "https://giphy.com/embed/jbJYmyIdelAJh9LQPs",
    "https://giphy.com/embed/l3vRfhFD8hJCiP0uQ",
    "https://giphy.com/embed/Z4Sek3StLGVO0",
    "https://giphy.com/embed/RokPlX3C71piryApkp",
    "https://giphy.com/embed/NOxZHqpeAw9tm",
    "https://giphy.com/embed/n8bAozpJjeiMU",
    "https://giphy.com/embed/RIHJGMww0p2IZng2l9",
    "https://giphy.com/embed/5yeQRdiYrDq2A",
    "https://giphy.com/embed/69warOL5MBhyzjAMov",
    "https://giphy.com/embed/7JbMfrLQJmxUc",
    "https://giphy.com/embed/26tjZAwU4fAQaahe8",
    "https://giphy.com/embed/cHw5gruhGb0IM",
    "https://giphy.com/embed/T9PbAsiKKWYlG",
    "https://giphy.com/embed/l0HlQXkh1wx1RjtUA",
    "https://giphy.com/embed/KupdfnqWwV7J6",
    "https://giphy.com/embed/RwLDkna2fN3fG",
    "https://giphy.com/embed/fvxGJE7bvJ6I5YJm4a",
    "https://giphy.com/embed/3ohjV8JRMcNVGYK10I",
    "https://giphy.com/embed/5fOiRnJOUnTMY",
    "https://giphy.com/embed/oS5Uanjai8qbe",
    "https://giphy.com/embed/oVmJpctjWDmi4",
    "https://giphy.com/embed/QuxqWk7m9ffxyfoa0a",
    "https://giphy.com/embed/kBrY0BlY4C4jhBeubb",
    "https://giphy.com/embed/qTD9EXZRgI1y0",
    "https://giphy.com/embed/l0MYryZTmQgvHI5TG",
    "https://giphy.com/embed/1qj43zb19qDsjLxMao",
    "https://giphy.com/embed/bEVKYB487Lqxy",
    "https://giphy.com/embed/28aGE5xerXkbK",
    "https://giphy.com/embed/Ee4Y8s4Lr3c0o",
    "https://giphy.com/embed/gBMjDoJW2CwU",
    "https://giphy.com/embed/oFVr84BOpjyiA",
    "https://giphy.com/embed/JBN6hII6XhuWk",
    "https://giphy.com/embed/jquDWJfPUMCiI",
    "https://giphy.com/embed/14fb6qSKwFLbGg",
    "https://giphy.com/embed/xU9TT471DTGJq",
    "https://giphy.com/embed/mQC0dMQwoQ4Fy",
    "https://giphy.com/embed/l0HlS0dxEOuJA6U0M",
    "https://giphy.com/embed/l2SqgYw7UPfayhIMo",
    "https://giphy.com/embed/LHJBeMDuSIfYY",
    "https://giphy.com/embed/IcifS1qG3YFlS",
    "https://giphy.com/embed/6YpKCYnlojXRS",
    "https://giphy.com/embed/GsJO3Yy0DCvEk",
    "https://giphy.com/embed/YRSQuXoJacEpO",
    "https://giphy.com/embed/8bXtRaK3rHvxe",
    "https://giphy.com/embed/eomy8S00ljwjK",
    "https://giphy.com/embed/l0FebdLg2Z2ZO5LNe",
    "https://giphy.com/embed/u5h5GqU0maLWE",
    "https://giphy.com/embed/l0NwLUVdksjwmtgLC",
    "https://giphy.com/embed/fjxl5lo5rZMre",
    "https://giphy.com/embed/G83E9hh3TkC9a",
    "https://giphy.com/embed/HaWGrXhclEQso",
    "https://giphy.com/embed/LwP7B9qCPfwLC",
    "https://giphy.com/embed/MuHxTqxKayPFS",
    "https://giphy.com/embed/xT0GqIleDVzqm7HE8o",
    "https://giphy.com/embed/l41Yl108BMSthoqXu",
    "https://giphy.com/embed/26BRAwxj0wEa6efFC",
    "https://giphy.com/embed/jIsgja3R661b2",
    "https://giphy.com/embed/OPcrwxFDZE5uU",
    "https://giphy.com/embed/LNLpm8hhY2yc7GPXB9",
    "https://giphy.com/embed/Zxp6dJwqiTyo0",
    "https://giphy.com/embed/3ohzdYjwEQuR1J7dte",
    "https://giphy.com/embed/13KV2vJLM4p2SI",
    "https://giphy.com/embed/l3V0d6rmSuzSwcb0Q",
    "https://giphy.com/embed/V3UvgjfbbZ3X2",
    "https://giphy.com/embed/12RfP2odT4hEOI",
    "https://giphy.com/embed/l0HlMWkHJKvyjftKM",
    "https://giphy.com/embed/igi0dS20WxPJvroIgW",
    "https://giphy.com/embed/Pwe7LOrjLGNy0",
    "https://giphy.com/embed/s0OXfMFqNC2QdfNPGx",
    "https://giphy.com/embed/QMb8vOYeatvaHSJuS6",
    "https://giphy.com/embed/hctAq4KcfzvENlz7Ck",
    "https://giphy.com/embed/GPvPg9pb7SUx2",
    "https://giphy.com/embed/genCnNWnmKJcDErp8h",
    "https://giphy.com/embed/efxG06iL3J7zSVEoqF",
    "https://giphy.com/embed/TdFnxsJuDv4lbdXP7I",
    "https://giphy.com/embed/duuegFXcMKherSFtkM",
    "https://giphy.com/embed/jQycuUzZVB4Cv5TxLk",
    "https://giphy.com/embed/yvbiFXNXp6ShkDrv6i",
    "https://giphy.com/embed/xT9KVHs6I3EfDKnVte",
    "https://giphy.com/embed/xT9KVjBI3W2283URdm",
    "https://giphy.com/embed/UEkfeSORZIQog",
    "https://giphy.com/embed/l0Iun26OYGNGR4tKU",
    "https://giphy.com/embed/xT9KVuZarGwgenjBOU",
    "https://giphy.com/embed/dIF9r8sVaSDPW",
    "https://giphy.com/embed/xT9KVg8gkDEyJIrVdK",
    "https://giphy.com/embed/3otPoJhe5AZrhllEeQ",
    "https://giphy.com/embed/bEew58Q0lSy7C",
    "https://giphy.com/embed/u15ZDWKh95r7q",
    "https://giphy.com/embed/I45vYOHGvWK2I",
    "https://giphy.com/embed/5oWpOD8Thsmo8",
    "https://giphy.com/embed/J4PzFd0Vq7vYQ",
    "https://giphy.com/embed/l46Ciz9gxiJNGM5YA",
    "https://giphy.com/embed/s4Q3geM5T1XCo",
    "https://giphy.com/embed/ptOuUotgxJ648",
    "https://giphy.com/embed/3og0IT214wwK7MxG7e",
    "https://giphy.com/embed/HiDd1Kv0fFvgY",
    "https://giphy.com/embed/9OqB7C2tlxV84",
    "https://giphy.com/embed/K5Gqxrz4s6oOQ",
    "https://giphy.com/embed/h9J9Mysy0X1FC",
    "https://giphy.com/embed/l2R0fCTGe4EGyS0Ao",
    "https://giphy.com/embed/F9UJWvTartMHe",
    "https://giphy.com/embed/w5Lp7RmMcMTRe",
    "https://giphy.com/embed/rcfRXKbNNKrOU",
    "https://giphy.com/embed/12TgYGrHqVesa4",
    "https://giphy.com/embed/rWMkSuxUSEjyo",
    "https://giphy.com/embed/YLIFVP5zkLuGQ",
    "https://giphy.com/embed/vppfBcl2vrsek",
    "https://giphy.com/embed/siKMh3tAfQtsQ",
    "https://giphy.com/embed/IUqcdVEVjKsH6",
    "https://giphy.com/embed/QJJJcOySWIG1q",
    "https://giphy.com/embed/6oEkcFF4E03tK",
    "https://giphy.com/embed/xVudSZL97djWljDzvg",
    "https://giphy.com/embed/0sUXVnW01KKEdRTThv",
    "https://giphy.com/embed/N2quVSSRLwjN6",
    "https://giphy.com/embed/cKRG8Vz1vgv3W",
    "https://giphy.com/embed/L0HTycLevyRlS",
    "https://giphy.com/embed/13PvTOzHbSBPBC",
    "https://giphy.com/embed/VvxJm74lRElvW",
    "https://giphy.com/embed/GQbNswkIXzlvi",
    "https://giphy.com/embed/9QeUkhB0C9zzy",
    "https://giphy.com/embed/4Sm7D7rlopgqs",
    "https://giphy.com/embed/9MHWfbuzuQRdC",
    "https://giphy.com/embed/FPAzQ9dFmK89y",
    "https://giphy.com/embed/QsyPRpG6WVR6SYfBVw",
    "https://giphy.com/embed/qToRXyEdW31xm",
    "https://giphy.com/embed/mAYym8ui14nuM",
    "https://giphy.com/embed/13R1tAWGfHnWiA",
    "https://giphy.com/embed/f5q7pA7KM1cQmPqwqQ",
    "https://giphy.com/embed/fVi8QTmS3U5cm3FY4H",
    "https://giphy.com/embed/XfK1UwGdONkm74xCw9",
    "https://giphy.com/embed/llyXVF8HwZKtrz4W6U",
    "https://giphy.com/embed/JBHILTl3Df6aA",
    "https://giphy.com/embed/qt8JrN2ATag8M",
    "https://giphy.com/embed/IdwEN5eoXFodi",
    "https://giphy.com/embed/xT5LMCEqNmf12uVdSw",
    "https://giphy.com/embed/3orieUorpNFurrhGaA",
    "https://giphy.com/embed/11WPbzFpOuQSyI",
    "https://giphy.com/embed/xT5LMyNjatcyCE2lTG",
    "https://giphy.com/embed/l2JdSBo6QzmitH7Mc",
    "https://giphy.com/embed/3o6MbbSRunUKRxcKvS",
    "https://giphy.com/embed/3o6Mb5iisRRCCxCA5q",
    "https://giphy.com/embed/xT5LMtdoPAlGWHmAzS",
    "https://giphy.com/embed/3o6MbgZTfran6AHIic",
    "https://giphy.com/embed/NdfezeeAnQGUvC3AuG",
    "https://giphy.com/embed/3o7TKVGI2JHgZCawLK",
    "https://giphy.com/embed/26uf8PZTLE6kRcAz6",
    "https://giphy.com/embed/9HFJeciNrHKeI",
    "https://giphy.com/embed/3ohhwFkswmco4FJdtu",
    "https://giphy.com/embed/EiaKmyLrPqPio",
    "https://giphy.com/embed/9PxQsCGhVsSBy",
    "https://giphy.com/embed/wN6Ez6gIe4fLy",
    "https://giphy.com/embed/lXXqPhhLfDf4Q",
    "https://giphy.com/embed/3ohhwfAa9rbXaZe86c",
    "https://giphy.com/embed/THlB4bsoSA0Cc",
    "https://giphy.com/embed/QWPIBMUCSXRL2",
    "https://giphy.com/embed/mdzHqtdkwdeZG",
    "https://giphy.com/embed/oVIee2L3kjgUE",
    "https://giphy.com/embed/jpbAaUG7cjkZy",
    "https://giphy.com/embed/P0I4FJmnYl5E4",
    "https://giphy.com/embed/TGHXd9J6mK6sM",
    "https://giphy.com/embed/IhuFgc1AnzrmE",
    "https://giphy.com/embed/3ow0TN2M8TH2aAn67F",
    "https://giphy.com/embed/ITrQsucXGd88o",
    "https://giphy.com/embed/Q4sjT8WOcE1Ow",
    "https://giphy.com/embed/11Te2XU6O0orS0",
    "https://giphy.com/embed/xT9KVyjNlC40uBUO9W",
    "https://giphy.com/embed/q0vEPDANK527lTsZzy",
    "https://giphy.com/embed/yP7z0GSKKiswXKHiUn",
    "https://giphy.com/embed/NVlrEnSgDTwe6ZIMVs",
    "https://giphy.com/embed/U6qZw9rnxW6Hs2K4mA",
    "https://giphy.com/embed/3o7TKAQJnQJPp7y8Te",
    "https://giphy.com/embed/GJdyb2BqwDtbq",
    "https://giphy.com/embed/6he2lvEoUwKGLwKIrQ",
    "https://giphy.com/embed/vJgxZ71bDcZt8OS1hX",
    "https://giphy.com/embed/20RFCtXjVXb9e",
    "https://giphy.com/embed/VyhQ6LgFckzRu",
    "https://giphy.com/embed/2sbPhDJ1bOe9veN8vY",
    "https://giphy.com/embed/l2YWAA2jwPVUdDnGw",
    "https://giphy.com/embed/pjcV8IhfaLnCAy5IV9",
    "https://giphy.com/embed/3oz8xSwPT41eZOvS2A",
    "https://giphy.com/embed/HB6LEzrCJs4A0NNYJM",
    "https://giphy.com/embed/BRF2QmzB59VryBsgdQ",
    "https://giphy.com/embed/1lnH4AXlWgqp7e7VRn",
    "https://giphy.com/embed/L606NTBE9mODC",
    "https://giphy.com/embed/01Oqnvn0guyBTXoQIe",
    "https://giphy.com/embed/2frWHgkE573sk",
    "https://giphy.com/embed/2vmgb8ZGaeBsuSeo5I",
    "https://giphy.com/embed/Y15UrbIl4tbYk",
    "https://giphy.com/embed/7OeXVZZO6Me5O",
    "https://giphy.com/embed/26uf74lvsfLSt70Vq",
    "https://giphy.com/embed/JlZJZnCmnExFu",
    "https://giphy.com/embed/11J4DgZ883KhLq",
    "https://giphy.com/embed/3o6Zt0XNmz5ASmzH9u",
    "https://giphy.com/embed/7lNcDfYEy3byKvY4BG",
    "https://giphy.com/embed/V8fXavnE00iPu",
    "https://giphy.com/embed/2fXvNjhnat6yk",
    "https://giphy.com/embed/3I42TOjesVXFK",
    "https://giphy.com/embed/AFTWK5Qo22V2g",
    "https://giphy.com/embed/klYzRJwHUUWxW",
    "https://giphy.com/embed/tPkQzeWgmTQVW",
    "https://giphy.com/embed/YmTyGDmIubn6E",
    "https://giphy.com/embed/X96p9L5DkcdSOIoBiX",
    "https://giphy.com/embed/l2Sqf6tB2gympOc0g",
    "https://giphy.com/embed/dYEJs1feiAlSo",
    "https://giphy.com/embed/h3sl6ULjDJo9a",
    "https://giphy.com/embed/PFwKHjOcIoVUc",
    "https://giphy.com/embed/7U1XfwZ94okRW",
    "https://giphy.com/embed/FbfNWx3LPoy2I",
    "https://giphy.com/embed/ATfHxbc5VaS08",
    "https://giphy.com/embed/HBClyWNBZTqg0",
    "https://giphy.com/embed/cpdm68C5dDKV2",
    "https://giphy.com/embed/3ofT5QOCCRDsM5ZDag",
    "https://giphy.com/embed/eXxDUhcc2iaiUGgwz7",
    "https://giphy.com/embed/J5evF2PW0fbKkohcPF",
    "https://giphy.com/embed/i0qDBDRw0d55wBNCLZ",
    "https://giphy.com/embed/26gsv1iextbg5Gm5O",
    "https://giphy.com/embed/ABrRUFN83nj68",
    "https://giphy.com/embed/tLTEFHdOu8fQc",
    "https://giphy.com/embed/347UjtDLwMoXMBD6Pm",
    "https://giphy.com/embed/d7ZnigaY86sdMDC3SL",
    "https://giphy.com/embed/7XuBAl7nzvZ9yN0zaN",
    "https://giphy.com/embed/DvtsYOKrqPZg4",
    "https://giphy.com/embed/QBH4pcJAjGODC",
    "https://giphy.com/embed/35LCBkf6buF9AuzOL7",
    "https://giphy.com/embed/SbKXI3yxofOOK7theN",
    "https://giphy.com/embed/wzgjH2QsAanC0",
    "https://giphy.com/embed/no2JeUjkz6EBG",
    "https://giphy.com/embed/2huOBcwEIGGNa",
    "https://giphy.com/embed/RSeauh7Iyr9Yoys5Dd",
    "https://giphy.com/embed/ztEgW4lPD3qSbZHVt2",
    "https://giphy.com/embed/YoJFD1UZFhnIk",
    "https://giphy.com/embed/fGdm4ZsZ8QbIhlMU7r",
    "https://giphy.com/embed/4nlLsagDaNTtRxWGkX",
    "https://giphy.com/embed/34hWhLGCYhmvD3PXdg",
    "https://giphy.com/embed/twWWtsZ4Ef8d0a7t1F",
    "https://giphy.com/embed/B0qOY0YfWeTdZIz8Yq",
    "https://giphy.com/embed/ScsjBLspSbhhQP1JWR",
    "https://giphy.com/embed/h7jYjQivP0mxHSHbfE",
    "https://giphy.com/embed/SNzCErlLKLLvVqzR2a",
    "https://giphy.com/embed/HRF05wHuIBGAkS1wRt",
    "https://giphy.com/embed/9Y1BfGEG29BVrNZyBX",
    "https://giphy.com/embed/3osxYz9sSvPoM8IRva",
    "https://giphy.com/embed/l2Je5oKAjMtwB5x4s",
    "https://giphy.com/embed/ORWdUNzeK5FJWDiDW4",
    "https://giphy.com/embed/tw2qkBNhG1xu0",
    "https://giphy.com/embed/57x4ApyRzkI1y",
    "https://giphy.com/embed/9F8qrvlkjUdcQ",
    "https://giphy.com/embed/UUZizGOekwK1a",
    "https://giphy.com/embed/CnRmpfxlPutVAFChvm",
    "https://giphy.com/embed/9PT57ONmuazTi",
    "https://giphy.com/embed/l3vQWwsj7Ww40gAyQ",
    "https://giphy.com/embed/5vCWii3HEE75e",
    "https://giphy.com/embed/3oz8xSD5WkRNG1R6x2",
    "https://giphy.com/embed/3oz8xD0xvAJ5FCk7Di",
    "https://giphy.com/embed/5gyIqaONkIlA49Bg8C",
    "https://giphy.com/embed/ETHkUuVhK0L723cWVg",
    "https://giphy.com/embed/3o7aTtcgJBW0pOfpFC",
    "https://giphy.com/embed/h5NLPVn3rg0Rq",
    "https://giphy.com/embed/fuHdUls1uGRtS",
    "https://giphy.com/embed/aOPINgmqpVXNK",
    "https://giphy.com/embed/1BQdjXovIqSLS",
    "https://giphy.com/embed/zKf6Fl6wLX0oo",
    "https://giphy.com/embed/10ExQg4YwG1p8k",
    "https://giphy.com/embed/eKxbmJ88B0JuU",
    "https://giphy.com/embed/eSg8K9E0oyCLm",
    "https://giphy.com/embed/xTiTntH1cWq5gyBceQ",
    "https://giphy.com/embed/3fiozjLoilfLSovqgt",
    "https://giphy.com/embed/oirp52G8Ijpz5mlqUY",
    "https://giphy.com/embed/WcAuwBs45Pzzx1OsmO",
    "https://giphy.com/embed/O6kb3Pa3Kgbsc",
    "https://giphy.com/embed/QG37Ws7Bm5d60",
    "https://giphy.com/embed/TmzGmX0c91JUQ",
    "https://giphy.com/embed/YEkdhK3KYafGE",
    "https://giphy.com/embed/7QIAI2eGWecmc",
    "https://giphy.com/embed/YNLLu9hPJKJeE",
    "https://giphy.com/embed/GBwYrdMTQ9Lb2",
    "https://giphy.com/embed/lYiNyCGfT5BMeVxYBF",
    "https://giphy.com/embed/11PyEGIyET0NSU",
    "https://giphy.com/embed/kJfqyIRrEm35e",
    "https://giphy.com/embed/aTf4PONtSYB1e",
    "https://giphy.com/embed/YARUMKaGd8cRG",
    "https://giphy.com/embed/4KFQL2rzYs1nG",
    "https://giphy.com/embed/XkcWp4M06HbMI",
    "https://giphy.com/embed/xUOwG9sKaQtpInT7wI",
    "https://giphy.com/embed/3ohs4CFLK53EJYWJPy",
    "https://giphy.com/embed/26DMVA1ArEk3TOrte",
    "https://giphy.com/embed/mmWX5KjweaNAQ",
    "https://giphy.com/embed/xZJuo8bBgUopO",
    "https://giphy.com/embed/Drw86fJe2ifC0",
    "https://giphy.com/embed/q8nPhZQwxL7MI",
    "https://giphy.com/embed/QrgdcmyQohWnpbZdcH",
    "https://giphy.com/embed/ighdr7xNaVwwQtUkP0",
]

THUMBNAILS = [
    "https://oldschool.runescape.wiki/images/Pumpkin_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Skull_%28item%29_detail.png/1024px-Skull_%28item%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%288%29.png/1280px-Jack-O-Lantern_%288%29.png",
    "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%289%29.png/1024px-Jack-O-Lantern_%289%29.png",
    "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%2810%29.png/1024px-Jack-O-Lantern_%2810%29.png",
    "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%2811%29.png/1280px-Jack-O-Lantern_%2811%29.png",
    "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%2812%29.png/1024px-Jack-O-Lantern_%2812%29.png",
    "https://oldschool.runescape.wiki/images/thumb/Jack-O-Lantern_%2819%29.png/1024px-Jack-O-Lantern_%2819%29.png",
    "https://oldschool.runescape.wiki/images/thumb/Great_cauldron_%28overflowing%29.png/1280px-Great_cauldron_%28overflowing%29.png",
    "https://oldschool.runescape.wiki/images/thumb/Greater_demon_mask_detail.png/1024px-Greater_demon_mask_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Black_demon_mask_detail.png/1280px-Black_demon_mask_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Death.png/1280px-Death.png",
    "https://oldschool.runescape.wiki/images/thumb/Orange_pumpkin_%28angry%29_detail.png/150px-Orange_pumpkin_%28angry%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Orange_pumpkin_%28depressed%29_detail.png/150px-Orange_pumpkin_%28depressed%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Orange_pumpkin_%28disgusted%29_detail.png/150px-Orange_pumpkin_%28disgusted%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Orange_pumpkin_%28evil%29_detail.png/150px-Orange_pumpkin_%28evil%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Orange_pumpkin_%28happy%29_detail.png/150px-Orange_pumpkin_%28happy%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Orange_pumpkin_%28laughing%29_detail.png/150px-Orange_pumpkin_%28laughing%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Orange_pumpkin_%28sad%29_detail.png/150px-Orange_pumpkin_%28sad%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Orange_pumpkin_%28shocked%29_detail.png/150px-Orange_pumpkin_%28shocked%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Orange_pumpkin_%28silly%29_detail.png/150px-Orange_pumpkin_%28silly%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Beige_pumpkin_%28angry%29_detail.png/150px-Beige_pumpkin_%28angry%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Beige_pumpkin_%28depressed%29_detail.png/150px-Beige_pumpkin_%28depressed%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Beige_pumpkin_%28disgusted%29_detail.png/150px-Beige_pumpkin_%28disgusted%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Beige_pumpkin_%28evil%29_detail.png/150px-Beige_pumpkin_%28evil%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Beige_pumpkin_%28happy%29_detail.png/150px-Beige_pumpkin_%28happy%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Beige_pumpkin_%28laughing%29_detail.png/150px-Beige_pumpkin_%28laughing%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Beige_pumpkin_%28sad%29_detail.png/150px-Beige_pumpkin_%28sad%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Beige_pumpkin_%28shocked%29_detail.png/150px-Beige_pumpkin_%28shocked%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Beige_pumpkin_%28silly%29_detail.png/150px-Beige_pumpkin_%28silly%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Dark_green_pumpkin_%28angry%29_detail.png/150px-Dark_green_pumpkin_%28angry%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Dark_green_pumpkin_%28depressed%29_detail.png/150px-Dark_green_pumpkin_%28depressed%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Dark_green_pumpkin_%28disgusted%29_detail.png/150px-Dark_green_pumpkin_%28disgusted%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Dark_green_pumpkin_%28evil%29_detail.png/150px-Dark_green_pumpkin_%28evil%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Dark_green_pumpkin_%28happy%29_detail.png/150px-Dark_green_pumpkin_%28happy%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Dark_green_pumpkin_%28laughing%29_detail.png/150px-Dark_green_pumpkin_%28laughing%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Dark_green_pumpkin_%28sad%29_detail.png/150px-Dark_green_pumpkin_%28sad%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Dark_green_pumpkin_%28shocked%29_detail.png/150px-Dark_green_pumpkin_%28shocked%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Dark_green_pumpkin_%28silly%29_detail.png/150px-Dark_green_pumpkin_%28silly%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Powder_grey_pumpkin_%28angry%29_detail.png/150px-Powder_grey_pumpkin_%28angry%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Powder_grey_pumpkin_%28depressed%29_detail.png/150px-Powder_grey_pumpkin_%28depressed%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Powder_grey_pumpkin_%28disgusted%29_detail.png/150px-Powder_grey_pumpkin_%28disgusted%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Powder_grey_pumpkin_%28evil%29_detail.png/150px-Powder_grey_pumpkin_%28evil%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Powder_grey_pumpkin_%28happy%29_detail.png/150px-Powder_grey_pumpkin_%28happy%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Powder_grey_pumpkin_%28laughing%29_detail.png/150px-Powder_grey_pumpkin_%28laughing%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Powder_grey_pumpkin_%28sad%29_detail.png/150px-Powder_grey_pumpkin_%28sad%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Powder_grey_pumpkin_%28shocked%29_detail.png/150px-Powder_grey_pumpkin_%28shocked%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Powder_grey_pumpkin_%28silly%29_detail.png/150px-Powder_grey_pumpkin_%28silly%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Red_pumpkin_%28angry%29_detail.png/150px-Red_pumpkin_%28angry%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Red_pumpkin_%28depressed%29_detail.png/150px-Red_pumpkin_%28depressed%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Red_pumpkin_%28disgusted%29_detail.png/150px-Red_pumpkin_%28disgusted%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Red_pumpkin_%28evil%29_detail.png/150px-Red_pumpkin_%28evil%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Red_pumpkin_%28happy%29_detail.png/150px-Red_pumpkin_%28happy%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Red_pumpkin_%28laughing%29_detail.png/150px-Red_pumpkin_%28laughing%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Red_pumpkin_%28sad%29_detail.png/150px-Red_pumpkin_%28sad%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Red_pumpkin_%28shocked%29_detail.png/150px-Red_pumpkin_%28shocked%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Red_pumpkin_%28silly%29_detail.png/150px-Red_pumpkin_%28silly%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/White_pumpkin_%28angry%29_detail.png/150px-White_pumpkin_%28angry%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/White_pumpkin_%28depressed%29_detail.png/150px-White_pumpkin_%28depressed%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/White_pumpkin_%28disgusted%29_detail.png/150px-White_pumpkin_%28disgusted%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/White_pumpkin_%28evil%29_detail.png/150px-White_pumpkin_%28evil%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/White_pumpkin_%28happy%29_detail.png/150px-White_pumpkin_%28happy%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/White_pumpkin_%28laughing%29_detail.png/150px-White_pumpkin_%28laughing%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/White_pumpkin_%28sad%29_detail.png/150px-White_pumpkin_%28sad%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/White_pumpkin_%28shocked%29_detail.png/150px-White_pumpkin_%28shocked%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/White_pumpkin_%28silly%29_detail.png/150px-White_pumpkin_%28silly%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Yellow_pumpkin_%28angry%29_detail.png/150px-Yellow_pumpkin_%28angry%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Yellow_pumpkin_%28depressed%29_detail.png/150px-Yellow_pumpkin_%28depressed%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Yellow_pumpkin_%28disgusted%29_detail.png/150px-Yellow_pumpkin_%28disgusted%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Yellow_pumpkin_%28evil%29_detail.png/150px-Yellow_pumpkin_%28evil%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Yellow_pumpkin_%28happy%29_detail.png/150px-Yellow_pumpkin_%28happy%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Yellow_pumpkin_%28laughing%29_detail.png/150px-Yellow_pumpkin_%28laughing%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Yellow_pumpkin_%28sad%29_detail.png/150px-Yellow_pumpkin_%28sad%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Yellow_pumpkin_%28shocked%29_detail.png/150px-Yellow_pumpkin_%28shocked%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Yellow_pumpkin_%28silly%29_detail.png/150px-Yellow_pumpkin_%28silly%29_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Red_halloween_mask_detail.png/150px-Red_halloween_mask_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Green_halloween_mask_detail.png/150px-Green_halloween_mask_detail.png",
    "https://oldschool.runescape.wiki/images/thumb/Blue_halloween_mask_detail.png/150px-Blue_halloween_mask_detail.png",
]


class TrickOrTreat(Enum):
    GIF = 5
    REMOVE_INGOTS_LOW = 11
    ADD_INGOTS_LOW = 10
    REMOVE_INGOTS_HIGH = 55
    ADD_INGOTS_HIGH = 50
    REMOVE_ALL_INGOTS_TRICK = 100
    JACKPOT_INGOTS = 10_000


@singleton
class TrickOrTreatHandler:
    def __init__(self):
        self.weights = [1 / item.value for item in TrickOrTreat]
        self.ingot_icon = find_emoji(None, "Ingot")
        self.gif_history = []
        self.thumbnail_history = []
        self.positive_message_history = []
        self.negative_message_history = []

    def _get_random_positive_message(self) -> str:
        if random.random() >= 0.5:
            return ":tada: Treat! **{ingots}**!\ngzzzzzzzzzzzzz :jack_o_lantern:"

        options = [
            "Oh fine.\n**{ingots}** is a small price to pay to get out of this interaction.",
            "Congratulations on your life changing payout of... _*drumroll*_\n**{ingots}**!",
            "I'm feeling generous.\nTake **{ingots}** ingots and get yourself something nice.",
            "**{ingots}** to trim my armour?\nYou got yourself a deal. :handshake:",
            "...and with the recipt of **{ingots}** ingots, the contract is official.\nI hope you read the fine print.",
            "I'm printing **{ingots}** out of thin air just for you.\nThis devalues all ingots a little bit, I hope you're happy.",
            "If I dropped **{ingots}** north of the Edgeville ditch...\nwould you pick them up? Asking for a friend.",
            "When Kodiak's back was turned, I stole **{ingots}** from his account.\nNow they are yours, and you're as guilty as I am.",
            "You have been credited **{ingots}**.\nThank you for playing, human.",
            "On behalf of everyone at Iron Forged I just want to say ~~fuc~~... **congratulations**!!\nWe are all so happy for you. **{ingots}**.",
            "_Sigh_\nJust take **{ingots}** ingots and get out of my sight.",
            "**JACKPOT!!!!!!!**\nOh no, it's only **{ingots}**. False alarm.",
            "**{ingots}**\ngz.",
            "Gzzzzzzzzzzz!!\nWinnings: **{ingots}**.",
            "The RNG Gods smile upon you this day, adventurer.\nYou won **{ingots}** ingots.",
            "You are now thinking about blinking..\n...and ingots **{ingots}**.\n_blingots_.",
            "You've been working hard lately. I've noticed.\nHave **{ingots}** ingots.",
            "**{ingots}**\n**gzzzzzzz**\ngzzzzzzz\n-# gzzzzzzz",
            "You're rich now!\n**{ingots}** ingot payday.",
            "Good job bud!\n**{ingots}**.",
            "Hey bud!\n**{ingots}** you deserve this.",
            "Good day adventurer. I come to you with gifts.\n**{ingots}** fresh from the mine.",
            "**{ingots}** just for you,\nbud.",
            "**{ingots}** from my bud **test run btw**\ndirectly to you!",
        ]

        chosen = random.choice(
            [s for s in options if s not in self.positive_message_history]
        )
        self._add_to_history(chosen, self.positive_message_history, 5)

        return chosen

    def _get_random_negative_message(self) -> str:
        if random.random() >= 0.5:
            annoyance = [
                "bud",
                "buddy",
                "pal",
                "champ",
                "boss",
                "chief",
                "friend",
                "mate",
                "kid",
                "kiddo",
            ]
            return (
                "Trick!\nUnlucky " + random.choice(annoyance) + " **{ingots}** ingots."
            )

        options = [
            "You gambled against the house and lost **{ingots}**...\nIt's me. I am the house.",
            "Your profile has been found guilty of botting.\nThe fine is **{ingots}**.\nPayment is mandatory.\nYour guilt is undeniable.",
            "The odds of losing exactly **{ingots}** is truly astronomical.\nReally, you should be proud.",
            "...aaaaaaand it's gone.\n**{ingots}** :wave:",
            "Quick, look behind you! _*yoink*_ **{ingots}**\n:eyes:",
            "**JACKPOT!!!!!!!**\nOh no... it's an anti-jackpot **{ingots}**. Unlucky.",
            "You chose...\n\n...poorly **{ingots}**.",
            "Sorry champ..\n**{ingots}** :frowning:",
            "Ah damn, I was rooting for you too **{ingots}**.\n-# not",
            "If you stop reading now, you can pretend you actually won.\n**{ingots}** :hear_no_evil:",
            "**{ingots}**...\nSorry.",
            "**WRONG {ingots}**, try again.\n:person_gesturing_no:",
            "Ha!\n**{ingots}** :person_shrugging:",
            "The RNG Gods are laughing at you, adventurer...\nYou lost **{ingots}** ingots.",
            "**{ingots}** ouch bud.\n:grimacing:",
            "Unluck pal, **{ingots}**.\n:badger:",
            "You are a loser.\n\nAlso, you lost **{ingots}** ingots.",
            "I took no pleasure in deducting **{ingots}** from you.\n... :joy:",
            "The worst part about losing **{ingots}**, isn't the ingot loss.\nIt's the public humiliation. :clown:",
            "It's nothing personal.\nI'm just following my programming **{ingots}**.",
            "Sorry bud...\n**{ingots}**",
            "Sorry buddy...\n**{ingots}**",
            "Unlucky bud...\n**{ingots}**",
            "Sucks to be you, champ.\n**{ingots}**",
            "My electricity bill is due...\nIt's your turn **{ingots}**.",
            "I see dead ingots.\n**{ingots}** :ghost:",
        ]

        chosen = random.choice(
            [s for s in options if s not in self.negative_message_history]
        )
        self._add_to_history(chosen, self.negative_message_history, 5)

        return chosen

    def _get_balance_message(self, username: str, balance: int) -> str:
        return f"\n\n**{username}** now has **{self.ingot_icon}{balance:,}** ingots."

    def _build_embed(self, content: str) -> discord.Embed:
        chosen_thumbnail = random.choice(
            [s for s in THUMBNAILS if s not in self.thumbnail_history]
        )
        self._add_to_history(chosen_thumbnail, self.thumbnail_history, 8)

        embed = build_response_embed("", content, discord.Color.orange())
        embed.set_thumbnail(url=chosen_thumbnail)
        return embed

    def _build_no_ingots_error_response(self, username: str) -> discord.Embed:
        return self._build_embed(
            (
                "You lost... _well_, you would have lost ingots if you had any!\n"
                + "Attend some events, throw us a bond or _something_.\nYou're making me look bad. 💀"
                + self._get_balance_message(username, 0)
            )
        )

    def _add_to_history(self, item, list: list, limit=5):
        list.append(item)
        if len(list) > limit:
            list.pop(0)

    async def _adjust_ingots(
        self,
        interaction: discord.Interaction,
        quantity: int,
        discord_member: discord.Member | None,
    ) -> int:
        if not discord_member:
            raise Exception("error no user found")

        async for session in db.get_session():
            ingot_service = IngotService(session)
            member_service = MemberService(session)

            if quantity > 0:
                result = await ingot_service.try_add_ingots(
                    discord_member.id, quantity, None, "Trick or treat win"
                )
            else:
                member = await member_service.get_member_by_discord_id(
                    interaction.user.id
                )

                if not member:
                    logger.error("Member not found in database")
                    await send_error_response(interaction, "Error updating ingots.")
                    return 0

                if member.ingots > 0 and member.ingots - quantity < 0:
                    quantity = member.ingots
                else:
                    return -1

                result = await ingot_service.try_remove_ingots(
                    discord_member.id, quantity, None, "Trick or treat loss"
                )

            if not result:
                logger.error("Error adjusting ingots")
                await send_error_response(interaction, "Error updating ingots.")
                return 0

            if not result.status:
                await send_error_response(interaction, result.message)
                return 0

            return result.new_total
        return 0

    async def random_result(self, interaction: discord.Interaction):
        match random.choices(list(TrickOrTreat), weights=self.weights)[0]:
            case TrickOrTreat.JACKPOT_INGOTS:
                return await self.result_jackpot(interaction)
            case TrickOrTreat.REMOVE_ALL_INGOTS_TRICK:
                return await self.result_remove_all_ingots_trick(interaction)
            case TrickOrTreat.REMOVE_INGOTS_HIGH:
                return await self.result_remove_high(interaction)
            case TrickOrTreat.ADD_INGOTS_HIGH:
                return await self.result_add_high(interaction)
            case TrickOrTreat.REMOVE_INGOTS_LOW:
                return await self.result_remove_low(interaction)
            case TrickOrTreat.ADD_INGOTS_LOW:
                return await self.result_add_low(interaction)
            case TrickOrTreat.GIF:
                return await self.result_gif(interaction)

    async def result_jackpot(self, interaction: discord.Interaction):
        assert interaction.guild
        if STATE.state["trick_or_treat_jackpot_claimed"]:
            embed = self._build_embed(
                (
                    "**Treat!** Or, well, it would have been... but you have been deemed unworthy.\n"
                    "I don't know what to tell you, I don't make the rules. 🤷‍♂️"
                    "\n\nHave a consolation pumpkin emoji 🎃"
                )
            )
            return await interaction.followup.send(embed=embed)

        jackpot_value = 1_000_000

        user_new_total = await self._adjust_ingots(
            interaction,
            jackpot_value,
            interaction.guild.get_member(interaction.user.id),
        )

        STATE.state["trick_or_treat_jackpot_claimed"] = True

        embed = self._build_embed(
            (
                f"**JACKPOT!!** 🎉🎊🥳\n\nToday is your lucky day {interaction.user.mention}!\n"
                f"You have been blessed with the biggest payout I am authorized to give.\n\n"
                f"A cool **{self.ingot_icon}{jackpot_value:,}** ingots wired directly into your bank account.\n\n"
                "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n"
                "`wave2:rainbow:gzzzzzzzzzzzzzzzzzzzzzzzzzzzzz`"
                + self._get_balance_message(
                    interaction.user.display_name, user_new_total
                )
            )
        )
        embed.set_thumbnail(
            url="https://oldschool.runescape.wiki/images/thumb/Great_cauldron_%28overflowing%29.png/1280px-Great_cauldron_%28overflowing%29.png"
        )
        return await interaction.followup.send(embed=embed)

    async def result_remove_all_ingots_trick(self, interaction: discord.Interaction):
        async for session in db.get_session():
            member_service = MemberService(session)
            member = await member_service.get_member_by_discord_id(interaction.user.id)

            if member is None:
                return await send_error_response(
                    interaction,
                    f"Member '{interaction.user.display_name}' not found in storage.",
                )

            embed = ""
            if member.ingots < 1:
                embed = self._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            else:
                embed = self._build_embed(
                    (
                        f"You lost **{self.ingot_icon}{member.ingots:,}**...\nNow that's gotta sting."
                        + self._get_balance_message(interaction.user.display_name, 0)
                    )
                )
            embed.set_thumbnail(
                url="https://oldschool.runescape.wiki/images/thumb/Skull_%28item%29_detail.png/1024px-Skull_%28item%29_detail.png"
            )
            return await interaction.followup.send(embed=embed)

    async def result_remove_high(self, interaction: discord.Interaction):
        assert interaction.guild
        quantity_removed = (random.randrange(100, 250, 1) * 10) * -1

        ingot_total = await self._adjust_ingots(
            interaction,
            quantity_removed,
            interaction.guild.get_member(interaction.user.id),
        )

        if ingot_total < 0:
            await interaction.followup.send(
                embed=self._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            )
            return

        message = self._get_random_negative_message().format(
            ingots=f"{self.ingot_icon}{quantity_removed:,}"
        )

        embed = self._build_embed(
            (
                message
                + self._get_balance_message(
                    interaction.user.display_name, ingot_total or 0
                )
            )
        )
        return await interaction.followup.send(embed=embed)

    async def result_add_high(self, interaction: discord.Interaction):
        assert interaction.guild
        quantity_added = random.randrange(150, 250, 1) * 10
        ingot_total = await self._adjust_ingots(
            interaction,
            quantity_added,
            interaction.guild.get_member(interaction.user.id),
        )

        message = self._get_random_positive_message().format(
            ingots=f"{self.ingot_icon}{quantity_added:,}"
        )

        embed = self._build_embed(
            (
                message
                + self._get_balance_message(
                    interaction.user.display_name, ingot_total or 0
                )
            )
        )
        return await interaction.followup.send(embed=embed)

    async def result_remove_low(self, interaction: discord.Interaction):
        assert interaction.guild
        quantity_removed = (random.randrange(1, 100, 1) * 10) * -1
        ingot_total = await self._adjust_ingots(
            interaction,
            quantity_removed,
            interaction.guild.get_member(interaction.user.id),
        )

        if ingot_total < 0:
            return await interaction.followup.send(
                embed=self._build_no_ingots_error_response(
                    interaction.user.display_name
                )
            )

        message = self._get_random_negative_message().format(
            ingots=f"{self.ingot_icon}{quantity_removed:,}"
        )

        embed = self._build_embed(
            (
                message
                + self._get_balance_message(
                    interaction.user.display_name, ingot_total or 0
                )
            )
        )
        return await interaction.followup.send(embed=embed)

    async def result_add_low(self, interaction: discord.Interaction):
        assert interaction.guild
        quantity_added = random.randrange(1, 100, 1) * 10
        ingot_total = await self._adjust_ingots(
            interaction,
            quantity_added,
            interaction.guild.get_member(interaction.user.id),
        )

        message = self._get_random_positive_message().format(
            ingots=f"{self.ingot_icon}{quantity_added:,}"
        )

        embed = self._build_embed(
            (
                message
                + self._get_balance_message(
                    interaction.user.display_name, ingot_total or 0
                )
            )
        )
        return await interaction.followup.send(embed=embed)

    async def result_joke(self, interaction: discord.Interaction):
        jokes = [
            "**Why did the skeleton go to the party alone?**\n"
            "He had no body to go with! 🩻"
        ]

        await interaction.followup.send(embed=self._build_embed(random.choice(jokes)))

    async def result_gif(self, interaction: discord.Interaction):
        chosen_gif = random.choice([s for s in GIFS if s not in self.gif_history])
        self._add_to_history(chosen_gif, self.gif_history, 100)

        return await interaction.followup.send(chosen_gif)
