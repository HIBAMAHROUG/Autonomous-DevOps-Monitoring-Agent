import pathlib

path = pathlib.Path("templates/dashboard.html")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        '<section id="historySection" style="display:none">',
        '<section id="decisionsSection" style="display:none">\n'
        '  <h2>Décisions de l\'IA &amp; Self-Healing</h2>\n'
        '\n'
        '  <div class="cards">\n'
        '    <div class="card resolved">\n'
        '      <div class="value" id="selfHealingRatio">–</div>\n'
        '      <div class="label">Taux d\'auto-résolution</div>\n'
        '    </div>\n'
        '\n'
        '    <div class="card">\n'
        '      <div class="value" id="avgMttr">–</div>\n'
        '      <div class="label">MTTR moyen (s)</div>\n'
        '    </div>\n'
        '\n'
        '    <div class="card">\n'
        '      <div class="value" id="totalIncidentsTracked">–</div>\n'
        '      <div class="label">Incidents suivis</div>\n'
        '    </div>\n'
        '  </div>\n'
        '\n'
        '  <table>\n'
        '    <thead>\n'
        '      <tr>\n'
        '        <th>Horodatage</th>\n'
        '        <th>Mode</th>\n'
        '        <th>Confiance</th>\n'
        '        <th>Action</th>\n'
        '        <th>Issue</th>\n'
        '        <th>Raison</th>\n'
        '      </tr>\n'
        '    </thead>\n'
        '\n'
        '    <tbody id="decisionsBody"></tbody>\n'
        '  </table>\n'
        '</section>\n'
        '\n'
        '<section id="historySection" style="display:none">'
    ),
    (
        "  document.getElementById('historySection').style.display = 'block';",
        "  document.getElementById('historySection').style.display = 'block';\n"
        "  document.getElementById('decisionsSection').style.display = 'block';"
    ),
    (
        'async function refresh() {\n  try {',
        'async function refresh() {\n'
        '  try {\n'
        '    const decisionsData = await apiGet(\'/api/dashboard/decisions?limit=50\');\n'
        '\n'
        '    document.getElementById(\'selfHealingRatio\').textContent =\n'
        '      (decisionsData.self_healing_ratio * 100).toFixed(0) + \'%\';\n'
        '    document.getElementById(\'avgMttr\').textContent =\n'
        '      decisionsData.avg_mttr_seconds.toFixed(0);\n'
        '    document.getElementById(\'totalIncidentsTracked\').textContent =\n'
        '      decisionsData.total_incidents;\n'
        '\n'
        '    const decisionsBody = document.getElementById(\'decisionsBody\');\n'
        '\n'
        '    decisionsBody.innerHTML = decisionsData.recent.map(d => `\n'
        '      <tr>\n'
        '        <td>${new Date(d.timestamp).toLocaleString(\'fr-FR\')}</td>\n'
        '        <td>${d.mode}</td>\n'
        '        <td>${d.confidence !== null ? (d.confidence * 100).toFixed(0) + \'%\' : \'–\'}</td>\n'
        '        <td>${d.action_type || \'–\'}</td>\n'
        '        <td>\n'
        '          <span class="status status-${d.outcome || \'escalated\'}">\n'
        '            ${d.outcome || \'en cours\'}\n'
        '          </span>\n'
        '        </td>\n'
        '        <td>${d.reason || \'–\'}</td>\n'
        '      </tr>\n'
        '    `).join(\'\') ||\n'
        '      \'<tr><td colspan="6" class="empty">Aucune décision journalisée.</td></tr>\';\n'
    ),
]

for i, (old, new) in enumerate(replacements):
    if old not in text:
        raise SystemExit(f"ANCRAGE {i} INTROUVABLE -- arret sans modification.\n{old[:150]!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("dashboard.html patche avec succes (3/3 ancrages appliques).")
