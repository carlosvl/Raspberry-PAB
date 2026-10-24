"""Team-level contacts from MCA's Team Finder (https://minnesotacycling.org/team-finder-2/).

Only the team website and the team address MCA publishes there; no rider or
parent contacts. Copied 2026-10-13, so re-check the page if one bounces.
"""

from __future__ import annotations

from dataclasses import dataclass

from raspberry_pab.race_results.state_qualification import normalize_team

TEAM_FINDER_URL = "https://minnesotacycling.org/team-finder-2/"


@dataclass(frozen=True)
class TeamContact:
    team: str  # Team Finder name
    site: str  # "" when none is listed
    email: str  # "" when none is listed


_CEC = TeamContact(
    "CEC Cycling Comp",
    "https://www.missionnorthcycling.org/cec-mtb",
    "cec-coach@outlook.com",
)
_CCMTB = TeamContact(
    "Chanhassen / Chaska / Eden Prairie HS",
    "https://www.ccmtbike.com/",
    "admin@ccmtbike.com",
)
_CPOMG = TeamContact(
    "Champlin Park / Osseo / Maple Grove",
    "https://www.facebook.com/cpomgmtb/",
    "Info@cpomg.org",
)
_CUYUNA = TeamContact(
    "Cuyuna / Brainerd / Crosby High School",
    "https://www.facebook.com/cuyunalakeshsmtb/",
    "hagensean7@gmail.com",
)
_196 = TeamContact("196 MTB", "http://www.196mtb.org/", "")
_PWER = TeamContact("PWER", "http://www.pwermtb.org/", "")
_STCROIX = TeamContact("St Croix Valley Comp", "http://www.stcroixcomposite.com/", "")
_MANKATO = TeamContact("Mankato Comp", "", "mankatomtb@hickorytech.net")
_ELK = TeamContact(
    "Elk River Composite / ISD827", "", "elkrivercompositemtbteam@gmail.com"
)
_WESTONKA = TeamContact(
    "Westonka Composite",
    "https://www.facebook.com/MoundWestonkaMTB",
    "WestonkaMTB@gmail.com",
)
_MV = TeamContact(
    "Mounds View / Irondale / Totino Grace",
    "http://www.moudsviewbiketeam.org/",
    "mvbiketeam@gmail.com",
)
_LAKES = TeamContact(
    "Lakes Area Composite",
    "https://www.facebook.com/LakesAreaMTB",
    "lakesareacmt@gmail.com",
)

