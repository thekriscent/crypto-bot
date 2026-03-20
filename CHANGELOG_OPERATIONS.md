Bot Change Ledger

For every change, append a new entry using this template.

Change ID
	•	Format: S-001, P-001, D-001, R-001
	•	S = strategy logic
	•	P = persistence / DB / logging
	•	D = dashboard / display
	•	R = runtime / deploy only

Required fields
	•	Change ID:
	•	Date/time requested (UTC):
	•	Commit hash:
	•	Files changed:
	•	Logic changed:
	•	Schema changed: Yes/No
	•	Selection logic changed: Yes/No
	•	Persistence/logging changed: Yes/No
	•	Replit pull completed at (UTC):
	•	Bot restarted at (UTC):
	•	Published at (UTC):
	•	First trusted post-change trade timestamp (UTC):
	•	Export/log captured at (UTC):
	•	Notes:

Rule

Never evaluate a patch using trades before the “First trusted post-change trade timestamp”.

Starter entries

Change ID:
	•	S-001
Date/time requested (UTC):
	•	UNKNOWN
Commit hash:
	•	8d85740c1a69d0d8cb829e336661d98acc924d7e
Files changed:
	•	import_json_log.py
	•	strategy_selection.py
	•	trend_bot.py
Logic changed:
	•	Fix EARLY_DOWN selection to continuation-or-skip.
Schema changed: Yes/No
	•	No
Selection logic changed: Yes/No
	•	Yes
Persistence/logging changed: Yes/No
	•	No
Replit pull completed at (UTC):
	•	UNKNOWN
Bot restarted at (UTC):
	•	UNKNOWN
Published at (UTC):
	•	UNKNOWN
First trusted post-change trade timestamp (UTC):
	•	UNKNOWN
Export/log captured at (UTC):
	•	UNKNOWN
Notes:
	•	Commit authored at 2026-03-20T18:58:54Z per git history.

Change ID:
	•	P-001
Date/time requested (UTC):
	•	UNKNOWN
Commit hash:
	•	a308b3dccacde5317a206485800ac124c9444747
Files changed:
	•	journal.py
Logic changed:
	•	Enforce final persistence invariants so skip_candidate forces selected = 0 and continuation EARLY_DOWN / CONFIRMED_DOWN forces trade_direction = DOWN before finalized rows are written.
Schema changed: Yes/No
	•	No
Selection logic changed: Yes/No
	•	No
Persistence/logging changed: Yes/No
	•	Yes
Replit pull completed at (UTC):
	•	UNKNOWN
Bot restarted at (UTC):
	•	UNKNOWN
Published at (UTC):
	•	UNKNOWN
First trusted post-change trade timestamp (UTC):
	•	UNKNOWN
Export/log captured at (UTC):
	•	UNKNOWN
Notes:
	•	Commit authored at 2026-03-20T21:33:30Z per git history.

Change ID:
	•	R-001
Date/time requested (UTC):
	•	UNKNOWN
Commit hash:
	•	UNKNOWN
Files changed:
	•	UNKNOWN
Logic changed:
	•	Latest Replit pull / restart / publish event placeholder. Populate when deployment timing is verified from platform logs or operator notes.
Schema changed: Yes/No
	•	No
Selection logic changed: Yes/No
	•	No
Persistence/logging changed: Yes/No
	•	No
Replit pull completed at (UTC):
	•	UNKNOWN
Bot restarted at (UTC):
	•	UNKNOWN
Published at (UTC):
	•	UNKNOWN
First trusted post-change trade timestamp (UTC):
	•	UNKNOWN
Export/log captured at (UTC):
	•	UNKNOWN
Notes:
	•	The latest deploy/restart could not be safely inferred from git history or the current conversation alone.
