SELECT DISTINCT simulations.alias, simulations.uuid
FROM simulation_output_files, simulations, files
WHERE files.checksum IN (
    SELECT files.checksum
    FROM files, simulation_input_files, simulations
    WHERE simulation_input_files.file_id=files.id
      AND simulation_input_files.simulation_id=simulations.id
      AND simulations.uuid=:val
    )
  AND files.id=simulation_output_files.file_id
  AND simulations.id=simulation_output_files.simulation_id;

SELECT DISTINCT simulations.uuid, simulations.alias
FROM simulations
    JOIN simulation_output_files AS simulation_output_files_1 ON simulations.id = simulation_output_files_1.simulation_id
    JOIN files ON files.id = simulation_output_files_1.file_id
WHERE files.checksum IN (
    SELECT anon_1.checksum
    FROM (
        SELECT files.checksum AS checksum
        FROM files, simulation_input_files AS simulation_input_files_1
        WHERE files.checksum != ?
          AND files.id = simulation_input_files_1.file_id
          AND ? = simulation_input_files_1.simulation_id
        ) AS anon_1
    );


SELECT DISTINCT simulations.alias, simulations.uuid
FROM simulation_input_files, simulations, files
WHERE files.checksum IN (
    SELECT files.checksum
    FROM files, simulation_output_files, simulations
    WHERE simulation_output_files.file_id=files.id
      AND simulation_output_files.simulation_id=simulations.id
      AND simulations.uuid=:val
    )
  AND files.id=simulation_input_files.file_id
  AND simulations.id=simulation_input_files.simulation_id;