# Result-sheet school name (normalized) -> Team Finder entry. Schools without a
# confident match (Minneapolis and St Paul city schools) are left out.
_CONTACTS: dict[str, TeamContact] = {
    "alexandria youth cycling": TeamContact(
        "Alexandria Mountaineers", "", "aayc@alexschools.org"
    ),
    "apple valley hs": _196,
    "armstrong cycle": TeamContact(
        "Armstrong Cycle Club", "http://www.armstrongcycleclub.com/", ""
    ),
    "austin hs": TeamContact(
        "Austin Comp",
        "https://www.facebook.com/AustinAreamountainbiking",
        "austin.mn.cycling@gmail.com",
    ),
    "bemidji": TeamContact("Bemidji Composite", "", "mlarson@treknorth.org"),
    "borealis": TeamContact(
        "Team Borealis", "https://teamborealis.org/", "teamborealismn@gmail.com"
    ),
    "brainerd hs": _CUYUNA,
    "champlin park hs": _CPOMG,
    "chanhassen hs": _CCMTB,
    "chaska hs": _CCMTB,
    "cloquet-esko-carlton": _CEC,
    "crosby-ironton hs": _CUYUNA,
    "eagan hs": _196,
    "east ridge hs": _PWER,
    "eastview hs": _196,
    "edina cycling": TeamContact(
        "Edina", "https://www.edinacyclingteam.com/", "mhartmann403@gmail.com"
    ),
    "elk river": _ELK,
    "hermantown-proctor": TeamContact(
        "Hermantown-Proctor",
        "https://www.missionnorthcycling.org/hpc-mtb",
        "cec-coach@outlook.com",
    ),
    "hopkins hs": TeamContact(
        "Hopkins High School", "http://hopkinsmountainbiketeam.com/", ""
    ),
    "hudson hs": _STCROIX,
    "isd728": _ELK,
    "lakes area composite": _LAKES,
    "lakeville north hs": TeamContact(
        "Lakeville North & South", "https://www.lakevillemtb.com/", ""
    ),
    "lakeville south": TeamContact(
        "Lakeville North & South", "https://www.lakevillemtb.com/", ""
    ),
    "maple grove hs": _CPOMG,
    "mankato": _MANKATO,
    "mankato west hs": _MANKATO,
    "minnesota valley": TeamContact(
        "Minnesota Valley MTB",
        "https://minnesotavalleymtbteam.com/",
        "jon.rosemeier@gmail.com",
    ),
    "minnetonka hs": TeamContact(
        "Minnetonka High School", "http://www.facebook.com/TONKA.MTB", ""
    ),
    "mounds view hs": _MV,
    "northwest": TeamContact("Northwest Comp", "", "nwcompmtb@gmail.com"),
    "orono hs": TeamContact("Orono High School", "", "oronomtb@gmail.com"),
    "park hs": _PWER,
    "prior lake hs": TeamContact(
        "Prior Lake High School",
        "http://www.plhsactivities.org/page/show/550813-mountain-biking",
        "",
    ),
    "river falls hs": _STCROIX,
    "rochester area": TeamContact("Rochester Comp", "", "info@rochmtb.org"),
    "rochester century hs": TeamContact("Century High School", "", "rochmtb@gmail.com"),
    "rock ridge": TeamContact(
        "Rock Ridge Composite",
        "https://www.facebook.com/rockridgemtb",
        "rockridgemtbteam@gmail.com",
    ),
    "rockford": TeamContact(
        "Rockford Comp",
        "https://www.facebook.com/RockfordMTB/",
        "rockfordmtb@gmail.com",
    ),
    "rosemount hs": _196,
    "roseville": TeamContact("Roseville Area Comp", "", "racmtbmn@gmail.com"),
    "shakopee hs": TeamContact("Shakopee High School", "", "joman@shakopee.k12.mn.us"),
    "st cloud": TeamContact("St Cloud Area Comp", "", "mike@fitzharrismn.com"),
    "st louis park hs": TeamContact(
        "St. Louis Park HS / BB Bikers", "https://slpmtb.org/", "coach@slpmtb.org"
    ),
    "st paul central": TeamContact(
        "St. Paul Central", "https://centralmtb.com/", "headcoach@centralmtb.com"
    ),
    "stillwater mountain bike": TeamContact(
        "Stillwater High School",
        "http://www.stillwatermtb.com/",
        "director@sasca-mn.org",
    ),
    "tioga trailblazers": TeamContact(
        "Tioga Trailblazers", "", "jhconnelly2@gmail.com"
    ),
    "totino grace-irondale": _MV,
    "watertown-mayer": _WESTONKA,
    "wayzata mountain bike": TeamContact(
        "Wayzata",
        "https://www.wayzataschools.org/communityed/youth/classes",
        "communityed@wayzataschools.org",
    ),
    "westonka": _WESTONKA,
    "white bear lake hs": TeamContact(
        "White Bear Lake High School",
        "https://www.facebook.com/wblmountainbiketeam",
        "wbl.mtb@gmail.com",
    ),
    "winona": TeamContact(
        "Winona Composite",
        "https://www.facebook.com/winonacompmtb",
        "winmtbteam@gmail.com",
    ),
    "woodbury hs": _PWER,
}


def team_contact(school: str) -> TeamContact | None:
    return _CONTACTS.get(normalize_team(school))


def contact_text(school: str) -> str:
    """Markdown cell: team site and published team address, or a Team Finder link."""
    contact = team_contact(school)
    if contact is None:
        return f"[Team Finder]({TEAM_FINDER_URL})"
    parts = [f"[{contact.team}]({contact.site})" if contact.site else contact.team]
    if contact.email:
        parts.append(f"[{contact.email}](mailto:{contact.email})")
    return " · ".join(parts)
