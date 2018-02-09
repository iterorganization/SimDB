CREATE TABLE simulations
    (simulation_id INTEGER PRIMARY KEY ASC AUTOINCREMENT,
    simulation_uuid TEXT NOT NULL,
    status TEXT NOT NULL,
    current_datetime TEXT NOT NULL);

CREATE TABLE metadata
    (metadata_id INTEGER PRIMARY KEY ASC AUTOINCREMENT,
    metadata_set_uuid TEXT NOT NULL,
    element TEXT NOT NULL,
    value TEXT);

CREATE TABLE files
    (file_id INTEGER PRIMARY KEY ASC AUTOINCREMENT,
    file_uuid TEXT NOT NULL,
    metadata_set TEXT,
    useage TEXT,
    file_name TEXT NOT NULL,
    directory TEXT,
    checksum TEXT,
    type TEXT,
    purpose TEXT,
    sensitivity TEXT,
    access TEXT,
    embargo TEXT,
    current_datetime TEXT NOT NULL,
    FOREIGN KEY(metadata_set) REFERENCES metadata(metadata_id));

CREATE TABLE simulation_files
    (simulation_files_id INTEGER PRIMARY KEY ASC AUTOINCREMENT,
    simulation TEXT NOT NULL,
    file TEXT NOT NULL,
    FOREIGN KEY(simulation) REFERENCES simulations(simulation_id),
    FOREIGN KEY(file) REFERENCES files(file_id));