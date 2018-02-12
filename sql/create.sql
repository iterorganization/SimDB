PRAGMA foreign_keys = ON;

CREATE TABLE simulations (
    simulation_id INTEGER PRIMARY KEY ASC AUTOINCREMENT,
    simulation_uuid TEXT NOT NULL,
    alias TEXT,
    status TEXT NOT NULL,
    current_datetime TEXT NOT NULL
);

CREATE TABLE metadata (
    metadata_id INTEGER PRIMARY KEY ASC AUTOINCREMENT,
    metadata_set_uuid TEXT NOT NULL,
    element TEXT NOT NULL,
    value TEXT
);

CREATE TABLE files (
    file_id INTEGER PRIMARY KEY ASC AUTOINCREMENT,
    file_uuid TEXT NOT NULL,
    metadata_set TEXT REFERENCES metadata(metadata_id) ON DELETE CASCADE,
    usage TEXT,
    file_name TEXT NOT NULL,
    directory TEXT,
    checksum TEXT,
    type TEXT,
    purpose TEXT,
    sensitivity TEXT,
    access TEXT,
    embargo TEXT,
    current_datetime TEXT NOT NULL
);

CREATE TABLE simulation_files (
    simulation_files_id INTEGER PRIMARY KEY ASC AUTOINCREMENT,
    simulation INTEGER NOT NULL REFERENCES simulations(simulation_id) ON DELETE CASCADE,
    file INTEGER NOT NULL REFERENCES files(file_id) ON DELETE CASCADE
);