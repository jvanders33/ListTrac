-- ListTrac v1 schema (AFL)

CREATE TABLE club (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    abbreviation TEXT NOT NULL,
    primary_color TEXT,
    secondary_color TEXT,
    logo_url TEXT
);

CREATE TABLE player (
    id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    dob DATE,
    height_cm INTEGER,
    weight_kg INTEGER,
    position TEXT,                     -- comma-separated or normalize to player_position later
    current_club_id INTEGER REFERENCES club(id),
    jumper_number INTEGER,
    debut_year INTEGER,
    draft_pick_id INTEGER REFERENCES draft_pick(id),
    afl_tables_id TEXT,                -- external ID for reconciliation
    footywire_id TEXT,
    draftguru_id TEXT,                 -- /players/{slug}/{n} path from draftguru
    status TEXT CHECK (status IN ('listed','delisted','retired','unattached')) NOT NULL DEFAULT 'listed'
);

CREATE TABLE contract_status (
    id INTEGER PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES player(id),
    club_id INTEGER NOT NULL REFERENCES club(id),
    contracted_through_year INTEGER,
    status TEXT CHECK (status IN ('contracted','out_of_contract','restricted_fa','unrestricted_fa')) NOT NULL,
    source_note TEXT,
    source_url TEXT,
    last_confirmed_date DATE,
    is_current BOOLEAN NOT NULL DEFAULT 1   -- flip to 0 when superseded; keep history
);

-- named player_transaction because TRANSACTION is a SQL reserved word
CREATE TABLE player_transaction (
    id INTEGER PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES player(id),
    type TEXT CHECK (type IN ('trade','delist','retire','sign_fa','rookie_elevate','sign_rookie')) NOT NULL,
    from_club_id INTEGER REFERENCES club(id),
    to_club_id INTEGER REFERENCES club(id),
    date DATE NOT NULL,
    trade_period_year INTEGER,
    source_url TEXT,
    notes TEXT
);

CREATE TABLE draft_pick (
    id INTEGER PRIMARY KEY,
    year INTEGER NOT NULL,
    draft_type TEXT CHECK (draft_type IN ('national','rookie','pre_season','mid_season','sandover')) NOT NULL,
    original_club_id INTEGER NOT NULL REFERENCES club(id),
    current_owner_club_id INTEGER NOT NULL REFERENCES club(id),
    pick_number INTEGER,
    points_value INTEGER,
    status TEXT CHECK (status IN ('used','traded','forfeited')) NOT NULL DEFAULT 'used',
    player_selected_id INTEGER REFERENCES player(id)
);

CREATE TABLE draft_pick_trade_history (
    id INTEGER PRIMARY KEY,
    -- NULL when a traded future pick can't be tied to a specific selection
    -- (lapsed, passed, or unresolved at scrape time) — description keeps the raw text
    draft_pick_id INTEGER REFERENCES draft_pick(id),
    description TEXT,
    from_club_id INTEGER NOT NULL REFERENCES club(id),
    to_club_id INTEGER NOT NULL REFERENCES club(id),
    transaction_id INTEGER REFERENCES player_transaction(id),
    date DATE NOT NULL
);

-- Indexes for the lookups the UI will hammer
CREATE INDEX idx_player_current_club ON player(current_club_id);
CREATE INDEX idx_contract_status_player ON contract_status(player_id, is_current);
CREATE INDEX idx_transaction_player ON player_transaction(player_id);
CREATE INDEX idx_draft_pick_year ON draft_pick(year, draft_type);
