CREATE TABLE simulations
    (simulation_id INTEGER UNIQUE NOT NULL PRIMARY KEY ASC AUTOINCREMENT,
    simulation_uuid TEXT NOT NULL,
    status TEXT NOT NULL,
    current_date TEXT NOT NULL,
    current_time TEXT NOT NULL);

CREATE TABLE metadata
    (metadata_id INTEGER UNIQUE NOT NULL PRIMARY KEY ASC AUTOINCREMENT,
    metadata_set_uuid TEXT NOT NULL,
    element TEXT NOT NULL,
    value TEXT);

CREATE TABLE files
    (file_id INTEGER UNIQUE NOT NULL PRIMARY KEY ASC AUTOINCREMENT,
    file_uuid TEXT NOT NULL,
    metadata_set_uuid TEXT,
    useage TEXT,
    filename TEXT NOT NULL,
    directory TEXT,
    checksum TEXT,
    type TEXT,
    purpose TEXT,
    sensitivity TEXT,
    access TEXT,
    embargo TEXT,
    current_date TEXT NOT NULL,
    current_time TEXT NOT NULL,
    FOREIGN KEY(metadata_set_uuid) REFERENCES metadata(metadata_set_uuid));

CREATE TABLE simulation_files
    (simulation_files_id INTEGER UNIQUE NOT NULL PRIMARY KEY ASC AUTOINCREMENT,
    simulation_uuid TEXT NOT NULL,
    file_uuid TEXT NOT NULL,
    FOREIGN KEY(simulation_uuid) REFERENCES simulations(simulation_uuid),
    FOREIGN KEY(file_uuid) REFERENCES files(file_uuid));