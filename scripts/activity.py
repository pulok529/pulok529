"""Builds dist/activity.svg: the GitHub stats and language cards in the Nexus style.
Runs in the snake workflow with the workflow's GITHUB_TOKEN. Standard library only."""
import json, os, sys, urllib.request
from datetime import date, timedelta
from html import escape

USER = os.environ.get("GH_USER", "pulok529")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist/activity.svg"

Q = """query($login:String!,$cursor:String){user(login:$login){
 contributionsCollection{totalCommitContributions restrictedContributionsCount
  contributionCalendar{weeks{contributionDays{date contributionCount}}}}
 pullRequests{totalCount} issues{totalCount}
 repositories(first:100,after:$cursor,ownerAffiliations:OWNER,isFork:false){
  pageInfo{hasNextPage endCursor}
  nodes{stargazerCount languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}}}"""

def gql(cursor=None):
    req = urllib.request.Request("https://api.github.com/graphql",
        data=json.dumps({"query": Q, "variables": {"login": USER, "cursor": cursor}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]["user"]

def collect():
    u = gql(); repos = list(u["repositories"]["nodes"]); page = u["repositories"]["pageInfo"]
    while page["hasNextPage"]:
        nxt = gql(page["endCursor"]); repos += nxt["repositories"]["nodes"]; page = nxt["repositories"]["pageInfo"]
    cc = u["contributionsCollection"]
    days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    streak = 0
    today = date.today().isoformat()
    for d in reversed(days):
        if d["date"] == today and d["contributionCount"] == 0:
            continue  # today isn't over yet
        if d["contributionCount"] > 0:
            streak += 1
        else:
            break
    langs = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    return {
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs": u["pullRequests"]["totalCount"], "issues": u["issues"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos), "streak": streak,
        "langs": sorted(langs.items(), key=lambda kv: -kv[1])[:5],
    }

COLORS = ["#2EF2FF", "#A66BFF", "#2EF29A", "#FFB547", "#7E97A6"]

def render(s):
    W, H, gap = 880, 200, 16
    cw = (W - gap) // 2
    rows = [("Commits this year", s["commits"]), ("Pull requests", s["prs"]), ("Issues", s["issues"]),
            ("Stars earned", s["stars"]), ("Current streak", f'{s["streak"]} days')]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub stats and most used languages">',
           '<style>.t{font:600 18px "Chakra Petch","Segoe UI",sans-serif;fill:#2EF2FF}.l{font:400 14px "IBM Plex Sans","Segoe UI",sans-serif;fill:#C3D6E0}'
           '.v{font:500 14px "JetBrains Mono",Consolas,monospace;fill:#E6F6FF}.m{font:400 12px "IBM Plex Sans","Segoe UI",sans-serif;fill:#7E97A6}'
           '.r{opacity:0;animation:in .5s ease-out forwards}@keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}'
           '.b{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:grow 1s ease-out forwards}@keyframes grow{to{transform:scaleX(1)}}'
           '@media (prefers-reduced-motion:reduce){.r,.b{animation:none;opacity:1;transform:none}}</style>']
    for x in (0, cw + gap):
        out.append(f'<rect x="{x+.5}" y=".5" width="{cw-1}" height="{H-1}" rx="10" fill="#0C1217" stroke="#2EF2FF" stroke-opacity=".18"/>')
    out.append('<text class="t" x="24" y="40">GitHub stats</text>')
    for i, (k, v) in enumerate(rows):
        y = 74 + i * 26
        out.append(f'<g class="r" style="animation-delay:{.15*i:.2f}s"><text class="l" x="24" y="{y}">{k}</text>'
                   f'<text class="v" x="{cw-24}" y="{y}" text-anchor="end">{escape(str(v))}</text></g>')
    x0 = cw + gap + 24; bw = cw - 48
    out.append(f'<text class="t" x="{x0}" y="40">Most used languages</text>')
    total = sum(n for _, n in s["langs"]) or 1
    x = x0
    for i, (name, n) in enumerate(s["langs"]):
        w = max(4, bw * n / total - 3)
        out.append(f'<rect class="b" style="animation-delay:{.12*i:.2f}s" x="{x:.1f}" y="62" width="{w:.1f}" height="10" rx="3" fill="{COLORS[i]}"/>')
        x += w + 3
    for i, (name, n) in enumerate(s["langs"]):
        cx = x0 + (i % 3) * (bw / 3); cy = 104 + (i // 3) * 26
        out.append(f'<g class="r" style="animation-delay:{.4+.1*i:.2f}s"><circle cx="{cx+5:.1f}" cy="{cy-5}" r="5" fill="{COLORS[i]}"/>'
                   f'<text class="l" x="{cx+16:.1f}" y="{cy}">{escape(name)} <tspan class="m">{100*n/total:.0f}%</tspan></text></g>')
    out.append(f'<text class="m" x="{x0}" y="{H-20}">Public repos, updated daily</text></svg>')
    return "\n".join(out)

if __name__ == "__main__":
    data = json.load(open(os.environ["FAKE"])) if os.environ.get("FAKE") else collect()
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    open(OUT, "w").write(render(data))
    print(OUT, {k: v for k, v in data.items() if k != "langs"}, data["langs"])
