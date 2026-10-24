# MUC Crew 1 – Vorschau

Ein nachtrainiertes gemeinsames PPO-Netz mit öffentlicher Rundenplanung (Assistenzprofil 1). Die Planung sieht ausschließlich eigene Würfel und öffentliche Felder. Sie berücksichtigt Pflichtfelder, Landungsvorbereitungen, Kaffee und mögliche Neuwürfe. Module und Fähigkeitskarten einschließlich Zusatzwürfeln sind noch ausgeschlossen. Die historische Aktionsmaske und die alten Modelle bleiben unverändert verfügbar.

Die feste Validierung des ersten Kandidaten erreichte 83 Siege aus 100 vollständigen MUC-Partien. Dies ist eine vorläufige Selbstspiel-Auswertung; sie belegt noch keine entsprechende Erfolgsquote mit menschlichen Partnern. Der lokale Lauf liegt unter `runs/muc-natural-v1/train`.

Trainiert wird auf dem Apple M2 Pro: sechs isolierte CPU-Simulationen, PPO-Updates über Metal. 25 % der Rollout-Batches verwenden die unabhängige Heuristik als Partner, abwechselnd in beiden Rollen. Kaffee und Neuwurfauswahl verursachen bei der Berechnung der Returns keine zusätzliche Abzinsung.

Checkpoint und Browser-Gewichte sind zusammen mit dem Code versioniert. Das Assistenzprofil ist Teil des veröffentlichten Spielers und muss für reproduzierbare Auswertungen aktiviert bleiben.
