import pathlib

path = pathlib.Path("templates/dashboard.html")
text = path.read_text(encoding="utf-8")

old = (
    "  <h2>Décisions de l'IA &amp; Self-Healing</h2>\n"
    "\n"
    '  <div class="cards">\n'
    '    <div class="card resolved">\n'
    '      <div class="value" id="selfHealingRatio">–</div>'
)
new = (
    "  <h2>Décisions de l'IA &amp; Self-Healing</h2>\n"
    "\n"
    '  <div class="cards">\n'
    '    <div class="card">\n'
    '      <div class="value" id="infraCpu">–</div>\n'
    '      <div class="label">CPU machine (%)</div>\n'
    '    </div>\n'
    '\n'
    '    <div class="card">\n'
    '      <div class="value" id="infraMem">–</div>\n'
    '      <div class="label">RAM machine (%)</div>\n'
    '    </div>\n'
    '\n'
    '    <div class="card resolved">\n'
    '      <div class="value" id="selfHealingRatio">–</div>'
)

if old not in text:
    raise SystemExit("ANCRAGE 0 INTROUVABLE")
text = text.replace(old, new, 1)

old2 = "    const decisionsData = await apiGet('/api/dashboard/decisions?limit=50');"
new2 = (
    "    const infra = await apiGet('/api/dashboard/infra');\n"
    "    document.getElementById('infraCpu').textContent =\n"
    "      infra.cpu_percent !== null ? infra.cpu_percent.toFixed(1) : '–';\n"
    "    document.getElementById('infraMem').textContent =\n"
    "      infra.memory_percent !== null ? infra.memory_percent.toFixed(1) : '–';\n"
    "\n"
    "    const decisionsData = await apiGet('/api/dashboard/decisions?limit=50');"
)
if old2 not in text:
    raise SystemExit("ANCRAGE 1 INTROUVABLE")
text = text.replace(old2, new2, 1)

path.write_text(text, encoding="utf-8")
print("dashboard.html patche pour infra (2/2 ancrages appliques).")
