-- One current JSON snapshot per installation and game. Safe to run repeatedly.
CREATE TABLE IF NOT EXISTS training_sessions (
    participant_hash TEXT NOT NULL,
    session_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision > 0),
    mode TEXT NOT NULL CHECK (mode IN ('feedback', 'examples')),
    status TEXT NOT NULL,
    event_count INTEGER NOT NULL,
    received_at TEXT NOT NULL,
    payload TEXT NOT NULL CHECK (json_valid(payload)),
    PRIMARY KEY (participant_hash, session_id)
) WITHOUT ROWID;
